"""Admin routes — Shop + User management (V1.4, V1.5)."""
from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, jsonify, send_file,
)
from flask_login import login_required, current_user
from sqlalchemy import func

from ..extensions import db
from ..models import Shop, User, Machine, Error, ErrorImage
from ..utils import admin_required
from ..sync import record_change
from .forms import (
    ShopForm, UserCreateForm, UserEditForm, PasswordResetForm,
    MachineForm, ErrorForm, MachineLinkForm, ErrorLinkForm,
    MachineImportUploadForm, ErrorImportUploadForm,
    PhotoUploadForm, PhotoEditForm,
)

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# =========================================================
# DASHBOARD
# =========================================================

@admin_bp.route("/")
@login_required
@admin_required
def dashboard():
    stats = {
        "shops": Shop.query.count(),
        "active_shops": Shop.query.filter_by(status=Shop.STATUS_ACTIVE).count(),
        "users": User.query.count(),
        "active_users": User.query.filter_by(status=User.STATUS_ACTIVE).count(),
        "machines": Machine.query.count(),
    }
    pending_count = User.query.filter_by(status=User.STATUS_PENDING).count()
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        pending_count=pending_count,
    )


# =========================================================
# SHOP MANAGEMENT
# =========================================================

@admin_bp.route("/shops")
@login_required
@admin_required
def shop_list():
    user_counts = dict(
        db.session.query(User.shop_id, func.count(User.id))
        .group_by(User.shop_id).all()
    )
    machine_counts = dict(
        db.session.query(Machine.shop_id, func.count(Machine.id))
        .group_by(Machine.shop_id).all()
    )

    shops = Shop.query.order_by(Shop.shop_code).all()
    rows = [
        {
            "shop": s,
            "user_count": user_counts.get(s.id, 0),
            "machine_count": machine_counts.get(s.id, 0),
        }
        for s in shops
    ]

    return render_template("admin/shops/list.html", rows=rows)


@admin_bp.route("/shops/new", methods=["GET", "POST"])
@login_required
@admin_required
def shop_create():
    form = ShopForm()

    if form.validate_on_submit():
        code = form.shop_code.data.strip().upper()
        existing = Shop.query.filter_by(shop_code=code).first()
        if existing:
            flash(f"Shop code '{code}' already exists.", "error")
            return render_template("admin/shops/form.html",
                                   form=form, mode="create"), 400

        shop = Shop(
            shop_code=code,
            shop_name=form.shop_name.data.strip(),
            status=form.status.data,
        )
        db.session.add(shop)
        db.session.commit()
        record_change("shops", shop.id, "CREATE")
        db.session.commit()

        flash(f"Shop '{code}' created.", "success")
        return redirect(url_for("admin.shop_list"))

    return render_template("admin/shops/form.html", form=form, mode="create")


@admin_bp.route("/shops/<int:shop_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def shop_edit(shop_id: int):
    shop = db.session.get(Shop, shop_id)
    if shop is None:
        flash("Shop not found.", "error")
        return redirect(url_for("admin.shop_list"))

    form = ShopForm(obj=shop)

    if form.validate_on_submit():
        new_code = form.shop_code.data.strip().upper()

        existing = Shop.query.filter(
            Shop.shop_code == new_code, Shop.id != shop.id
        ).first()
        if existing:
            flash(f"Shop code '{new_code}' already exists.", "error")
            return render_template("admin/shops/form.html",
                                   form=form, mode="edit", shop=shop), 400

        shop.shop_code = new_code
        shop.shop_name = form.shop_name.data.strip()
        shop.status = form.status.data
        db.session.commit()
        record_change("shops", shop.id, "UPDATE")
        db.session.commit()

        flash(f"Shop '{shop.shop_code}' updated.", "success")
        return redirect(url_for("admin.shop_list"))

    return render_template("admin/shops/form.html",
                           form=form, mode="edit", shop=shop)


@admin_bp.route("/shops/<int:shop_id>/status/<string:new_status>", methods=["POST"])
@login_required
@admin_required
def shop_set_status(shop_id: int, new_status: str):
    shop = db.session.get(Shop, shop_id)
    if shop is None:
        flash("Shop not found.", "error")
        return redirect(url_for("admin.shop_list"))

    if new_status not in Shop.ALL_STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("admin.shop_list"))

    shop.status = new_status
    db.session.commit()
    flash(f"Shop '{shop.shop_code}' set to {new_status}.", "success")
    return redirect(url_for("admin.shop_list"))


# =========================================================
# USER MANAGEMENT (V1.5)
# =========================================================

def _populate_shop_choices(form):
    """Fill a SelectField with shops. Adds '(none)' with value 0."""
    shops = Shop.query.filter(
        Shop.status != Shop.STATUS_ARCHIVED
    ).order_by(Shop.shop_code).all()
    form.shop_id.choices = [(0, "— No shop —")] + [
        (s.id, f"{s.shop_code} — {s.shop_name}") for s in shops
    ]


@admin_bp.route("/users")
@login_required
@admin_required
def user_list():
    """List users with optional filters."""
    q = User.query

    # Filters
    shop_filter = request.args.get("shop_id", type=int)
    role_filter = request.args.get("role", type=str)
    status_filter = request.args.get("status", type=str)

    if shop_filter is not None and shop_filter > 0:
        q = q.filter(User.shop_id == shop_filter)

    if role_filter in User.ALL_ROLES:
        q = q.filter(User.role == role_filter)

    if status_filter in User.ALL_STATUSES:
        q = q.filter(User.status == status_filter)

    users = q.order_by(User.username).all()
    shops = Shop.query.order_by(Shop.shop_code).all()

    return render_template(
        "admin/users/list.html",
        users=users,
        shops=shops,
        filters={
            "shop_id": shop_filter or 0,
            "role": role_filter or "",
            "status": status_filter or "",
        },
    )


@admin_bp.route("/users/new", methods=["GET", "POST"])
@login_required
@admin_required
def user_create():
    form = UserCreateForm()
    _populate_shop_choices(form)

    if form.validate_on_submit():
        username = form.username.data.strip().lower()

        existing = User.query.filter_by(username=username).first()
        if existing:
            flash(f"Username '{username}' already taken.", "error")
            return render_template("admin/users/form.html",
                                   form=form, mode="create"), 400

        # Validate: USER role must have a shop
        shop_id = form.shop_id.data if form.shop_id.data != 0 else None
        if form.role.data == User.ROLE_USER and shop_id is None:
            flash("A USER must be assigned to a shop.", "error")
            return render_template("admin/users/form.html",
                                   form=form, mode="create"), 400

        # Validate shop exists if provided
        if shop_id is not None:
            shop = db.session.get(Shop, shop_id)
            if shop is None:
                flash("Invalid shop selected.", "error")
                return render_template("admin/users/form.html",
                                       form=form, mode="create"), 400

        user = User(
            name=form.name.data.strip(),
            username=username,
            role=form.role.data,
            shop_id=shop_id,
            status=form.status.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash(f"User '{username}' created.", "success")
        return redirect(url_for("admin.user_list"))

    return render_template("admin/users/form.html",
                           form=form, mode="create")


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def user_edit(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("admin.user_list"))

    form = UserEditForm(obj=user)
    _populate_shop_choices(form)

    if request.method == "GET":
        form.shop_id.data = user.shop_id or 0

    if form.validate_on_submit():
        new_username = form.username.data.strip().lower()

        # Username uniqueness (excluding self)
        existing = User.query.filter(
            User.username == new_username, User.id != user.id
        ).first()
        if existing:
            flash(f"Username '{new_username}' already taken.", "error")
            return render_template("admin/users/form.html",
                                   form=form, mode="edit", user=user), 400

        shop_id = form.shop_id.data if form.shop_id.data != 0 else None

        # USER role must have shop
        if form.role.data == User.ROLE_USER and shop_id is None:
            flash("A USER must be assigned to a shop.", "error")
            return render_template("admin/users/form.html",
                                   form=form, mode="edit", user=user), 400

        # Validate shop
        if shop_id is not None:
            shop = db.session.get(Shop, shop_id)
            if shop is None:
                flash("Invalid shop selected.", "error")
                return render_template("admin/users/form.html",
                                       form=form, mode="edit", user=user), 400

        # Prevent deactivating yourself
        from flask_login import current_user
        if user.id == current_user.id and form.status.data != User.STATUS_ACTIVE:
            flash("You cannot deactivate yourself.", "error")
            return render_template("admin/users/form.html",
                                   form=form, mode="edit", user=user), 400

        # Prevent removing your own admin role
        if user.id == current_user.id and form.role.data != User.ROLE_ADMIN:
            flash("You cannot remove your own admin role.", "error")
            return render_template("admin/users/form.html",
                                   form=form, mode="edit", user=user), 400

        user.name = form.name.data.strip()
        user.username = new_username
        user.role = form.role.data
        user.shop_id = shop_id
        user.status = form.status.data
        db.session.commit()

        flash(f"User '{user.username}' updated.", "success")
        return redirect(url_for("admin.user_list"))

    return render_template("admin/users/form.html",
                           form=form, mode="edit", user=user)


@admin_bp.route("/users/<int:user_id>/password", methods=["GET", "POST"])
@login_required
@admin_required
def user_password(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("admin.user_list"))

    form = PasswordResetForm()
    form.user_id.data = user.id

    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        db.session.commit()
        flash(f"Password reset for '{user.username}'.", "success")
        return redirect(url_for("admin.user_list"))

    return render_template("admin/users/password.html",
                           form=form, user=user)


@admin_bp.route("/users/<int:user_id>/toggle-status", methods=["POST"])
@login_required
@admin_required
def user_toggle_status(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("admin.user_list"))

    from flask_login import current_user
    if user.id == current_user.id:
        flash("You cannot change your own status.", "error")
        return redirect(url_for("admin.user_list"))

    if user.status == User.STATUS_ACTIVE:
        user.status = User.STATUS_INACTIVE
        flash(f"User '{user.username}' deactivated.", "success")
    else:
        user.status = User.STATUS_ACTIVE
        flash(f"User '{user.username}' activated.", "success")

    db.session.commit()
    return redirect(url_for("admin.user_list"))


# =========================================================
# MACHINE MANAGEMENT (V1.6)
# =========================================================

def _populate_machine_shop_choices(form, include_archived: bool = False):
    """Fill MachineForm.shop_id choices with non-archived shops by default."""
    q = Shop.query
    if not include_archived:
        q = q.filter(Shop.status != Shop.STATUS_ARCHIVED)
    shops = q.order_by(Shop.shop_code).all()
    form.shop_id.choices = [
        (s.id, f"{s.shop_code} — {s.shop_name}") for s in shops
    ]


@admin_bp.route("/machines")
@login_required
@admin_required
def machine_list():
    """List machines with optional filters + pagination."""
    q = Machine.query.join(Shop)

    shop_filter = request.args.get("shop_id", type=int)
    status_filter = request.args.get("status", type=str)
    search = (request.args.get("q", type=str) or "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 50

    if shop_filter is not None and shop_filter > 0:
        q = q.filter(Machine.shop_id == shop_filter)

    if status_filter in Machine.ALL_STATUSES:
        q = q.filter(Machine.status == status_filter)

    if search:
        like = f"%{search}%"
        q = q.filter(
            db.or_(
                Machine.machine_name.ilike(like),
                Machine.machine_code.ilike(like),
            )
        )

    sort = request.args.get("sort", "code")
    if sort == "name":
        q = q.order_by(Machine.machine_name)
    elif sort == "date":
        q = q.order_by(Machine.created_at.desc())
    elif sort == "code":
        q = q.order_by(Shop.shop_code, Machine.machine_code)
    else:
        q = q.order_by(Shop.shop_code, Machine.machine_code)

    total = q.count()
    machines = (
        q.limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )

    total_pages = (total + per_page - 1) // per_page
    shops = Shop.query.order_by(Shop.shop_code).all()

    return render_template(
        "admin/machines/list.html",
        machines=machines,
        shops=shops,
        page=page,
        total=total,
        total_pages=total_pages,
        per_page=per_page,
        filters={
            "shop_id": shop_filter or 0,
            "status": status_filter or "",
            "q": search,
            "sort": sort,
        },
    )


@admin_bp.route("/machines/new", methods=["GET", "POST"])
@login_required
@admin_required
def machine_create():
    form = MachineForm()
    _populate_machine_shop_choices(form)

    if form.validate_on_submit():
        shop = db.session.get(Shop, form.shop_id.data)
        if shop is None:
            flash("Invalid shop selected.", "error")
            return render_template("admin/machines/form.html",
                                   form=form, mode="create"), 400

        code = form.machine_code.data.strip().upper()

        # Uniqueness within shop
        existing = Machine.query.filter_by(
            shop_id=shop.id, machine_code=code
        ).first()
        if existing:
            flash(
                f"Machine code '{code}' already exists in shop "
                f"'{shop.shop_code}'.",
                "error",
            )
            return render_template("admin/machines/form.html",
                                   form=form, mode="create"), 400

        machine = Machine(
            shop_id=shop.id,
            machine_name=form.machine_name.data.strip(),
            machine_code=code,
            description=(form.description.data or "").strip() or None,
            status=form.status.data,
        )
        db.session.add(machine)
        db.session.commit()
        record_change("machines", machine.id, "CREATE")
        db.session.commit()

        flash(
            f"Machine '{code}' created in shop '{shop.shop_code}'.",
            "success",
        )
        return redirect(url_for("admin.machine_list"))

    return render_template("admin/machines/form.html",
                           form=form, mode="create")


@admin_bp.route("/machines/<int:machine_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def machine_edit(machine_id: int):
    machine = db.session.get(Machine, machine_id)
    if machine is None:
        flash("Machine not found.", "error")
        return redirect(url_for("admin.machine_list"))

    form = MachineForm(obj=machine)
    _populate_machine_shop_choices(form, include_archived=True)

    if request.method == "GET":
        form.shop_id.data = machine.shop_id

    if form.validate_on_submit():
        shop = db.session.get(Shop, form.shop_id.data)
        if shop is None:
            flash("Invalid shop selected.", "error")
            return render_template("admin/machines/form.html",
                                   form=form, mode="edit",
                                   machine=machine), 400

        new_code = form.machine_code.data.strip().upper()

        # Uniqueness within shop (excluding self)
        existing = Machine.query.filter(
            Machine.shop_id == shop.id,
            Machine.machine_code == new_code,
            Machine.id != machine.id,
        ).first()
        if existing:
            flash(
                f"Machine code '{new_code}' already exists in shop "
                f"'{shop.shop_code}'.",
                "error",
            )
            return render_template("admin/machines/form.html",
                                   form=form, mode="edit",
                                   machine=machine), 400

        machine.shop_id = shop.id
        machine.machine_name = form.machine_name.data.strip()
        machine.machine_code = new_code
        machine.description = (form.description.data or "").strip() or None
        machine.status = form.status.data
        db.session.commit()
        record_change("machines", machine.id, "UPDATE")
        db.session.commit()

        flash(f"Machine '{new_code}' updated.", "success")
        return redirect(url_for("admin.machine_list"))

    return render_template("admin/machines/form.html",
                           form=form, mode="edit", machine=machine)


@admin_bp.route("/machines/<int:machine_id>/status/<string:new_status>",
                methods=["POST"])
@login_required
@admin_required
def machine_set_status(machine_id: int, new_status: str):
    machine = db.session.get(Machine, machine_id)
    if machine is None:
        flash("Machine not found.", "error")
        return redirect(url_for("admin.machine_list"))

    if new_status not in Machine.ALL_STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("admin.machine_list"))

    machine.status = new_status
    db.session.commit()
    flash(
        f"Machine '{machine.machine_code}' set to {new_status}.",
        "success",
    )
    return redirect(url_for("admin.machine_list"))


# =========================================================
# ERROR MANAGEMENT (V1.7)
# =========================================================

@admin_bp.route("/errors")
@login_required
@admin_required
def error_list():
    """List global errors with filters."""
    q = Error.query

    status_filter = request.args.get("status", type=str)
    search = (request.args.get("q", type=str) or "").strip()

    if status_filter in Error.ALL_STATUSES:
        q = q.filter(Error.status == status_filter)

    if search:
        like = f"%{search}%"
        q = q.filter(
            db.or_(
                Error.error_code.ilike(like),
                Error.error_name.ilike(like),
            )
        )

    errors = q.order_by(Error.error_code).all()

    return render_template(
        "admin/errors/list.html",
        errors=errors,
        filters={"status": status_filter or "", "q": search},
    )


@admin_bp.route("/errors/new", methods=["GET", "POST"])
@login_required
@admin_required
def error_create():
    form = ErrorForm()

    # Load active machines for picker UI
    machines = (
        Machine.query.join(Shop)
        .filter(Machine.status == Machine.STATUS_ACTIVE)
        .order_by(Shop.shop_code, Machine.machine_code)
        .all()
    )

    if form.validate_on_submit():
        # Normalize: uppercase, trim, collapse multiple spaces
        import re as _re
        raw = form.error_code.data.strip().upper()
        code = _re.sub(r"\s+", " ", raw)  # collapse spaces
        code = code.strip()

        existing = Error.query.filter_by(error_code=code).first()
        if existing:
            flash(f"Error code '{code}' already exists.", "error")
            return render_template("admin/errors/form.html",
                                   form=form, mode="create",
                                   machines=machines)

        error = Error(
            error_code=code,
            error_name=form.error_name.data.strip(),
            error_fix=(form.error_fix.data or "").strip() or None,
            explanation=(form.explanation.data or "").strip() or None,
            machine_name=(form.machine_name.data or "").strip() or None,
            status=form.status.data,
        )
        db.session.add(error)
        db.session.commit()

        # Link machines from request.form
        machine_ids = []
        for v in request.form.getlist("machines"):
            try:
                machine_ids.append(int(v))
            except (ValueError, TypeError):
                pass

        if machine_ids:
            selected = Machine.query.filter(Machine.id.in_(machine_ids)).all()
            for m in selected:
                if m not in error.machines:
                    error.machines.append(m)
            db.session.commit()

        # Upload photos (max 10)
        photos = (form.photos.data or [])[:10]
        if len(form.photos.data or []) > 10:
            flash("Max 10 photos per upload — first 10 saved.", "warning")
        caption = (form.photo_caption.data or "").strip() or None
        saved = 0
        next_order = 0
        for f in photos:
            if not f or not f.filename:
                continue
            if not allowed_image(f.filename):
                continue
            meta = save_error_image(f, _upload_root(), error.error_code)
            if not meta:
                continue
            img = ErrorImage(
                error_id=error.id,
                image_path=meta["image_path"],
                caption=caption,
                sort_order=next_order,
                file_size=meta["file_size"],
                width=meta["width"],
                height=meta["height"],
            )
            db.session.add(img)
            next_order += 1
            saved += 1
        db.session.commit()

        record_change("errors", error.id, "CREATE")
        db.session.commit()

        msg = f"Error '{code}' created."
        if machine_ids:
            msg += f" Linked {len(machine_ids)} machine(s)."
        if saved:
            msg += f" Uploaded {saved} photo(s)."
        flash(msg, "success")
        return redirect(url_for("admin.error_list"))

    return render_template("admin/errors/form.html",
                           form=form, mode="create",
                           machines=machines)
@admin_bp.route("/errors/<int:error_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def error_edit(error_id: int):
    error = db.session.get(Error, error_id)
    if error is None:
        flash("Error not found.", "error")
        return redirect(url_for("admin.error_list"))

    form = ErrorForm(obj=error)

    # Load active machines for picker UI
    machines = (
        Machine.query.join(Shop)
        .filter(Machine.status == Machine.STATUS_ACTIVE)
        .order_by(Shop.shop_code, Machine.machine_code)
        .all()
    )

    if form.validate_on_submit():
        new_code = form.error_code.data.strip().upper()

        existing = Error.query.filter(
            Error.error_code == new_code, Error.id != error.id
        ).first()
        if existing:
            flash(f"Error code '{new_code}' already exists.", "error")
            return render_template("admin/errors/form.html",
                                   form=form, mode="edit",
                                   error=error, machines=machines)

        error.error_code = new_code
        error.error_name = form.error_name.data.strip()
        error.error_fix = (form.error_fix.data or "").strip() or None
        error.explanation = (form.explanation.data or "").strip() or None
        error.machine_name = (form.machine_name.data or "").strip() or None
        error.category = form.category.data or "ERROR"
        error.status = form.status.data

        # Machine links
        machine_ids = set()
        for v in request.form.getlist("machines"):
            try:
                machine_ids.add(int(v))
            except (ValueError, TypeError):
                pass
        current_ids = {m.id for m in error.machines}

        to_add = machine_ids - current_ids
        if to_add:
            new_machines = Machine.query.filter(Machine.id.in_(to_add)).all()
            for m in new_machines:
                error.machines.append(m)

        to_remove = current_ids - machine_ids
        if to_remove:
            error.machines = [m for m in error.machines if m.id not in to_remove]

        # Photos
        photos = (form.photos.data or [])[:10]
        if len(form.photos.data or []) > 10:
            flash("Max 10 photos per upload — first 10 saved.", "warning")
        caption = (form.photo_caption.data or "").strip() or None
        saved = 0
        next_order = max([img.sort_order for img in error.images], default=-1) + 1
        for f in photos:
            if not f or not f.filename:
                continue
            if not allowed_image(f.filename):
                continue
            meta = save_error_image(f, _upload_root(), error.error_code)
            if not meta:
                continue
            img = ErrorImage(
                error_id=error.id,
                image_path=meta["image_path"],
                caption=caption,
                sort_order=next_order,
                file_size=meta["file_size"],
                width=meta["width"],
                height=meta["height"],
            )
            db.session.add(img)
            next_order += 1
            saved += 1

        db.session.commit()
        record_change("errors", error.id, "UPDATE")
        db.session.commit()

        msg = f"Error '{new_code}' updated."
        if saved:
            msg += f" Added {saved} photo(s)."
        flash(msg, "success")
        return redirect(url_for("admin.error_list"))

    return render_template("admin/errors/form.html",
                           form=form, mode="edit", error=error,
                           machines=machines)


@admin_bp.route("/errors/<int:error_id>/status/<string:new_status>",
                methods=["POST"])
@login_required
@admin_required
def error_set_status(error_id: int, new_status: str):
    error = db.session.get(Error, error_id)
    if error is None:
        flash("Error not found.", "error")
        return redirect(url_for("admin.error_list"))

    if new_status not in Error.ALL_STATUSES:
        flash("Invalid status.", "error")
        return redirect(url_for("admin.error_list"))

    error.status = new_status
    db.session.commit()
    flash(f"Error '{error.error_code}' set to {new_status}.", "success")
    return redirect(url_for("admin.error_list"))


# ---------- Machine ↔ Error linking ----------

@admin_bp.route("/errors/<int:error_id>/machines", methods=["GET", "POST"])
@login_required
@admin_required
def error_machines(error_id: int):
    """Manage machines linked to an error."""
    error = db.session.get(Error, error_id)
    if error is None:
        flash("Error not found.", "error")
        return redirect(url_for("admin.error_list"))

    form = MachineLinkForm()

    # Available machines not yet linked
    linked_ids = [m.id for m in error.machines]
    available = Machine.query.filter(
        Machine.status == Machine.STATUS_ACTIVE,
        ~Machine.id.in_(linked_ids) if linked_ids else True,
    ).join(Shop).order_by(Shop.shop_code, Machine.machine_code).all()

    form.machine_id.choices = [
        (m.id, f"{m.shop.shop_code} — {m.machine_code} — {m.machine_name}")
        for m in available
    ]

    if form.validate_on_submit():
        machine = db.session.get(Machine, form.machine_id.data)
        if machine is None:
            flash("Machine not found.", "error")
            return redirect(url_for("admin.error_machines", error_id=error.id))

        if machine not in error.machines:
            error.machines.append(machine)
            db.session.commit()
            flash(f"Linked '{machine.machine_code}' to '{error.error_code}'.",
                  "success")
        else:
            flash("Machine already linked.", "info")

        return redirect(url_for("admin.error_machines", error_id=error.id))

    return render_template("admin/errors/link.html",
                           error=error, form=form)


@admin_bp.route("/errors/<int:error_id>/machines/<int:machine_id>/unlink",
                methods=["POST"])
@login_required
@admin_required
def error_unlink_machine(error_id: int, machine_id: int):
    error = db.session.get(Error, error_id)
    machine = db.session.get(Machine, machine_id)
    if error is None or machine is None:
        flash("Not found.", "error")
        return redirect(url_for("admin.error_list"))

    if machine in error.machines:
        error.machines.remove(machine)
        db.session.commit()
        flash(f"Unlinked '{machine.machine_code}' from '{error.error_code}'.",
              "success")

    return redirect(url_for("admin.error_machines", error_id=error.id))


# ---------- Machine side: manage errors for a machine ----------

@admin_bp.route("/machines/<int:machine_id>/errors", methods=["GET", "POST"])
@login_required
@admin_required
def machine_errors(machine_id: int):
    """Manage errors linked to a machine."""
    machine = db.session.get(Machine, machine_id)
    if machine is None:
        flash("Machine not found.", "error")
        return redirect(url_for("admin.machine_list"))

    form = ErrorLinkForm()

    linked_ids = [e.id for e in machine.errors]
    available = Error.query.filter(
        Error.status == Error.STATUS_ACTIVE,
        ~Error.id.in_(linked_ids) if linked_ids else True,
    ).order_by(Error.error_code).all()

    form.error_id.choices = [
        (e.id, f"{e.error_code} — {e.error_name}") for e in available
    ]

    if form.validate_on_submit():
        error = db.session.get(Error, form.error_id.data)
        if error is None:
            flash("Error not found.", "error")
            return redirect(url_for("admin.machine_errors",
                                    machine_id=machine.id))

        if error not in machine.errors:
            machine.errors.append(error)
            db.session.commit()
            flash(f"Linked '{error.error_code}' to '{machine.machine_code}'.",
                  "success")
        else:
            flash("Error already linked.", "info")

        return redirect(url_for("admin.machine_errors", machine_id=machine.id))

    return render_template("admin/machines/link_errors.html",
                           machine=machine, form=form)


@admin_bp.route("/machines/<int:machine_id>/errors/<int:error_id>/unlink",
                methods=["POST"])
@login_required
@admin_required
def machine_unlink_error(machine_id: int, error_id: int):
    machine = db.session.get(Machine, machine_id)
    error = db.session.get(Error, error_id)
    if machine is None or error is None:
        flash("Not found.", "error")
        return redirect(url_for("admin.machine_list"))

    if error in machine.errors:
        machine.errors.remove(error)
        db.session.commit()
        flash(f"Unlinked '{error.error_code}' from '{machine.machine_code}'.",
              "success")

    return redirect(url_for("admin.machine_errors", machine_id=machine.id))


# =========================================================
# ADMIN SEARCH (V1.8)
# =========================================================

@admin_bp.route("/search")
@login_required
@admin_required
def admin_search():
    """Admin search UI — machines + errors."""
    query = (request.args.get("q") or "").strip()
    search_type = (request.args.get("type") or "all").lower()
    if search_type not in ("all", "machine", "error"):
        search_type = "all"

    machines = []
    errors = []

    if query:
        like = f"%{query}%"
        if search_type in ("all", "machine"):
            machines = (
                Machine.query.join(Shop)
                .filter(
                    db.or_(
                        Machine.machine_code.ilike(like),
                        Machine.machine_name.ilike(like),
                    )
                )
                .order_by(Shop.shop_code, Machine.machine_code)
                .limit(50)
                .all()
            )
        if search_type in ("all", "error"):
            errors = (
                Error.query.filter(
                    db.or_(
                        Error.error_code.ilike(like),
                        Error.error_name.ilike(like),
                    )
                )
                .order_by(Error.error_code)
                .limit(50)
                .all()
            )

    return render_template(
        "admin/search.html",
        query=query,
        search_type=search_type,
        machines=machines,
        errors=errors,
    )


# =========================================================
# EXCEL IMPORT (V1.8)
# =========================================================

from io import BytesIO as _BytesIO


def _allowed_excel(filename: str) -> bool:
    if not filename:
        return False
    return filename.lower().endswith(".xlsx")


@admin_bp.route("/import/machines", methods=["GET", "POST"])
@login_required
@admin_required
def import_machines_upload():
    """Step 1 — upload machine Excel + select shop. Show preview."""
    from .excel import parse_machines_excel

    form = MachineImportUploadForm()
    _populate_machine_shop_choices(form)

    if form.validate_on_submit():
        f = form.excel_file.data
        if not _allowed_excel(f.filename):
            flash("Only .xlsx files are allowed.", "error")
            return render_template("admin/import/machines_upload.html",
                                   form=form), 400

        content = f.read()
        if len(content) > 5 * 1024 * 1024:
            flash("File too large (max 5 MB).", "error")
            return render_template("admin/import/machines_upload.html",
                                   form=form), 400

        parsed = parse_machines_excel(content)

        if parsed.header_errors:
            for e in parsed.header_errors:
                flash(e, "error")
            return render_template("admin/import/machines_upload.html",
                                   form=form), 400

        # Compute preview counts (against existing DB)
        shop = db.session.get(Shop, form.shop_id.data)
        existing_codes = {
            m.machine_code
            for m in Machine.query.filter_by(shop_id=shop.id).all()
        }

        new_rows = []
        update_rows = []
        for r in parsed.valid:
            code = r.data["machine_code"]
            if code in existing_codes:
                update_rows.append(r)
            else:
                new_rows.append(r)

        return render_template(
            "admin/import/machines_preview.html",
            form=form,
            shop=shop,
            parsed=parsed,
            new_rows=new_rows,
            update_rows=update_rows,
            invalid_rows=parsed.invalid,
        )

    return render_template("admin/import/machines_upload.html", form=form)


@admin_bp.route("/import/machines/confirm", methods=["POST"])
@login_required
@admin_required
def import_machines_confirm():
    """Step 2 — actually import. Re-parses from re-uploaded file.

    We re-upload the file on confirm (simpler + safer than session storage).
    """
    from .excel import parse_machines_excel

    form = MachineImportUploadForm()
    _populate_machine_shop_choices(form)

    if not form.validate_on_submit():
        flash("Upload form invalid. Please retry.", "error")
        return redirect(url_for("admin.import_machines_upload"))

    f = form.excel_file.data
    if not _allowed_excel(f.filename):
        flash("Only .xlsx files are allowed.", "error")
        return redirect(url_for("admin.import_machines_upload"))

    shop = db.session.get(Shop, form.shop_id.data)
    if shop is None:
        flash("Invalid shop.", "error")
        return redirect(url_for("admin.import_machines_upload"))

    content = f.read()
    parsed = parse_machines_excel(content)
    if parsed.header_errors:
        for e in parsed.header_errors:
            flash(e, "error")
        return redirect(url_for("admin.import_machines_upload"))

    created = 0
    updated = 0
    skipped_existing = 0
    skipped_invalid = len(parsed.invalid)

    import_mode = request.form.get("import_mode", "update")

    # Create import batch (V5.4)
    from ..models import ImportBatch
    batch = ImportBatch(
        shop_id=shop.id,
        filename=request.form.get("filename", "import.xlsx"),
        machine_count=0,
        created_by=current_user.id if current_user.is_authenticated else None,
    )
    db.session.add(batch)
    db.session.flush()  # get batch.id

    for r in parsed.valid:
        code = r.data["machine_code"]
        existing = Machine.query.filter_by(
            shop_id=shop.id, machine_code=code
        ).first()

        if existing:
            if import_mode == "skip":
                skipped_existing += 1
                continue
            elif import_mode == "error":
                flash(f"Machine code '{code}' already exists — import aborted.", "error")
                return redirect(url_for("admin.import_machines_upload"))

            # Smart update — only overwrite non-empty values
            if r.data.get("machine_name"):
                existing.machine_name = r.data["machine_name"]
            if r.data.get("description"):
                existing.description = r.data["description"]
            if r.data.get("status"):
                existing.status = r.data["status"]
            existing.data_version = (existing.data_version or 0) + 1
            updated += 1
        else:
            m = Machine(
                shop_id=shop.id,
                machine_code=code,
                machine_name=r.data["machine_name"],
                description=r.data.get("description"),
                status=r.data.get("status") or "ACTIVE",
                batch_id=batch.id,  # link to batch
            )
            db.session.add(m)
            created += 1

    batch.machine_count = created + updated
    db.session.commit()

    msg = (
        f"Import complete for shop '{shop.shop_code}': "
        f"{created} created, {updated} updated"
    )
    if skipped_existing:
        msg += f", {skipped_existing} skipped (already existed)"
    if skipped_invalid:
        msg += f", {skipped_invalid} skipped (invalid)"
    msg += "."
    flash(msg, "success")
    return redirect(url_for("admin.machine_list"))


@admin_bp.route("/import/errors", methods=["GET", "POST"])
@login_required
@admin_required
def import_errors_upload():
    """Step 1 — upload error Excel. Show preview."""
    from .excel import parse_errors_excel

    form = ErrorImportUploadForm()

    if form.validate_on_submit():
        f = form.excel_file.data
        if not _allowed_excel(f.filename):
            flash("Only .xlsx files are allowed.", "error")
            return render_template("admin/import/errors_upload.html",
                                   form=form), 400

        content = f.read()
        if len(content) > 5 * 1024 * 1024:
            flash("File too large (max 5 MB).", "error")
            return render_template("admin/import/errors_upload.html",
                                   form=form), 400

        parsed = parse_errors_excel(content)

        if parsed.header_errors:
            for e in parsed.header_errors:
                flash(e, "error")
            return render_template("admin/import/errors_upload.html",
                                   form=form), 400

        existing_codes = {e.error_code for e in Error.query.all()}

        new_rows = []
        update_rows = []
        for r in parsed.valid:
            code = r.data["error_code"]
            if code in existing_codes:
                update_rows.append(r)
            else:
                new_rows.append(r)

        return render_template(
            "admin/import/errors_preview.html",
            form=form,
            parsed=parsed,
            new_rows=new_rows,
            update_rows=update_rows,
            invalid_rows=parsed.invalid,
        )

    return render_template("admin/import/errors_upload.html", form=form)


@admin_bp.route("/import/errors/confirm", methods=["POST"])
@login_required
@admin_required
def import_errors_confirm():
    """Step 2 — actually import errors."""
    from .excel import parse_errors_excel

    form = ErrorImportUploadForm()

    if not form.validate_on_submit():
        flash("Upload form invalid. Please retry.", "error")
        return redirect(url_for("admin.import_errors_upload"))

    f = form.excel_file.data
    if not _allowed_excel(f.filename):
        flash("Only .xlsx files are allowed.", "error")
        return redirect(url_for("admin.import_errors_upload"))

    content = f.read()
    parsed = parse_errors_excel(content)
    if parsed.header_errors:
        for e in parsed.header_errors:
            flash(e, "error")
        return redirect(url_for("admin.import_errors_upload"))

    created = 0
    updated = 0
    skipped_existing = 0
    skipped_invalid = len(parsed.invalid)

    import_mode = request.form.get("import_mode", "update")

    for r in parsed.valid:
        code = r.data["error_code"]
        existing = Error.query.filter_by(error_code=code).first()

        if existing:
            if import_mode == "skip":
                skipped_existing += 1
                continue
            elif import_mode == "error":
                flash(f"Error code '{code}' already exists — import aborted.", "error")
                return redirect(url_for("admin.import_errors_upload"))

            # Smart update — only overwrite non-empty
            if r.data.get("error_name"):
                existing.error_name = r.data["error_name"]
            if r.data.get("error_fix"):
                existing.error_fix = r.data["error_fix"]
            if r.data.get("explanation"):
                existing.explanation = r.data["explanation"]
            if r.data.get("machine_name"):
                existing.machine_name = r.data["machine_name"]
            if r.data.get("status"):
                existing.status = r.data["status"]
            if r.data.get("category"):
                existing.category = r.data["category"]
            existing.data_version = (existing.data_version or 0) + 1
            updated += 1
        else:
            e = Error(
                error_code=code,
                error_name=r.data["error_name"],
                error_fix=r.data.get("error_fix"),
                explanation=r.data.get("explanation"),
                machine_name=r.data.get("machine_name"),
                status=r.data.get("status") or "ACTIVE",
                category=r.data.get("category") or "ERROR",
            )
            db.session.add(e)
            created += 1

    db.session.commit()

    msg = f"Import complete: {created} created, {updated} updated"
    if skipped_existing:
        msg += f", {skipped_existing} skipped (already existed)"
    if skipped_invalid:
        msg += f", {skipped_invalid} skipped (invalid)"
    msg += "."
    flash(msg, "success")
    return redirect(url_for("admin.error_list"))


# =========================================================
# ERROR PHOTOS (V2)
# =========================================================

from flask import current_app, send_from_directory
from werkzeug.utils import secure_filename
from .images import save_error_image, delete_error_image, allowed_image
from .forms import PhotoUploadForm, PhotoEditForm


def _upload_root() -> str:
    return current_app.config["UPLOAD_FOLDER"]


@admin_bp.route("/uploads/<path:rel_path>")
@login_required
def serve_upload(rel_path: str):
    """Serve uploaded files (admin only via this route)."""
    return send_from_directory(_upload_root(), rel_path)


@admin_bp.route("/errors/<int:error_id>/photos", methods=["GET", "POST"])
@login_required
@admin_required
def error_photos(error_id: int):
    """Manage photos for an error."""
    error = db.session.get(Error, error_id)
    if error is None:
        flash("Error not found.", "error")
        return redirect(url_for("admin.error_list"))

    form = PhotoUploadForm()

    if form.validate_on_submit():
        files = form.images.data or []
        caption = (form.caption.data or "").strip() or None

        saved = 0
        failed = 0

        # Determine next sort_order
        next_order = max([img.sort_order for img in error.images], default=-1) + 1

        for f in files:
            if not f or not f.filename:
                continue
            if not allowed_image(f.filename):
                failed += 1
                continue

            meta = save_error_image(f, _upload_root(), error.error_code)
            if not meta:
                failed += 1
                continue

            img = ErrorImage(
                error_id=error.id,
                image_path=meta["image_path"],
                caption=caption,
                sort_order=next_order,
                file_size=meta["file_size"],
                width=meta["width"],
                height=meta["height"],
            )
            db.session.add(img)
            next_order += 1
            saved += 1

        db.session.commit()
        for img in error.images:
            record_change("error_images", img.id, "CREATE")
        db.session.commit()

        if saved:
            flash(f"Uploaded {saved} photo(s).", "success")
        if failed:
            flash(f"{failed} file(s) skipped (unsupported or invalid).", "warning")

        return redirect(url_for("admin.error_photos", error_id=error.id))

    return render_template("admin/errors/photos.html", error=error, form=form)


@admin_bp.route("/errors/<int:error_id>/photos/<int:image_id>/edit",
                methods=["GET", "POST"])
@login_required
@admin_required
def error_photo_edit(error_id: int, image_id: int):
    """Edit caption + sort order of a photo."""
    error = db.session.get(Error, error_id)
    image = db.session.get(ErrorImage, image_id)
    if error is None or image is None or image.error_id != error.id:
        flash("Photo not found.", "error")
        return redirect(url_for("admin.error_list"))

    form = PhotoEditForm(obj=image)

    if form.validate_on_submit():
        image.caption = (form.caption.data or "").strip() or None
        image.sort_order = form.sort_order.data or 0
        db.session.commit()
        flash("Photo updated.", "success")
        return redirect(url_for("admin.error_photos", error_id=error.id))

    return render_template("admin/errors/photo_edit.html",
                           error=error, image=image, form=form)


@admin_bp.route("/errors/<int:error_id>/photos/<int:image_id>/delete",
                methods=["POST"])
@login_required
@admin_required
def error_photo_delete(error_id: int, image_id: int):
    """Delete a photo (removes file + DB row)."""
    error = db.session.get(Error, error_id)
    image = db.session.get(ErrorImage, image_id)
    if error is None or image is None or image.error_id != error.id:
        flash("Photo not found.", "error")
        return redirect(url_for("admin.error_list"))

    # Delete file
    delete_error_image(_upload_root(), image.image_path)

    db.session.delete(image)
    db.session.commit()

    flash("Photo deleted.", "success")
    return redirect(url_for("admin.error_photos", error_id=error.id))


# =========================================================
# REPAIR HISTORY (V4.5)
# =========================================================

from ..models import RepairHistory, Favorite, ChangeLog
from .forms import RepairHistoryForm


def _populate_error_choices(form, machine):
    """Populate error dropdown with errors linked to this machine."""
    errors = machine.errors if machine.errors else []
    form.error_id.choices = [(0, "— None —")] + [
        (e.id, f"{e.error_code} — {e.error_name}") for e in errors
    ]


@admin_bp.route("/machines/<int:machine_id>/repairs", methods=["GET", "POST"])
@login_required
@admin_required
def machine_repairs(machine_id: int):
    """Manage repair history for a machine."""
    machine = db.session.get(Machine, machine_id)
    if machine is None:
        flash("Machine not found.", "error")
        return redirect(url_for("admin.machine_list"))

    form = RepairHistoryForm()
    _populate_error_choices(form, machine)

    if form.validate_on_submit():
        # Parse repaired_at
        from datetime import datetime, timezone
        repaired_at_str = (form.repaired_at.data or "").strip()
        repaired_at = datetime.now(timezone.utc)
        if repaired_at_str:
            try:
                repaired_at = datetime.strptime(
                    repaired_at_str, "%Y-%m-%d %H:%M"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                flash("Invalid date format. Use YYYY-MM-DD HH:MM", "error")
                return render_template(
                    "admin/machines/repairs.html",
                    machine=machine, form=form,
                    repairs=_get_repairs(machine),
                ), 400

        error_id = form.error_id.data if form.error_id.data != 0 else None

        repair = RepairHistory(
            machine_id=machine.id,
            error_id=error_id,
            performed_by=current_user.id,
            repaired_at=repaired_at,
            description=form.description.data.strip(),
            notes=(form.notes.data or "").strip() or None,
        )
        db.session.add(repair)
        db.session.commit()

        from ..sync import record_change
        record_change("repair_history", repair.id, "CREATE")
        db.session.commit()

        flash("Repair entry added.", "success")
        return redirect(url_for("admin.machine_repairs", machine_id=machine.id))

    return render_template(
        "admin/machines/repairs.html",
        machine=machine,
        form=form,
        repairs=_get_repairs(machine),
    )


@admin_bp.route("/machines/<int:machine_id>/repairs/<int:repair_id>/delete",
                methods=["POST"])
@login_required
@admin_required
def machine_repair_delete(machine_id: int, repair_id: int):
    """Delete a repair entry."""
    machine = db.session.get(Machine, machine_id)
    repair = db.session.get(RepairHistory, repair_id)
    if machine is None or repair is None or repair.machine_id != machine.id:
        flash("Repair not found.", "error")
        return redirect(url_for("admin.machine_list"))

    db.session.delete(repair)
    db.session.commit()
    flash("Repair entry deleted.", "success")
    return redirect(url_for("admin.machine_repairs", machine_id=machine.id))


def _get_repairs(machine):
    return (
        RepairHistory.query
        .filter_by(machine_id=machine.id)
        .order_by(RepairHistory.repaired_at.desc())
        .all()
    )


# =========================================================
# CHANGE LOGS (V4.5)
# =========================================================

@admin_bp.route("/change-logs")
@login_required
@admin_required
def change_logs():
    """View recent change logs with full audit info."""
    entity_filter = request.args.get("entity", type=str) or ""
    user_filter = request.args.get("user_id", type=int)
    action_filter = request.args.get("action", type=str) or ""
    limit = min(max(request.args.get("limit", 200, type=int) or 200, 1), 500)

    q = ChangeLog.query
    if entity_filter:
        q = q.filter(ChangeLog.entity == entity_filter)
    if user_filter:
        q = q.filter(ChangeLog.user_id == user_filter)
    if action_filter:
        q = q.filter(ChangeLog.action == action_filter)

    logs = q.order_by(ChangeLog.id.desc()).limit(limit).all()

    # Build enriched rows with target labels
    enriched = []
    for log in logs:
        target_label = _resolve_target_label(log.entity, log.record_id)
        enriched.append({
            "log": log,
            "target_label": target_label,
        })

    # Counts per entity
    from sqlalchemy import func as sql_func
    counts = dict(
        db.session.query(ChangeLog.entity, sql_func.count(ChangeLog.id))
        .group_by(ChangeLog.entity).all()
    )

    # Filter options
    users = User.query.order_by(User.username).all()
    actions = ["CREATE", "UPDATE", "DELETE"]

    return render_template(
        "admin/change_logs.html",
        rows=enriched,
        logs=logs,
        users=users,
        actions=actions,
        entity_filter=entity_filter,
        user_filter=user_filter or 0,
        action_filter=action_filter,
        counts=counts,
    )


def _resolve_target_label(entity: str, record_id: int) -> str:
    """Resolve a record label for display."""
    try:
        if entity == "machines":
            m = db.session.get(Machine, record_id)
            return f"{m.machine_code} — {m.machine_name}" if m else f"# {record_id}"
        elif entity == "errors":
            e = db.session.get(Error, record_id)
            return f"{e.error_code} — {e.error_name}" if e else f"# {record_id}"
        elif entity == "shops":
            s = db.session.get(Shop, record_id)
            return f"{s.shop_code} — {s.shop_name}" if s else f"# {record_id}"
        elif entity == "users":
            u = db.session.get(User, record_id)
            return f"@{u.username}" if u else f"# {record_id}"
        elif entity == "error_images":
            img = db.session.get(ErrorImage, record_id)
            return f"Photo #{record_id}" if img else f"# {record_id}"
        elif entity == "repair_history":
            r = db.session.get(RepairHistory, record_id)
            return f"Repair #{record_id}" if r else f"# {record_id}"
        return f"# {record_id}"
    except Exception:
        return f"# {record_id}"


# =========================================================
# SETUP GUIDE (V4.6)
# =========================================================

@admin_bp.route("/setup-guide")
@login_required
@admin_required
def setup_guide():
    """Step-by-step setup guide for admin."""
    # Detect what's been done
    from ..models import Shop, User, Machine, Error

    progress = {
        "has_shop": Shop.query.count() > 0,
        "has_user": User.query.filter_by(role="USER").count() > 0,
        "has_machine": Machine.query.count() > 0,
        "has_error": Error.query.count() > 0,
        "has_error_with_fix": Error.query.filter(
            Error.error_fix.isnot(None), Error.error_fix != ""
        ).count() > 0,
        "has_linked": db.session.query(Machine).join(
            Machine.errors
        ).count() > 0,
    }

    return render_template("admin/setup_guide.html", progress=progress)


# =========================================================
# PENDING USERS (V5.1)
# =========================================================

@admin_bp.route("/users/pending")
@login_required
@admin_required
def pending_users():
    """List of pending user registrations."""
    pending = (
        User.query
        .filter_by(status=User.STATUS_PENDING)
        .order_by(User.created_at.desc())
        .all()
    )
    return render_template("admin/users/pending.html", pending=pending)


@admin_bp.route("/users/<int:user_id>/pending")
@login_required
@admin_required
def pending_user_detail(user_id: int):
    """Pending user detail — assign shop + import machines + approve."""
    user = db.session.get(User, user_id)
    if user is None or user.status != User.STATUS_PENDING:
        flash("Pending user not found.", "error")
        return redirect(url_for("admin.pending_users"))

    shops = Shop.query.filter(
        Shop.status != Shop.STATUS_ARCHIVED
    ).order_by(Shop.shop_code).all()

    return render_template(
        "admin/users/pending_detail.html",
        user=user,
        shops=shops,
    )


@admin_bp.route("/users/<int:user_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_user(user_id: int):
    """Approve a pending user — assign shop, set ACTIVE."""
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("admin.pending_users"))

    if user.status != User.STATUS_PENDING:
        flash("User is not pending.", "warning")
        return redirect(url_for("admin.pending_users"))

    # Get shop from form
    shop_id = request.form.get("shop_id", type=int)
    if not shop_id:
        flash("Shop ကို ရွေးပါ။", "error")
        return redirect(url_for("admin.pending_user_detail", user_id=user.id))

    shop = db.session.get(Shop, shop_id)
    if shop is None:
        flash("Shop မမှန်ပါ။", "error")
        return redirect(url_for("admin.pending_user_detail", user_id=user.id))

    # Assign shop + activate
    user.shop_id = shop.id
    user.status = User.STATUS_ACTIVE
    db.session.commit()

    flash(
        f"User @{user.username} ကို {shop.shop_code} shop မှာ approve လုပ်ပြီးပါပြီ။",
        "success",
    )
    return redirect(url_for("admin.pending_users"))


@admin_bp.route("/users/<int:user_id>/reject", methods=["POST"])
@login_required
@admin_required
def reject_user(user_id: int):
    """Reject (delete) a pending user."""
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("admin.pending_users"))

    if user.status != User.STATUS_PENDING:
        flash("User is not pending.", "warning")
        return redirect(url_for("admin.pending_users"))

    username = user.username
    db.session.delete(user)
    db.session.commit()

    flash(f"User @{username} ကို ပယ်ဖျက်ပြီးပါပြီ။", "info")
    return redirect(url_for("admin.pending_users"))


# =========================================================
# SHOP DETAIL (V5.2)
# =========================================================

@admin_bp.route("/shops/<int:shop_id>")
@login_required
@admin_required
def shop_detail(shop_id: int):
    """Shop detail — machines + users in this shop."""
    shop = db.session.get(Shop, shop_id)
    if shop is None:
        flash("Shop not found.", "error")
        return redirect(url_for("admin.shop_list"))

    machines = (
        Machine.query
        .filter_by(shop_id=shop.id)
        .order_by(Machine.machine_code)
        .all()
    )
    users = (
        User.query
        .filter_by(shop_id=shop.id)
        .order_by(User.username)
        .all()
    )

    from ..models import ImportBatch
    batches = (
        ImportBatch.query
        .filter_by(shop_id=shop.id, status=ImportBatch.STATUS_ACTIVE)
        .order_by(ImportBatch.created_at.desc())
        .all()
    )

    return render_template(
        "admin/shops/detail.html",
        shop=shop,
        machines=machines,
        users=users,
        batches=batches,
    )

# =========================================================
# ERROR DELETE (V5.3)
# =========================================================

@admin_bp.route("/errors/<int:error_id>/delete", methods=["POST"])
@login_required
@admin_required
def error_delete(error_id: int):
    """Archive a single error."""
    error = db.session.get(Error, error_id)
    if error is None:
        flash("Error not found.", "error")
        return redirect(url_for("admin.error_list"))

    code = error.error_code
    error.status = Error.STATUS_ARCHIVED
    db.session.commit()

    record_change("errors", error.id, "UPDATE")

    flash(f"Error '{code}' archived.", "success")

    next_url = request.form.get("next") or request.referrer
    if next_url and "/admin/errors" in next_url:
        return redirect(next_url)
    return redirect(url_for("admin.error_list"))


@admin_bp.route("/errors/bulk-delete", methods=["POST"])
@login_required
@admin_required
def errors_bulk_delete():
    """Bulk archive errors."""
    ids = request.form.getlist("error_ids")
    ids = [int(i) for i in ids if i.isdigit()]

    if not ids:
        flash("No errors selected.", "warning")
        return redirect(url_for("admin.error_list"))

    count = 0
    for eid in ids:
        e = db.session.get(Error, eid)
        if e:
            e.status = Error.STATUS_ARCHIVED
            record_change("errors", e.id, "UPDATE")
            count += 1

    db.session.commit()
    flash(f"{count} error(s) archived.", "success")
    return redirect(url_for("admin.error_list"))


# =========================================================
# RESTORE ARCHIVED (V5.3)
# =========================================================

@admin_bp.route("/machines/<int:machine_id>/restore", methods=["POST"])
@login_required
@admin_required
def machine_restore(machine_id: int):
    """Restore an archived machine to ACTIVE."""
    machine = db.session.get(Machine, machine_id)
    if machine is None:
        flash("Machine not found.", "error")
        return redirect(url_for("admin.machine_list"))

    code = machine.machine_code
    machine.status = Machine.STATUS_ACTIVE
    db.session.commit()
    record_change("machines", machine.id, "UPDATE")

    flash(f"Machine '{code}' restored.", "success")
    return redirect(request.referrer or url_for("admin.machine_list"))


@admin_bp.route("/errors/<int:error_id>/restore", methods=["POST"])
@login_required
@admin_required
def error_restore(error_id: int):
    """Restore an archived error to ACTIVE."""
    error = db.session.get(Error, error_id)
    if error is None:
        flash("Error not found.", "error")
        return redirect(url_for("admin.error_list"))

    code = error.error_code
    error.status = Error.STATUS_ACTIVE
    db.session.commit()
    record_change("errors", error.id, "UPDATE")

    flash(f"Error '{code}' restored.", "success")
    return redirect(request.referrer or url_for("admin.error_list"))


# =========================================================
# PERMANENT DELETE (V5.3) — Danger Zone
# =========================================================

@admin_bp.route("/machines/<int:machine_id>/permanent-delete", methods=["POST"])
@login_required
@admin_required
def machine_permanent_delete(machine_id: int):
    """Permanently delete an archived machine. Cannot be undone."""
    machine = db.session.get(Machine, machine_id)
    if machine is None:
        flash("Machine not found.", "error")
        return redirect(url_for("admin.machine_list"))

    if machine.status != Machine.STATUS_ARCHIVED:
        flash("Only archived machines can be permanently deleted.", "warning")
        return redirect(url_for("admin.machine_list"))

    # Confirm by typing the code
    confirm_code = (request.form.get("confirm_code") or "").strip().upper()
    if confirm_code != machine.machine_code.upper():
        flash("Confirmation code does not match.", "error")
        return redirect(url_for("admin.machine_list"))

    code = machine.machine_code
    machine_id = machine.id

    # Record DELETE before removing
    record_change("machines", machine_id, "DELETE")
    db.session.delete(machine)
    db.session.commit()

    flash(f"Machine '{code}' permanently deleted.", "success")
    return redirect(url_for("admin.machine_list"))


@admin_bp.route("/errors/<int:error_id>/permanent-delete", methods=["POST"])
@login_required
@admin_required
def error_permanent_delete(error_id: int):
    """Permanently delete an archived error. Cannot be undone."""
    error = db.session.get(Error, error_id)
    if error is None:
        flash("Error not found.", "error")
        return redirect(url_for("admin.error_list"))

    if error.status != Error.STATUS_ARCHIVED:
        flash("Only archived errors can be permanently deleted.", "warning")
        return redirect(url_for("admin.error_list"))

    confirm_code = (request.form.get("confirm_code") or "").strip().upper()
    if confirm_code != error.error_code.upper():
        flash("Confirmation code does not match.", "error")
        return redirect(url_for("admin.error_list"))

    code = error.error_code
    error_id = error.id

    # Record DELETE before removing
    record_change("errors", error_id, "DELETE")
    db.session.delete(error)
    db.session.commit()

    flash(f"Error '{code}' permanently deleted.", "success")
    return redirect(url_for("admin.error_list"))


# =========================================================
# EXCEL EXPORT (V5.3)
# =========================================================

@admin_bp.route("/machines/export")
@login_required
@admin_required
def machines_export():
    """Export filtered machines to Excel."""
    from io import BytesIO
    from flask import send_file
    from openpyxl import Workbook

    q = Machine.query.join(Shop)

    shop_filter = request.args.get("shop_id", type=int)
    status_filter = request.args.get("status", type=str)
    search = (request.args.get("q", type=str) or "").strip()

    if shop_filter is not None and shop_filter > 0:
        q = q.filter(Machine.shop_id == shop_filter)
    if status_filter in Machine.ALL_STATUSES:
        q = q.filter(Machine.status == status_filter)
    if search:
        like = f"%{search}%"
        q = q.filter(db.or_(
            Machine.machine_name.ilike(like),
            Machine.machine_code.ilike(like),
        ))

    machines = q.order_by(Shop.shop_code, Machine.machine_code).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Machines"
    ws.append(["Shop", "machine_code", "machine_name", "description", "status", "errors_count"])

    for m in machines:
        ws.append([
            m.shop.shop_code if m.shop else "",
            m.machine_code,
            m.machine_name,
            m.description or "",
            m.status,
            len(m.errors),
        ])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    from datetime import datetime
    filename = f"machines_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@admin_bp.route("/errors/export")
@login_required
@admin_required
def errors_export():
    """Export errors to Excel."""
    from io import BytesIO
    from flask import send_file
    from openpyxl import Workbook

    q = Error.query

    status_filter = request.args.get("status", type=str)
    search = (request.args.get("q", type=str) or "").strip()

    if status_filter in Error.ALL_STATUSES:
        q = q.filter(Error.status == status_filter)
    if search:
        like = f"%{search}%"
        q = q.filter(db.or_(
            Error.error_code.ilike(like),
            Error.error_name.ilike(like),
        ))

    errors = q.order_by(Error.error_code).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Errors"
    ws.append(["error_code", "error_name", "error_fix", "explanation", "category", "status", "machines_count"])

    for e in errors:
        ws.append([
            e.error_code,
            e.error_name,
            e.error_fix or "",
            e.explanation or "",
            e.category or "ERROR",
            e.status,
            len(e.machines),
        ])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    from datetime import datetime
    filename = f"errors_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"

    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )



# =========================================================
# ACTIVITY LOG (V5.3)
# =========================================================

from ..models import ActivityLog
from sqlalchemy import func as sql_func
from datetime import datetime, timezone, timedelta


@admin_bp.route("/activity")
@login_required
@admin_required
def activity_log():
    """Full activity log with filters."""
    from datetime import datetime

    q = ActivityLog.query

    # Filters
    user_id = request.args.get("user_id", type=int)
    action = request.args.get("action", type=str)
    shop_id = request.args.get("shop_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = 100

    if user_id:
        q = q.filter(ActivityLog.user_id == user_id)
    if action:
        q = q.filter(ActivityLog.action == action)
    if shop_id:
        q = q.filter(ActivityLog.shop_id == shop_id)

    total = q.count()
    logs = (
        q.order_by(ActivityLog.created_at.desc())
        .limit(per_page)
        .offset((page - 1) * per_page)
        .all()
    )

    total_pages = (total + per_page - 1) // per_page

    # Filter options
    users = User.query.order_by(User.username).all()
    shops = Shop.query.order_by(Shop.shop_code).all()

    # Action types
    actions = [
        "LOGIN", "LOGOUT", "SEARCH",
        "VIEW_MACHINE", "VIEW_ERROR",
        "FAVORITE", "UNFAVORITE",
        "SYNC", "OFFLINE",
    ]

    return render_template(
        "admin/activity.html",
        logs=logs,
        users=users,
        shops=shops,
        actions=actions,
        page=page,
        total=total,
        total_pages=total_pages,
        filters={
            "user_id": user_id or 0,
            "action": action or "",
            "shop_id": shop_id or 0,
        },
    )


@admin_bp.route("/users/<int:user_id>/activity")
@login_required
@admin_required
def user_activity(user_id: int):
    """Per-user activity detail."""
    user = db.session.get(User, user_id)
    if user is None:
        flash("User not found.", "error")
        return redirect(url_for("admin.user_list"))

    logs = (
        ActivityLog.query
        .filter_by(user_id=user.id)
        .order_by(ActivityLog.created_at.desc())
        .limit(200)
        .all()
    )

    # Stats
    total_logs = ActivityLog.query.filter_by(user_id=user.id).count()
    searches = ActivityLog.query.filter_by(user_id=user.id, action="SEARCH").count()
    machine_views = ActivityLog.query.filter_by(user_id=user.id, action="VIEW_MACHINE").count()
    error_views = ActivityLog.query.filter_by(user_id=user.id, action="VIEW_ERROR").count()

    # Top searches
    from sqlalchemy import func as sql_func
    top_searches = (
        db.session.query(ActivityLog.target_label, sql_func.count(ActivityLog.id))
        .filter(
            ActivityLog.user_id == user.id,
            ActivityLog.action == "SEARCH",
            ActivityLog.target_label.isnot(None),
        )
        .group_by(ActivityLog.target_label)
        .order_by(sql_func.count(ActivityLog.id).desc())
        .limit(10)
        .all()
    )

    # Last login
    last_login = (
        ActivityLog.query
        .filter_by(user_id=user.id, action="LOGIN")
        .order_by(ActivityLog.created_at.desc())
        .first()
    )

    return render_template(
        "admin/user_activity.html",
        user=user,
        logs=logs,
        total_logs=total_logs,
        searches=searches,
        machine_views=machine_views,
        error_views=error_views,
        top_searches=top_searches,
        last_login=last_login,
    )


@admin_bp.route("/api/activity/live")
@login_required
@admin_required
def api_activity_live():
    """Live activity feed — last 50 actions."""
    from datetime import datetime, timedelta, timezone

    since_seconds = request.args.get("since", 60, type=int)
    since = datetime.now(timezone.utc) - timedelta(seconds=since_seconds)

    logs = (
        ActivityLog.query
        .filter(ActivityLog.created_at >= since)
        .order_by(ActivityLog.created_at.desc())
        .limit(50)
        .all()
    )

    # Online users — active in last 5 minutes
    online_since = datetime.now(timezone.utc) - timedelta(minutes=5)
    online_user_ids = (
        db.session.query(ActivityLog.user_id)
        .filter(ActivityLog.created_at >= online_since)
        .distinct()
        .all()
    )
    online_user_ids = [uid[0] for uid in online_user_ids]

    online_users = User.query.filter(User.id.in_(online_user_ids)).all()

    return jsonify({
        "logs": [
            {
                **log.to_dict(),
                "user_name": log.user.name if log.user else None,
                "user_username": log.user.username if log.user else None,
                "shop_code": (
                    db.session.get(Shop, log.shop_id).shop_code
                    if log.shop_id else None
                ),
            }
            for log in logs
        ],
        "online_users": [
            {
                "id": u.id,
                "name": u.name,
                "username": u.username,
                "shop_id": u.shop_id,
            }
            for u in online_users
        ],
        "count": len(logs),
        "online_count": len(online_users),
    })


@admin_bp.route("/api/activity/stats")
@login_required
@admin_required
def api_activity_stats():
    """Activity stats — today, week, month."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    def count_since(delta):
        since = now - delta
        return ActivityLog.query.filter(ActivityLog.created_at >= since).count()

    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_count = ActivityLog.query.filter(ActivityLog.created_at >= today).count()

    # Top users by activity today
    top_users = (
        db.session.query(
            ActivityLog.user_id,
            sql_func.count(ActivityLog.id).label("count"),
        )
        .filter(ActivityLog.created_at >= today)
        .group_by(ActivityLog.user_id)
        .order_by(sql_func.count(ActivityLog.id).desc())
        .limit(5)
        .all()
    )

    top_users_data = []
    for uid, count in top_users:
        u = db.session.get(User, uid)
        if u:
            top_users_data.append({
                "id": u.id,
                "name": u.name,
                "username": u.username,
                "count": count,
            })

    # Top searches today
    top_searches = (
        db.session.query(
            ActivityLog.target_label,
            sql_func.count(ActivityLog.id).label("count"),
        )
        .filter(
            ActivityLog.created_at >= today,
            ActivityLog.action == "SEARCH",
            ActivityLog.target_label.isnot(None),
        )
        .group_by(ActivityLog.target_label)
        .order_by(sql_func.count(ActivityLog.id).desc())
        .limit(10)
        .all()
    )

    return jsonify({
        "today": today_count,
        "hour": count_since(timedelta(hours=1)),
        "day": count_since(timedelta(days=1)),
        "week": count_since(timedelta(days=7)),
        "month": count_since(timedelta(days=30)),
        "top_users": top_users_data,
        "top_searches": [
            {"query": q, "count": c} for q, c in top_searches
        ],
    })


# =========================================================
# IMPORT BATCH DELETE (V5.4)
# =========================================================

@admin_bp.route("/shops/<int:shop_id>/batches/<int:batch_id>/delete", methods=["POST"])
@login_required
@admin_required
def batch_delete(shop_id: int, batch_id: int):
    """Permanently delete all machines in a batch."""
    from ..models import ImportBatch, Machine

    shop = db.session.get(Shop, shop_id)
    batch = db.session.get(ImportBatch, batch_id)
    if shop is None or batch is None or batch.shop_id != shop.id:
        flash("Batch not found.", "error")
        return redirect(url_for("admin.shop_detail", shop_id=shop_id))

    # Confirm dialog value
    confirm = (request.form.get("confirm") or "").strip()
    if confirm != "DELETE":
        flash("Type DELETE to confirm.", "error")
        return redirect(url_for("admin.shop_detail", shop_id=shop_id))

    # Find machines in batch
    machines = Machine.query.filter_by(batch_id=batch.id).all()
    count = len(machines)

    # Record delete for each
    for m in machines:
        record_change("machines", m.id, "DELETE")

    # Delete machines
    for m in machines:
        db.session.delete(m)

    # Delete batch
    db.session.delete(batch)
    db.session.commit()

    flash(
        f"Deleted {count} machine(s) from batch '{batch.filename or batch.id}'.",
        "success",
    )
    return redirect(url_for("admin.shop_detail", shop_id=shop_id))


# =========================================================
# MACHINE BULK DELETE + SINGLE DELETE (V5.3)
# =========================================================

@admin_bp.route("/shops/<int:shop_id>/machines/bulk-delete", methods=["POST"])
@login_required
@admin_required
def machines_bulk_delete(shop_id: int):
    """Bulk archive machines."""
    shop = db.session.get(Shop, shop_id)
    if shop is None:
        flash("Shop not found.", "error")
        return redirect(url_for("admin.shop_list"))

    ids = request.form.getlist("machine_ids")
    ids = [int(i) for i in ids if i.isdigit()]

    if not ids:
        flash("No machines selected.", "warning")
        return redirect(url_for("admin.shop_detail", shop_id=shop.id))

    count = 0
    for mid in ids:
        m = db.session.get(Machine, mid)
        if m and m.shop_id == shop.id:
            m.status = Machine.STATUS_ARCHIVED
            record_change("machines", m.id, "UPDATE")
            count += 1

    db.session.commit()
    flash(f"{count} machine(s) archived.", "success")
    return redirect(url_for("admin.shop_detail", shop_id=shop.id))


@admin_bp.route("/machines/<int:machine_id>/delete", methods=["POST"])
@login_required
@admin_required
def machine_delete(machine_id: int):
    """Archive a single machine."""
    machine = db.session.get(Machine, machine_id)
    if machine is None:
        flash("Machine not found.", "error")
        return redirect(url_for("admin.machine_list"))

    code = machine.machine_code
    machine.status = Machine.STATUS_ARCHIVED
    db.session.commit()
    record_change("machines", machine.id, "UPDATE")
    db.session.commit()

    flash(f"Machine '{code}' archived.", "success")
    next_url = request.form.get("next") or request.referrer
    if next_url and "/admin/shops/" in next_url:
        return redirect(next_url)
    return redirect(url_for("admin.machine_list"))
