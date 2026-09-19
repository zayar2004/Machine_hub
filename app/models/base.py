"""Shared base model with timestamps and helpers."""
from datetime import datetime, timezone

from ..extensions import db


def utcnow() -> datetime:
    """Timezone-aware UTC now."""
    return datetime.now(timezone.utc)


class TimestampMixin:
    """Adds created_at / updated_at to a model."""

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class StatusMixin:
    """Adds a status field: ACTIVE / INACTIVE / ARCHIVED."""

    STATUS_ACTIVE = "ACTIVE"
    STATUS_INACTIVE = "INACTIVE"
    STATUS_ARCHIVED = "ARCHIVED"
    ALL_STATUSES = (STATUS_ACTIVE, STATUS_INACTIVE, STATUS_ARCHIVED)

    status = db.Column(
        db.String(20),
        default=STATUS_ACTIVE,
        nullable=False,
        index=True,
    )

    def is_active(self) -> bool:
        return self.status == self.STATUS_ACTIVE
