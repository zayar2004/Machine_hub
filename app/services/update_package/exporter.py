"""
Update Package — Exporter

Creates a .zip package with data + images + manifest.
"""
import json
import hashlib
import zipfile
from pathlib import Path
from datetime import datetime, timezone
from io import BytesIO

PACKAGE_VERSION = "1.0.0"


def _serialize_row(obj):
    """Convert SQLAlchemy model → dict (dates to ISO)."""
    d = {}
    for col in obj.__table__.columns:
        v = getattr(obj, col.name)
        if hasattr(v, "isoformat"):
            v = v.isoformat()
        d[col.name] = v
    return d


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def create_package(
    *,
    shops,
    machines,
    errors,
    error_images,
    machine_errors,
    users,
    output_path: Path,
    created_by: str = "admin",
    include_images: bool = True,
):
    """
    Create a .zip package.

    Args:
        shops: list of Shop models
        machines: list of Machine models
        errors: list of Error models
        error_images: list of ErrorImage models
        machine_errors: list of (machine_id, error_id) tuples
        users: list of User models (optional — for admin transfer)
        output_path: where to write .zip
        created_by: admin username
        include_images: include base64 images

    Returns:
        dict with package info (path, size, counts, checksums)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # === 1. Prepare data JSON ===
    data_files = {}

    data_files["shops.json"] = json.dumps(
        [_serialize_row(s) for s in shops],
        indent=2, ensure_ascii=False,
    ).encode("utf-8")

    data_files["machines.json"] = json.dumps(
        [_serialize_row(m) for m in machines],
        indent=2, ensure_ascii=False,
    ).encode("utf-8")

    data_files["errors.json"] = json.dumps(
        [_serialize_row(e) for e in errors],
        indent=2, ensure_ascii=False,
    ).encode("utf-8")

    data_files["error_images.json"] = json.dumps(
        [_serialize_row(img) for img in error_images],
        indent=2, ensure_ascii=False,
    ).encode("utf-8")

    data_files["machine_errors.json"] = json.dumps(
        [{"machine_id": mid, "error_id": eid} for mid, eid in machine_errors],
        indent=2, ensure_ascii=False,
    ).encode("utf-8")

    if users:
        data_files["users.json"] = json.dumps(
            [_serialize_row(u) for u in users],
            indent=2, ensure_ascii=False,
        ).encode("utf-8")

    # === 2. Prepare images ===
    image_files = {}  # relative_path -> bytes

    if include_images:
        for img in error_images:
            if not img.image_data:
                continue
            # Decode base64 → bytes
            import base64
            try:
                b = base64.b64decode(img.image_data)
            except Exception:
                continue
            ext = "jpg"
            if img.mime_type == "image/png":
                ext = "png"
            elif img.mime_type == "image/webp":
                ext = "webp"
            rel = f"images/{img.error_id}/{img.id}.{ext}"
            image_files[rel] = b

    # === 3. Checksums ===
    checksums = {}
    for name, content in data_files.items():
        checksums[f"data/{name}"] = _sha256_bytes(content)
    for rel, content in image_files.items():
        checksums[rel] = _sha256_bytes(content)

    # === 4. Manifest ===
    manifest = {
        "app": "Machine Hub",
        "package_version": PACKAGE_VERSION,
        "data_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": created_by,
        "shop_ids": [s.id for s in shops],
        "counts": {
            "shops": len(shops),
            "machines": len(machines),
            "errors": len(errors),
            "error_images": len(error_images),
            "machine_errors": len(machine_errors),
            "users": len(users) if users else 0,
        },
        "checksums": checksums,
    }

    manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")

    # === 5. Write zip ===
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", manifest_bytes)
        for name, content in data_files.items():
            zf.writestr(f"data/{name}", content)
        for rel, content in image_files.items():
            zf.writestr(rel, content)
        # checksums.txt
        checksums_txt = "\n".join(f"{k}  {v}" for k, v in sorted(checksums.items()))
        zf.writestr("checksums.txt", checksums_txt.encode("utf-8"))

    size = output_path.stat().st_size

    return {
        "path": str(output_path),
        "size": size,
        "version": PACKAGE_VERSION,
        "counts": manifest["counts"],
        "checksums": checksums,
        "manifest": manifest,
    }
