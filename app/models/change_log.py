"""Change log — records every change for incremental sync + audit."""
from ..extensions import db
from .base import TimestampMixin


class ChangeLog(TimestampMixin, db.Model):
    """One row per changed entity record.

    Tracks WHO changed WHAT, WHEN, and HOW.
    """
    __tablename__ = "change_logs"

    id = db.Column(db.Integer, primary_key=True)
    entity = db.Column(db.String(40), nullable=False, index=True)
    record_id = db.Column(db.Integer, nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False, index=True)
    action = db.Column(db.String(20), nullable=False)  # CREATE/UPDATE/DELETE

    # Audit fields
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_label = db.Column(db.String(120), nullable=True)  # username snapshot
    detail = db.Column(db.String(500), nullable=True)  # summary

    __table_args__ = (
        db.Index("ix_changelog_entity_version", "entity", "version"),
    )

    user = db.relationship("User")

    def __repr__(self) -> str:
        return f"<ChangeLog {self.entity}#{self.record_id} v{self.version} {self.action}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entity": self.entity,
            "record_id": self.record_id,
            "version": self.version,
            "action": self.action,
            "user_id": self.user_id,
            "user_label": self.user_label,
            "detail": self.detail,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
