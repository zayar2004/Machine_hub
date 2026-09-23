"""User — Update Package import routes."""
from pathlib import Path
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, current_app,
)
from flask_login import login_required, current_user

from app.services.update_package import (
    validate_package, apply_package, ImportError,
)

user_updates_bp = Blueprint(
    "user_updates",
    __name__,
    url_prefix="/user/updates",
)


def _upload_dir() -> Path:
    p = Path(current_app.instance_path) / "update_packages"
    p.mkdir(parents=True, exist_ok=True)
    return p


@user_updates_bp.route("/", methods=["GET"])
@login_required
def index():
    """Landing — history + import link."""
    return render_template("user/updates/index.html")


@user_updates_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_package():
    """Upload + validate + apply."""
    if request.method == "GET":
        return render_template("user/updates/import.html")

    # === POST ===
    f = request.files.get("package")
    if not f or not f.filename:
        flash("Package file ရွေးပါ", "error")
        return redirect(url_for("user_updates.import_package"))

    if not f.filename.endswith(".zip"):
        flash("Only .zip files accepted", "error")
        return redirect(url_for("user_updates.import_package"))

    # Save upload
    safe_name = Path(f.filename).name
    dest = _upload_dir() / safe_name
    f.save(dest)

    # Validate
    try:
        info = validate_package(dest)
    except ImportError as e:
        flash(f"❌ Validation failed: {e}", "error")
        return redirect(url_for("user_updates.import_package"))
    except Exception as e:
        current_app.logger.exception("Package validate failed")
        flash(f"❌ Invalid package: {e}", "error")
        return redirect(url_for("user_updates.import_package"))

    # Show confirm page
    return render_template(
        "user/updates/confirm.html",
        manifest=info["manifest"],
        counts=info["counts"],
        images_count=info["images_count"],
        zip_size=info["zip_size"],
        zip_name=safe_name,
    )


@user_updates_bp.route("/apply", methods=["POST"])
@login_required
def apply():
    """Confirm → apply."""
    zip_name = request.form.get("zip_name", "")
    if not zip_name:
        flash("Missing package name", "error")
        return redirect(url_for("user_updates.import_package"))

    safe_name = Path(zip_name).name
    dest = _upload_dir() / safe_name

    if not dest.exists():
        flash("Package file not found", "error")
        return redirect(url_for("user_updates.import_package"))

    # User's allowed shops
    shop_ids = [current_user.shop_id] if current_user.shop_id else None

    try:
        result = apply_package(
            dest,
            current_app._get_current_object(),
            shop_ids=shop_ids,
        )
    except ImportError as e:
        flash(f"❌ Apply failed: {e}", "error")
        return redirect(url_for("user_updates.import_package"))
    except Exception as e:
        current_app.logger.exception("Package apply failed")
        flash(f"❌ Apply failed: {e}", "error")
        return redirect(url_for("user_updates.import_package"))

    # Cleanup upload
    try:
        dest.unlink()
    except Exception:
        pass

    return render_template(
        "user/updates/result.html",
        result=result,
    )
