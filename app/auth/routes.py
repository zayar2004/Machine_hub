"""Authentication routes."""
from datetime import datetime, timezone, timedelta

from flask import (
    Blueprint, render_template, redirect, url_for,
    flash, request, session, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user

from ..extensions import db
from ..models import User
from ..utils import log_activity
from .forms import LoginForm, RegisterForm

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("user.home"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip().lower()).first()

        if user is None or not user.check_password(form.password.data):
            flash("Invalid username or password.", "error")
            return render_template("auth/login.html", form=form), 401

        if user.status == User.STATUS_PENDING:
            flash(
                "သင့် account ကို Admin က စစ်ဆေးနေပါတယ်။ "
                "အတည်ပြုပြီးရင် login လုပ်နိုင်ပါမယ်။",
                "warning",
            )
            return render_template("auth/login.html", form=form), 403

        if user.status != User.STATUS_ACTIVE:
            flash("သင့် account ကို ပိတ်ထားပါတယ်။ Admin ကို ဆက်သွယ်ပါ။", "error")
            return render_template("auth/login.html", form=form), 403

        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

        # Remember forever (1 year) — always use remember=True
        login_user(user, remember=True, duration=timedelta(days=365))
        session.permanent = True
        current_app.permanent_session_lifetime = timedelta(days=365)

        # Redirect by role
        if user.is_admin:
            return redirect(url_for("admin.dashboard"))
        return redirect(url_for("user.home"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("user.home"))

    form = RegisterForm()
    if form.validate_on_submit():
        full_name = form.name.data.strip()

        # Generate unique username
        username = User.generate_username(full_name)

        user = User(
            name=full_name,
            username=username,
            role=User.ROLE_USER,
            shop_id=None,  # will be set by admin
            status=User.STATUS_PENDING,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash(
            f"Account ဖန်တီးပြီးပါပြီ။\n"
            f"Username: {username}\n"
            f"Admin အတည်ပြုပြီးရင် login လုပ်နိုင်ပါမယ်။",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    try:
        log_activity("LOGOUT")
    except Exception:
        pass
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
