"""Repair History API."""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

from ..extensions import db
from ..models import RepairHistory, Machine, Error
from ..sync import record_change


repair_bp = Blueprint("repair_history", __name__,
                      url_prefix="/api/repair-history")


def _serialize(r: RepairHistory) -> dict:
    d = r.to_dict()
    d["machine_code"] = r.machine.machine_code if r.machine else None
    d["machine_name"] = r.machine.machine_name if r.machine else None
    d["error_code"] = r.error.error_code if r.error else None
    d["error_name"] = r.error.error_name if r.error else None
    d["performed_by_username"] = (
        r.performed_by_user.username if r.performed_by_user else None
    )
    return d


@repair_bp.route("", methods=["GET"])
@login_required
def list_repairs():
    """List repair history.

    Query params:
      machine_id — filter by machine (optional)
      limit      — default 100
    """
    q = RepairHistory.query

    machine_id = request.args.get("machine_id", type=int)
    if machine_id:
        q = q.filter(RepairHistory.machine_id == machine_id)

    # Non-admin: only see machines in their shop
    if not current_user.is_admin:
        if current_user.shop_id is None:
            q = q.filter(db.false())
        else:
            q = q.join(Machine).filter(Machine.shop_id == current_user.shop_id)

    limit = min(max(request.args.get("limit", 100, type=int) or 100, 1), 500)
    rows = q.order_by(RepairHistory.repaired_at.desc()).limit(limit).all()

    return jsonify({
        "repairs": [_serialize(r) for r in rows],
        "count": len(rows),
    })


@repair_bp.route("/machine/<int:machine_id>", methods=["POST"])
@login_required
def add_repair(machine_id: int):
    """Add a repair entry (admin only, or users for their own shop)."""
    machine = db.session.get(Machine, machine_id)
    if machine is None:
        return jsonify({"error": "Machine not found"}), 404

    if not current_user.is_admin and machine.shop_id != current_user.shop_id:
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json() or {}

    # Parse repaired_at
    repaired_at_str = (data.get("repaired_at") or "").strip()
    if repaired_at_str:
        try:
            repaired_at = datetime.fromisoformat(
                repaired_at_str.replace("Z", "+00:00")
            )
        except ValueError:
            return jsonify({"error": "Invalid repaired_at"}), 400
    else:
        repaired_at = datetime.now(timezone.utc)

    error_id = data.get("error_id")
    if error_id:
        error = db.session.get(Error, error_id)
        if error is None:
            return jsonify({"error": "Invalid error_id"}), 400

    repair = RepairHistory(
        machine_id=machine.id,
        error_id=error_id,
        performed_by=current_user.id,
        repaired_at=repaired_at,
        description=(data.get("description") or "").strip() or None,
        notes=(data.get("notes") or "").strip() or None,
    )
    db.session.add(repair)
    db.session.commit()

    record_change("repair_history", repair.id, "CREATE")
    db.session.commit()

    return jsonify({
        "status": "created",
        "repair": _serialize(repair),
    }), 201


@repair_bp.route("/<int:repair_id>", methods=["DELETE"])
@login_required
def delete_repair(repair_id: int):
    """Delete a repair entry (admin only)."""
    if not current_user.is_admin:
        return jsonify({"error": "Admin only"}), 403

    repair = db.session.get(RepairHistory, repair_id)
    if repair is None:
        return jsonify({"error": "Not found"}), 404

    db.session.delete(repair)
    db.session.commit()
    return jsonify({"status": "deleted"})
