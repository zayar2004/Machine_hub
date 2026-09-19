"""Favorite model — user's saved machines/errors."""
from ..extensions import db
from .base import TimestampMixin


class Favorite(TimestampMixin, db.Model):
    """A user's favorite machine or error.

    Both machine_id and error_id are optional, but exactly one must be set.
    """
    __tablename__ = "favorites"

    ITEM_MACHINE = "machine"
    ITEM_ERROR = "error"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_type = db.Column(db.String(20), nullable=False, index=True)
    machine_id = db.Column(
        db.Integer,
        db.ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    error_id = db.Column(
        db.Integer,
        db.ForeignKey("errors.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # Relationships
    user = db.relationship("User", backref="favorites")
    machine = db.relationship("Machine")
    error = db.relationship("Error")

    __table_args__ = (
        db.CheckConstraint(
            "(item_type = 'machine' AND machine_id IS NOT NULL AND error_id IS NULL) OR "
            "(item_type = 'error' AND error_id IS NOT NULL AND machine_id IS NULL)",
            name="ck_favorite_item_type",
        ),
        db.UniqueConstraint(
            "user_id", "machine_id", name="uq_favorite_user_machine",
        ),
        db.UniqueConstraint(
            "user_id", "error_id", name="uq_favorite_user_error",
        ),
    )

    def __repr__(self) -> str:
        return f"<Favorite user={self.user_id} {self.item_type}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "item_type": self.item_type,
            "machine_id": self.machine_id,
            "error_id": self.error_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
