"""Sync service — track changes and serve incremental data."""
from typing import Any

from flask_login import current_user

from ..extensions import db
from ..models import (
    Shop, User, Machine, Error, ErrorImage, RepairHistory,
    SyncState, ChangeLog,
)


SYNCABLE_ENTITIES = (
    "shops", "users", "machines", "errors", "error_images", "repair_history",
)


def record_change(entity: str, record_id: int, action: str = "UPDATE",
                  detail: str | None = None) -> int:
    """Record a change."""
    if entity not in SYNCABLE_ENTITIES:
        return 0

    new_version = SyncState.bump(entity)

    user_id = None
    user_label = None
    try:
        if current_user and current_user.is_authenticated:
            user_id = current_user.id
            user_label = f"@{current_user.username}"
    except Exception:
        pass

    log = ChangeLog(
        entity=entity,
        record_id=record_id,
        version=new_version,
        action=action,
        user_id=user_id,
        user_label=user_label,
        detail=(detail or "")[:500] or None,
    )
    db.session.add(log)

    return new_version


def get_all_versions() -> dict[str, int]:
    rows = SyncState.query.filter(
        SyncState.entity.in_(SYNCABLE_ENTITIES)
    ).all()
    by_entity = {r.entity: r.current_version for r in rows}
    return {e: by_entity.get(e, 0) for e in SYNCABLE_ENTITIES}


def get_max_version() -> int:
    versions = get_all_versions()
    return max(versions.values()) if versions else 0


def _serialize(model, obj) -> dict:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return {c.name: getattr(obj, c.name) for c in model.__table__.columns}


def get_changes_since(since_version: int, limit: int = 500) -> dict:
    """Return changes since a given version.

    Includes:
      - changes: current records for each entity
      - deletes: list of {entity, id} records deleted since since_version
    """
    result: dict[str, Any] = {
        "current_version": get_max_version(),
        "changes": {e: [] for e in SYNCABLE_ENTITIES},
        "deletes": [],  # ← NEW
        "has_more": False,
    }

    if since_version < 0:
        since_version = 0

    by_entity: dict[str, list[int]] = {e: [] for e in SYNCABLE_ENTITIES}
    deletes: list[dict] = []
    has_more = False

    logs = (
        ChangeLog.query
        .filter(ChangeLog.version > since_version)
        .order_by(ChangeLog.version.asc(), ChangeLog.id.asc())
        .limit(limit + 1)
        .all()
    )

    if len(logs) > limit:
        has_more = True
        logs = logs[:limit]

    for log in logs:
        if log.entity not in by_entity:
            continue
        if log.action == "DELETE":
            deletes.append({
                "entity": log.entity,
                "id": log.record_id,
            })
        else:
            by_entity[log.entity].append(log.record_id)

    models_map = {
        "shops": Shop,
        "users": User,
        "machines": Machine,
        "errors": Error,
        "error_images": ErrorImage,
        "repair_history": RepairHistory,
    }

    for entity, ids in by_entity.items():
        if not ids:
            continue
        model = models_map[entity]
        unique_ids = list(set(ids))
        records = model.query.filter(model.id.in_(unique_ids)).all()
        result["changes"][entity] = [_serialize(model, r) for r in records]

    # If a record was deleted but also updated before, the actual record may
    # not exist anymore. Detect: if entity changed but record missing — treat as DELETE
    for entity, ids in by_entity.items():
        if not ids:
            continue
        model = models_map[entity]
        unique_ids = list(set(ids))
        existing_ids = {r.id for r in model.query.filter(model.id.in_(unique_ids)).all()}
        missing = [rid for rid in unique_ids if rid not in existing_ids]
        for rid in missing:
            # Check if already in deletes
            already = any(d["entity"] == entity and d["id"] == rid for d in deletes)
            if not already:
                deletes.append({"entity": entity, "id": rid})

    result["deletes"] = deletes
    result["has_more"] = has_more
    return result
