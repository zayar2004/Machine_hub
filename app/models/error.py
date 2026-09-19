"""Error model — global error knowledge base."""
from ..extensions import db
from .base import TimestampMixin, StatusMixin


class Error(TimestampMixin, StatusMixin, db.Model):
    __tablename__ = "errors"

    id = db.Column(db.Integer, primary_key=True)
    error_code = db.Column(db.String(60), unique=True, nullable=False, index=True)
    error_name = db.Column(db.String(200), nullable=False, index=True)
    error_fix = db.Column(db.Text, nullable=True)
    explanation = db.Column(db.Text, nullable=True)

    # Machine name / pattern — for auto-matching without M2M linkage
    # Admin can enter full name, partial, or keyword (freeform)
    machine_name = db.Column(db.String(200), nullable=True, index=True)

    # Knowledge category — ERROR / TIP / INFO / HOW_TO
    category = db.Column(
        db.String(20),
        default="ERROR",
        nullable=False,
        index=True,
    )

    # Sync / versioning
    data_version = db.Column(db.Integer, default=1, nullable=False)

    # Relationships
    machines = db.relationship(
        "Machine",
        secondary="machine_errors",
        back_populates="errors",
        lazy="selectin",
    )
    images = db.relationship(
        "ErrorImage",
        back_populates="error",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ErrorImage.sort_order",
    )

    def __repr__(self) -> str:
        return f"<Error {self.error_code} {self.error_name}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "error_code": self.error_code,
            "error_name": self.error_name,
            "error_fix": self.error_fix,
            "explanation": self.explanation,
            "machine_name": self.machine_name,
            "status": self.status,
            "data_version": self.data_version,
            "category": self.category or "ERROR",
            "image_count": len(self.images),
            "machine_count": len(self.machines),
            "machine_ids": [m.id for m in self.machines],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
