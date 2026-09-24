"""Admin — Update Package routes."""
from pathlib import Path
from datetime import datetime, timezone
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, send_file, current_app, jsonify,
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Shop, Machine, Error, ErrorImage, User, ImportBatch
from app.models import machine_errors as me_table
from app.services.update_package import create_package, PACKAGE_VERSION
from app.utils.decorators import admin_required

admin_updates_bp = Blueprint(
    "admin_updates",
    __name__,
    url_prefix="/admin/updates",
)


def _packages_dir() -> Path:
    """Return app/static/updates/ (create if missing)."""
    p = Path(current_app.root_path) / "static" / "updates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _list_packages():
    """List existing .zip packages in static/updates/."""
    p = _packages_dir()
    items = []
    for f in sorted(p.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True):
        st = f.stat()
        items.append({
            "name": f.name,
            "size": st.st_size,
            "size_h": _human_size(st.st_size),
            "mtime": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        })
    return items


def _human_size(n: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


@admin_updates_bp.route("/", methods=["GET"])
@login_required
@admin_required
def index():
    packages = _list_packages()
    return render_template(
        "admin/updates/index.html",
        packages=packages,
        version=PACKAGE_VERSION,
    )


@admin_updates_bp.route("/create", methods=["GET", "POST"])
@login_required
@admin_required
def create():
    shops = Shop.query.order_by(Shop.id).all()

    if request.method == "GET":
        # Add machine count + codes preview per shop
        shop_info = []
        for s in shops:
            machine_count = Machine.query.filter_by(shop_id=s.id).count()
            machine_codes = [
                m.machine_code for m in
                Machine.query.filter_by(shop_id=s.id).order_by(Machine.machine_code).limit(10).all()
            ]
            shop_info.append({
                "shop": s,
                "machine_count": machine_count,
                "machine_codes_preview": machine_codes,
            })
        return render_template(
            "admin/updates/create.html",
            shops=shops,
            shop_info=shop_info,
            version=PACKAGE_VERSION,
        )

    # === POST — generate package ===
    shop_ids = request.form.getlist("shop_ids")
    include_images = request.form.get("include_images") == "on"
    include_users = request.form.get("include_users") == "on"
    include_errors = request.form.get("include_errors") == "on"

    if not shop_ids:
        flash("Shop အနည်းဆုံး ၁ ခု ရွေးပါ", "error")
        return redirect(url_for("admin_updates.create"))

    try:
        shop_ids_int = [int(s) for s in shop_ids]
    except ValueError:
        flash("Invalid shop selection", "error")
        return redirect(url_for("admin_updates.create"))

    selected_shops = Shop.query.filter(Shop.id.in_(shop_ids_int)).all()
    machines = Machine.query.filter(Machine.shop_id.in_(shop_ids_int)).all()

    if include_errors:
        errors = Error.query.all()
    else:
        errors = []

    # error images linked to selected errors
    if errors:
        error_ids = [e.id for e in errors]
        error_images = ErrorImage.query.filter(
            ErrorImage.error_id.in_(error_ids)
        ).all()
    else:
        error_images = []

    # machine_errors M2M
    machine_ids = [m.id for m in machines]
    me_rows = []
    if machine_ids:
        rows = db.session.execute(
            me_table.select().where(me_table.c.machine_id.in_(machine_ids))
        ).fetchall()
        me_rows = [(r[0], r[1]) for r in rows]

    users = []
    if include_users:
        users = User.query.filter(User.shop_id.in_(shop_ids_int)).all()

    # Output path — knowledge_update_<ts>.zip
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_name = f"knowledge_update_{ts}.zip"
    out_path = _packages_dir() / out_name

    try:
        info = create_package(
            shops=selected_shops,
            machines=machines,
            errors=errors,
            error_images=error_images,
            machine_errors=me_rows,
            import_batches=ImportBatch.query.all(),
            users=users,
            output_path=out_path,
            created_by=current_user.username,
            include_images=include_images,
        )
    except Exception as e:
        current_app.logger.exception("Package create failed")
        flash(f"Package create failed: {e}", "error")
        return redirect(url_for("admin_updates.create"))

    flash(
        f"✅ Package created: {out_name} "
        f"({_human_size(info['size'])}, "
        f"{info['counts']['machines']} machines, "
        f"{info['counts']['errors']} errors)",
        "success",
    )
    return redirect(url_for("admin_updates.index"))


@admin_updates_bp.route("/download/<name>", methods=["GET"])
@login_required
@admin_required
def download(name: str):
    # sanitize
    safe = Path(name).name
    p = _packages_dir() / safe
    if not p.exists() or not p.is_file():
        flash("File not found", "error")
        return redirect(url_for("admin_updates.index"))
    return send_file(p, as_attachment=True, download_name=safe)


@admin_updates_bp.route("/delete/<name>", methods=["POST"])
@login_required
@admin_required
def delete(name: str):
    safe = Path(name).name
    p = _packages_dir() / safe
    if p.exists() and p.is_file():
        p.unlink()
        flash(f"Deleted: {safe}", "success")
    else:
        flash("File not found", "error")
    return redirect(url_for("admin_updates.index"))
