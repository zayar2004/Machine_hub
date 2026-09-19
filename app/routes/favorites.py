"""Favorites API — user's saved machines/errors."""
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Favorite, Machine, Error


favorites_bp = Blueprint("favorites", __name__, url_prefix="/api/favorites")


def _favorite_dict(fav: Favorite) -> dict:
    """Serialize favorite with related item details."""
    result = fav.to_dict()
    result["item"] = None
    if fav.item_type == "machine" and fav.machine:
        result["item"] = {
            "id": fav.machine.id,
            "machine_code": fav.machine.machine_code,
            "machine_name": fav.machine.machine_name,
            "shop_id": fav.machine.shop_id,
            "shop_code": fav.machine.shop.shop_code if fav.machine.shop else None,
        }
    elif fav.item_type == "error" and fav.error:
        result["item"] = {
            "id": fav.error.id,
            "error_code": fav.error.error_code,
            "error_name": fav.error.error_name,
        }
    return result


@favorites_bp.route("", methods=["GET"])
@login_required
def list_favorites():
    """List the current user's favorites."""
    favs = (
        Favorite.query
        .filter_by(user_id=current_user.id)
        .order_by(Favorite.created_at.desc())
        .all()
    )
    return jsonify({
        "favorites": [_favorite_dict(f) for f in favs],
        "count": len(favs),
    })


@favorites_bp.route("/machine/<int:machine_id>", methods=["POST"])
@login_required
def toggle_machine(machine_id: int):
    """Toggle favorite for a machine."""
    machine = db.session.get(Machine, machine_id)
    if machine is None:
        return jsonify({"error": "Machine not found"}), 404

    # Users can only favorite their own shop's machines
    if not current_user.is_admin and machine.shop_id != current_user.shop_id:
        return jsonify({"error": "Forbidden"}), 403

    existing = Favorite.query.filter_by(
        user_id=current_user.id,
        item_type=Favorite.ITEM_MACHINE,
        machine_id=machine.id,
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"status": "removed", "is_favorite": False})

    fav = Favorite(
        user_id=current_user.id,
        item_type=Favorite.ITEM_MACHINE,
        machine_id=machine.id,
    )
    db.session.add(fav)
    db.session.commit()
    return jsonify({
        "status": "added",
        "is_favorite": True,
        "favorite": _favorite_dict(fav),
    })


@favorites_bp.route("/error/<int:error_id>", methods=["POST"])
@login_required
def toggle_error(error_id: int):
    """Toggle favorite for an error (global)."""
    error = db.session.get(Error, error_id)
    if error is None:
        return jsonify({"error": "Error not found"}), 404

    existing = Favorite.query.filter_by(
        user_id=current_user.id,
        item_type=Favorite.ITEM_ERROR,
        error_id=error.id,
    ).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"status": "removed", "is_favorite": False})

    fav = Favorite(
        user_id=current_user.id,
        item_type=Favorite.ITEM_ERROR,
        error_id=error.id,
    )
    db.session.add(fav)
    db.session.commit()
    return jsonify({
        "status": "added",
        "is_favorite": True,
        "favorite": _favorite_dict(fav),
    })


@favorites_bp.route("/check", methods=["GET"])
@login_required
def check_favorites():
    """Check if items are favorited.

    Query params:
      machine_ids — comma-separated IDs
      error_ids   — comma-separated IDs
    """
    machine_ids = [
        int(x) for x in (request.args.get("machine_ids", "") or "").split(",")
        if x.strip().isdigit()
    ]
    error_ids = [
        int(x) for x in (request.args.get("error_ids", "") or "").split(",")
        if x.strip().isdigit()
    ]

    result = {"machines": {}, "errors": {}}

    if machine_ids:
        favs = Favorite.query.filter(
            Favorite.user_id == current_user.id,
            Favorite.item_type == Favorite.ITEM_MACHINE,
            Favorite.machine_id.in_(machine_ids),
        ).all()
        for f in favs:
            result["machines"][str(f.machine_id)] = True

    if error_ids:
        favs = Favorite.query.filter(
            Favorite.user_id == current_user.id,
            Favorite.item_type == Favorite.ITEM_ERROR,
            Favorite.error_id.in_(error_ids),
        ).all()
        for f in favs:
            result["errors"][str(f.error_id)] = True

    return jsonify(result)
