"""Import batch — tracks Excel imports for bulk management."""
from ..extensions import db
from .base import TimestampMixin


class ImportBatch(TimestampMixin, db.Model):
    __tablename__ = "import_batches"

    STATUS_ACTIVE = "ACTIVE"
    STATUS_DELETED = "DELETED"

    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(
        db.Integer,
        db.ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename = db.Column(db.String(255), nullable=True)
    machine_count = db.Column(db.Integer, default=0, nullable=False)
    created_by = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = db.Column(db.String(20), default=STATUS_ACTIVE, nullable=False, index=True)
    notes = db.Column(db.String(500), nullable=True)

    # Relationships
    shop = db.relationship("Shop", backref="import_batches")
    user = db.relationship("User")
    machines = db.relationship(
        "Machine",
        back_populates="batch",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ImportBatch {self.id} shop={self.shop_id} count={self.machine_count}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "shop_id": self.shop_id,
            "filename": self.filename,
            "machine_count": self.machine_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "status": self.status,
        }
