"""
Update Package — Importer

Reads .zip, validates, applies data (atomic + rollback).
"""
import json
import zipfile
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from io import BytesIO


class ImportError(Exception):
    """Raised when package is invalid."""


# Fields that are datetime — must be parsed from ISO string
_DATETIME_FIELDS = {"created_at", "updated_at", "last_login", "imported_at"}


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _parse_row(row: dict) -> dict:
    """Convert ISO date strings → datetime objects."""
    from datetime import datetime
    out = {}
    for k, v in row.items():
        if k in _DATETIME_FIELDS and isinstance(v, str) and v:
            try:
                # Handle both with/without timezone
                s = v.replace("Z", "+00:00")
                out[k] = datetime.fromisoformat(s)
            except Exception:
                out[k] = None
        else:
            out[k] = v
    return out


def validate_package(zip_path: Path) -> dict:
    """
    Validate package without applying.

    Returns:
        dict with manifest + counts + validation results

    Raises:
        ImportError on failure
    """
    zip_path = Path(zip_path)
    if not zip_path.exists():
        raise ImportError(f"File not found: {zip_path}")

    if not zipfile.is_zipfile(zip_path):
        raise ImportError("Not a valid .zip file")

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()

        # Required files
        if "manifest.json" not in names:
            raise ImportError("manifest.json not found")

        # Read manifest
        try:
            manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        except Exception as e:
            raise ImportError(f"manifest.json invalid: {e}")

        # Required fields
        for field in ["app", "package_version", "data_version", "counts"]:
            if field not in manifest:
                raise ImportError(f"manifest missing field: {field}")

        if manifest["app"] != "Machine Hub":
            raise ImportError(f"Wrong app: {manifest['app']}")

        # Version format X.Y.Z
        parts = manifest["package_version"].split(".")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ImportError(f"Invalid version: {manifest['package_version']}")

        # Validate checksums
        checksums = manifest.get("checksums", {})
        if not checksums:
            raise ImportError("manifest missing checksums")

        errors = []
        for name, expected in checksums.items():
            if name not in names:
                errors.append(f"missing: {name}")
                continue
            actual = _sha256_bytes(zf.read(name))
            if actual != expected:
                errors.append(f"checksum mismatch: {name}")

        if errors:
            raise ImportError("Checksum errors: " + "; ".join(errors))

        # Read data files
        data = {}
        for name in names:
            if name.startswith("data/") and name.endswith(".json"):
                key = Path(name).stem
                try:
                    data[key] = json.loads(zf.read(name).decode("utf-8"))
                except Exception as e:
                    raise ImportError(f"data file invalid: {name}: {e}")

        # Count data
        actual_counts = {
            "shops": len(data.get("shops", [])),
            "machines": len(data.get("machines", [])),
            "errors": len(data.get("errors", [])),
            "error_images": len(data.get("error_images", [])),
            "machine_errors": len(data.get("machine_errors", [])),
            "users": len(data.get("users", [])),
        }

        # Compare to manifest counts
        manifest_counts = manifest.get("counts", {})
        for k, v in actual_counts.items():
            if manifest_counts.get(k, 0) != v:
                raise ImportError(
                    f"count mismatch for {k}: manifest={manifest_counts.get(k, 0)}, actual={v}"
                )

        return {
            "manifest": manifest,
            "data": data,
            "counts": actual_counts,
            "images_count": sum(1 for n in names if n.startswith("images/")),
            "zip_size": zip_path.stat().st_size,
        }


def apply_package(zip_path: Path, target_app, *, shop_ids=None):
    """
    Apply package to target app's DB (atomic).

    Args:
        zip_path: Path to .zip
        target_app: Flask app to apply to
        shop_ids: optional list of shop IDs to restrict (for User)
                  None = apply all

    Returns:
        dict with summary

    Raises:
        ImportError on failure (DB unchanged — rollback)
    """
    from app.extensions import db
    from app.models import Shop, Machine, Error, ErrorImage, User
    from app.models import machine_errors as me_table

    info = validate_package(zip_path)
    manifest = info["manifest"]
    data = info["data"]

    # Shop authorization (User)
    if shop_ids is not None:
        pkg_shop_ids = set(manifest.get("shop_ids", []))
        allowed = set(shop_ids)
        unauthorized = pkg_shop_ids - allowed
        if unauthorized:
            raise ImportError(
                f"Package contains unauthorized shops: {sorted(unauthorized)}"
            )

    with target_app.app_context():
        try:
            # === DELETE existing data ===
            db.session.execute(me_table.delete())
            ErrorImage.query.delete()
            Error.query.delete()
            Machine.query.delete()
            # Keep current session user + admin
            # (Avoid deleting the logged-in user account)
            from flask_login import current_user
            keep_usernames = {"admin"}
            try:
                if current_user and current_user.is_authenticated:
                    keep_usernames.add(current_user.username)
            except Exception:
                pass
            pkg_usernames = {u.get("username") for u in data.get("users", []) if u.get("username")}
            keep_usernames.update(pkg_usernames)

            User.query.filter(
                ~User.username.in_(keep_usernames)
            ).delete(synchronize_session=False)
            # Keep admin
            Shop.query.delete()

            # === INSERT new data (order: parents first) ===
            # Shops
            for row in data.get("shops", []):
                s = Shop(**_parse_row(row))
                db.session.add(s)
            db.session.flush()

            # Users (non-admin)
            for row in data.get("users", []):
                if row.get("username") == "admin":
                    continue
                u = User(**_parse_row(row))
                db.session.add(u)
            db.session.flush()

            # Machines
            for row in data.get("machines", []):
                m = Machine(**_parse_row(row))
                db.session.add(m)
            db.session.flush()

            # Errors
            for row in data.get("errors", []):
                e = Error(**_parse_row(row))
                db.session.add(e)
            db.session.flush()

            # Error images
            for row in data.get("error_images", []):
                img = ErrorImage(**_parse_row(row))
                db.session.add(img)

            # Machine errors (M2M)
            for row in data.get("machine_errors", []):
                db.session.execute(
                    me_table.insert().values(
                        machine_id=row["machine_id"],
                        error_id=row["error_id"],
                    )
                )

            db.session.commit()

        except Exception as e:
            db.session.rollback()
            raise ImportError(f"Apply failed: {e}")

        # === Reset sequences (Postgres) ===
        from sqlalchemy import text
        for t in ["shops", "users", "machines", "errors",
                  "error_images", "machine_errors"]:
            try:
                db.session.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), "
                    f"COALESCE(MAX(id), 1)) FROM {t}"
                ))
            except Exception:
                pass
        db.session.commit()

    return {
        "manifest": manifest,
        "counts": info["counts"],
        "images_count": info["images_count"],
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }
