"""Activity logger — record user actions."""
from datetime import datetime, timezone

from flask import request
from flask_login import current_user

from ..extensions import db
from ..models import ActivityLog


def log_activity(
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    target_label: str | None = None,
    meta: str | None = None,
) -> None:
    """Record a user activity.

    Safe — never raises. If logging fails, action still succeeds.
    """
    try:
        if not current_user or not current_user.is_authenticated:
            return

        ip = None
        ua = None
        try:
            ip = request.remote_addr
            ua = (request.user_agent.string or "")[:250] if request.user_agent else None
        except Exception:
            pass

        log = ActivityLog(
            user_id=current_user.id,
            shop_id=current_user.shop_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            target_label=(target_label or "")[:200] or None,
            meta=(meta or "")[:500] or None,
            ip_address=ip,
            user_agent=ua,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        # Never break the request
        try:
            db.session.rollback()
        except Exception:
            pass
        print(f"[ActivityLog] error: {e}")
