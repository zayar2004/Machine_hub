"""Authorization decorators."""
from functools import wraps

from flask import abort, redirect, url_for
from flask_login import current_user


def admin_required(view):
    """Allow only authenticated ADMIN users. Others get 403."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def shop_user_required(view):
    """Allow only authenticated non-admin users with a shop assigned."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.is_admin:
            abort(403)
        if current_user.shop_id is None:
            abort(403)
        return view(*args, **kwargs)
    return wrapper
