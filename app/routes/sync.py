"""Sync API — version + incremental changes."""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from ..sync import get_all_versions, get_changes_since, get_max_version
from ..extensions import db
from ..models import Machine, Error, Shop

sync_bp = Blueprint("sync", __name__, url_prefix="/api/sync")


@sync_bp.after_request
def _no_cache_sync(response):
    """Sync API must never be cached — browser/SW should always hit server."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@sync_bp.route("/version")
@login_required
def version():
    """Return current server version info.

    Response:
      {
        "server_version": N,
        "entities": {"shops": v, "machines": v, ...},
        "shop_id": <current user's shop id or null>
      }
    """
    return jsonify({
        "server_version": get_max_version(),
        "entities": get_all_versions(),
        "shop_id": current_user.shop_id,
        "is_admin": current_user.is_admin,
    })


@sync_bp.route("/changes")
@login_required
def changes():
    """Return incremental changes since a given version.

    Query params:
      since — int (default 0)
      limit — int (default 500, max 1000)

    Response:
      {
        "current_version": N,
        "changes": {
          "shops": [...],
          "users": [...],
          ...
        },
        "has_more": bool,
      }
    """
    since = request.args.get("since", 0, type=int) or 0
    limit = min(max(request.args.get("limit", 500, type=int) or 500, 1), 1000)

    result = get_changes_since(since_version=since, limit=limit)

    # Scope: non-admin users only get their own shop's machines
    if not current_user.is_admin:
        user_shop = current_user.shop_id
        if user_shop:
            result["changes"]["machines"] = [
                m for m in result["changes"]["machines"]
                if m.get("shop_id") == user_shop
            ]
        else:
            result["changes"]["machines"] = []

        # Non-admins don't get user list
        result["changes"]["users"] = []

    # Shops: everyone gets the list (needed for shop codes)
    # Users: only admins
    if not current_user.is_admin:
        result["changes"]["users"] = []

    return jsonify(result)
