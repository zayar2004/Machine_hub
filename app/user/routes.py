"""User routes with activity tracking."""
from flask import Blueprint, render_template, request, abort
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Machine, Error, Shop, Favorite, RepairHistory, SyncState
from ..utils import log_activity

user_bp = Blueprint("user", __name__)


def _user_shop():
    if current_user.is_admin:
        return None
    if current_user.shop_id is None:
        return None
    return db.session.get(Shop, current_user.shop_id)


def _machine_visible_to_user(machine):
    if current_user.is_admin:
        return True
    return machine.shop_id == current_user.shop_id


# ---------- home ----------

@user_bp.route("/uploads/<path:rel_path>")
@login_required
def serve_upload(rel_path):
    """Serve uploaded error photos — file OR base64 fallback.

    Priority:
      1. Local file (uploads/errors/...)
      2. DB image_data (base64) — Render persistent
    """
    from flask import current_app, send_from_directory, abort, Response
    import os, base64

    root = current_app.config.get("UPLOAD_FOLDER")
    if not root:
        abort(404)

    # Prevent path traversal
    safe = os.path.normpath(rel_path).lstrip("/")
    if ".." in safe.split(os.sep):
        abort(404)

    full = os.path.join(root, safe)

    # 1) Try local file
    if os.path.isfile(full):
        return send_from_directory(root, safe)

    # 2) Fallback — DB base64
    # rel_path: 'errors/ERROR_1/xxx.jpg'
    from ..models import ErrorImage
    img = ErrorImage.query.filter_by(image_path=safe).first()
    if img is None:
        # Try with 'uploads/' prefix stripped
        alt = safe
        if alt.startswith("uploads/"):
            alt = alt[8:]
        img = ErrorImage.query.filter_by(image_path=alt).first()

    if img and img.image_data:
        try:
            raw = base64.b64decode(img.image_data)
            mime = img.mime_type or "image/jpeg"
            return Response(
                raw,
                mimetype=mime,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Content-Length": str(len(raw)),
                },
            )
        except Exception:
            abort(500)

    abort(404)


@user_bp.route("/")
@login_required
def home():
    from datetime import datetime
    shop = _user_shop()

    # Machine count (shop-scoped)
    machine_count = 0
    if shop:
        machine_count = Machine.query.filter_by(
            shop_id=shop.id, status=Machine.STATUS_ACTIVE
        ).count()

    # Error count (global)
    error_count = Error.query.filter(
        Error.status != Error.STATUS_ARCHIVED
    ).count()

    # Favorite count (user-scoped)
    favorite_count = 0
    try:
        from ..models import Favorite
        favorite_count = Favorite.query.filter_by(
            user_id=current_user.id
        ).count()
    except Exception:
        favorite_count = 0

    # Greeting — time-based (Myanmar + name)
    hour = datetime.now().hour
    if 5 <= hour < 12:
        greeting_text = "မင်္ဂလာမနက်ခင်း"
    elif 12 <= hour < 17:
        greeting_text = "မင်္ဂလာနေ့လည်"
    elif 17 <= hour < 21:
        greeting_text = "မင်္ဂလာညနေ"
    else:
        greeting_text = "မင်္ဂလာည"

    first_name = (current_user.name or current_user.username or "").split(" ")[0] or "User"
    greeting = f"{greeting_text}, {first_name}"

    return render_template(
        "user/home.html",
        shop=shop,
        machine_count=machine_count,
        error_count=error_count,
        favorite_count=favorite_count,
        greeting=greeting,
    )


# ---------- search ----------

@user_bp.route("/search")
@login_required
def search():
    query = (request.args.get("q") or "").strip()
    search_type = (request.args.get("type") or "all").lower()
    if search_type not in ("all", "machine", "error"):
        search_type = "all"

    machines = []
    errors = []
    related_error_ids = set()

    if query:
        # Log search
        log_activity(
            "SEARCH",
            target_type=search_type,
            target_label=query[:100],
            meta=f"type={search_type}, len={len(query)}",
        )

        like = f"%{query}%"
        words = [w for w in query.split() if len(w) > 0]

        # ----- MACHINES -----
        if search_type in ("all", "machine"):
            mq = Machine.query.join(Shop).filter(
                Machine.status != Machine.STATUS_ARCHIVED,
            )
            # Match: single query OR all words
            from sqlalchemy import or_, and_
            conditions = [
                Machine.machine_code.ilike(like),
                Machine.machine_name.ilike(like),
                Machine.description.ilike(like),
            ]
            for w in words:
                wlike = f"%{w}%"
                conditions.append(or_(
                    Machine.machine_code.ilike(wlike),
                    Machine.machine_name.ilike(wlike),
                    Machine.description.ilike(wlike),
                ))
            mq = mq.filter(or_(*conditions))

            if not current_user.is_admin:
                if current_user.shop_id is None:
                    mq = mq.filter(db.false())
                else:
                    mq = mq.filter(Machine.shop_id == current_user.shop_id)

            machines = mq.order_by(Machine.machine_code).limit(50).all()

            # Collect related errors from machines
            for m in machines:
                for e in m.errors:
                    related_error_ids.add(e.id)


                # Auto-pair via error.machine_name pattern
                import re as _re
                _all_errors = Error.query.filter(
                    Error.status != Error.STATUS_ARCHIVED,
                    Error.machine_name.isnot(None),
                    Error.machine_name != "",
                ).all()
                for m in machines:
                    text = (str(m.machine_code or "") + " " + str(m.machine_name or "")).lower()
                    tokens = [
                        t for t in _re.split(r"[\s_\-./]+", text)
                        if len(t) >= 3
                    ]
                    if not tokens:
                        continue
                    for e in _all_errors:
                        pattern = str(e.machine_name).lower()
                        if any(tok in pattern for tok in tokens):
                            related_error_ids.add(e.id)
        # ----- ERRORS (by keyword) -----
        if search_type in ("all", "error"):
            from sqlalchemy import or_
            eq = Error.query.filter(
                Error.status != Error.STATUS_ARCHIVED,
            )
            conditions = [
                Error.error_code.ilike(like),
                Error.error_name.ilike(like),
                Error.error_fix.ilike(like),
                Error.explanation.ilike(like),
                Error.machine_name.ilike(like),
            ]
            for w in words:
                wlike = f"%{w}%"
                conditions.append(or_(
                    Error.error_code.ilike(wlike),
                    Error.error_name.ilike(wlike),
                    Error.error_fix.ilike(wlike),
                    Error.explanation.ilike(wlike),
                    Error.machine_name.ilike(wlike),
                ))
            eq = eq.filter(or_(*conditions))

            errors = eq.order_by(Error.error_code).limit(50).all()

        # ----- RELATED ERRORS (from machines) -----
        # If machine search found errors, include them too
        if related_error_ids:
            existing_ids = {e.id for e in errors}
            extra_ids = related_error_ids - existing_ids
            if extra_ids:
                extra = Error.query.filter(
                    Error.id.in_(extra_ids),
                    Error.status != Error.STATUS_ARCHIVED,
                ).order_by(Error.error_code).limit(50).all()
                # Related errors go FIRST
                errors = extra + errors

        # Attach photo preview URLs to each error (up to 5 per error)
        for e in errors:
            previews = []
            try:
                imgs = list(e.images or [])
                for img in imgs[:5]:
                    path = getattr(img, "image_path", None) or ""
                    if path:
                        if path.startswith("/"):
                            url = path
                        elif path.startswith("uploads/"):
                            url = "/" + path
                        else:
                            url = "/uploads/" + path
                        previews.append({
                            "id": img.id,
                            "url": url,
                            "caption": getattr(img, "caption", None),
                        })
                e.photo_previews = previews
                e.photo_total = len(imgs)
            except Exception:
                e.photo_previews = []
                e.photo_total = 0

    shop = _user_shop()

    # Attach all_errors to each machine (M2M + auto-paired)
    _all_errors = globals().get('_all_errors') or []
    _err_by_id = {e.id: e for e in errors}
    for m in machines:
        m2m_ids = {e.id for e in m.errors}
        text = (str(m.machine_code or "") + " " + str(m.machine_name or "")).lower()
        tokens = [t for t in _re.split(r"[\s_\-./]+", text) if len(t) >= 3]
        auto_ids = set()
        if tokens:
            for e in _all_errors:
                pattern = str(e.machine_name or "").lower()
                if any(tok in pattern for tok in tokens):
                    auto_ids.add(e.id)
        combined_ids = m2m_ids | auto_ids
        m.all_errors = [
            _err_by_id[eid] for eid in combined_ids if eid in _err_by_id
        ]

    return render_template(
        "user/search.html",
        query=query, search_type=search_type,
        machines=machines, errors=errors, shop=shop,
    )


# ---------- machine detail ----------

@user_bp.route("/machine/<int:machine_id>")
@login_required
def machine_detail(machine_id):
    machine = db.session.get(Machine, machine_id)
    if machine is None:
        abort(404)
    if not _machine_visible_to_user(machine):
        abort(403)

    log_activity(
        "VIEW_MACHINE",
        target_type="machine",
        target_id=machine.id,
        target_label=machine.machine_code,
    )

    shop = _user_shop()
    return render_template("user/machine_detail.html", machine=machine, shop=shop)


# ---------- error detail ----------

@user_bp.route("/error/<int:error_id>")
@login_required
def error_detail(error_id):
    error = db.session.get(Error, error_id)
    if error is None:
        abort(404)

    log_activity(
        "VIEW_ERROR",
        target_type="error",
        target_id=error.id,
        target_label=error.error_code,
    )

    shop = _user_shop()

    if current_user.is_admin:
        visible_machines = list(error.machines)
    else:
        visible_machines = [
            m for m in error.machines
            if m.shop_id == current_user.shop_id
        ]

    hidden_count = len(error.machines) - len(visible_machines)

    return render_template(
        "user/error_detail.html",
        error=error, visible_machines=visible_machines,
        hidden_count=hidden_count, shop=shop,
    )


# ---------- favorites ----------

@user_bp.route("/favorites")
@login_required
def favorites():
    favs = (
        Favorite.query
        .filter_by(user_id=current_user.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )
    machine_favs = [f for f in favs if f.item_type == Favorite.ITEM_MACHINE]
    error_favs = [f for f in favs if f.item_type == Favorite.ITEM_ERROR]
    shop = _user_shop()
    return render_template(
        "user/favorites.html",
        machine_favs=machine_favs, error_favs=error_favs, shop=shop,
    )


@user_bp.route("/recent")
@login_required
def recent():
    shop = _user_shop()
    return render_template("user/recent.html", shop=shop)


@user_bp.route("/history")
@login_required
def history():
    shop = _user_shop()
    repairs_q = RepairHistory.query
    if not current_user.is_admin and current_user.shop_id:
        repairs_q = repairs_q.join(Machine).filter(
            Machine.shop_id == current_user.shop_id
        )
    repairs = repairs_q.order_by(RepairHistory.repaired_at.desc()).limit(30).all()
    return render_template("user/history.html", shop=shop, repairs=repairs)


@user_bp.route("/settings")
@login_required
def settings():
    shop = _user_shop()
    return render_template("user/settings.html", shop=shop)


@user_bp.route("/profile")
@login_required
def profile():
    shop = _user_shop()
    fav_count = Favorite.query.filter_by(user_id=current_user.id).count()
    return render_template("user/profile.html", shop=shop, fav_count=fav_count)


@user_bp.route("/offline")
@login_required
def offline():
    shop = _user_shop()
    machines_total = Machine.query.count()
    errors_total = Error.query.count()
    if not current_user.is_admin and current_user.shop_id:
        machines_total = Machine.query.filter_by(shop_id=current_user.shop_id).count()
    return render_template(
        "user/offline.html",
        shop=shop,
        machines_total=machines_total,
        errors_total=errors_total,
    )


@user_bp.route("/sync")
@login_required
def sync():
    shop = _user_shop()
    return render_template("user/sync.html", shop=shop)


@user_bp.route("/help")
@login_required
def help_center():
    shop = _user_shop()
    return render_template("user/help.html", shop=shop)


@user_bp.route("/docs")
@login_required
def docs():
    shop = _user_shop()
    return render_template("user/docs.html", shop=shop)


@user_bp.route("/about")
@login_required
def about():
    return render_template("user/about.html")
