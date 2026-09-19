"""Repair history model — log of repairs for a machine."""
from ..extensions import db
from .base import TimestampMixin


class RepairHistory(TimestampMixin, db.Model):
    """A single repair event for a machine."""
    __tablename__ = "repair_history"

    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(
        db.Integer,
        db.ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    error_id = db.Column(
        db.Integer,
        db.ForeignKey("errors.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    performed_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    repaired_at = db.Column(db.DateTime(timezone=True), nullable=False)
    description = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    # Sync version
    data_version = db.Column(db.Integer, default=1, nullable=False)

    # Relationships
    machine = db.relationship("Machine", backref="repair_history")
    error = db.relationship("Error")
    performed_by_user = db.relationship("User")

    def __repr__(self) -> str:
        return f"<RepairHistory machine={self.machine_id} at={self.repaired_at}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "machine_id": self.machine_id,
            "error_id": self.error_id,
            "performed_by": self.performed_by,
            "repaired_at": self.repaired_at.isoformat() if self.repaired_at else None,
            "description": self.description,
            "notes": self.notes,
            "data_version": self.data_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
