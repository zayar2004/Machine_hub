"""Machine model — shop-scoped machine records."""
from ..extensions import db
from .base import TimestampMixin, StatusMixin


class Machine(TimestampMixin, StatusMixin, db.Model):
    __tablename__ = "machines"

    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(
        db.Integer,
        db.ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    batch_id = db.Column(
        db.Integer,
        db.ForeignKey("import_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    machine_name = db.Column(db.String(160), nullable=False, index=True)
    machine_code = db.Column(db.String(60), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(255), nullable=True)

    # Sync / versioning
    data_version = db.Column(db.Integer, default=1, nullable=False)

    # Relationships
    shop = db.relationship("Shop", back_populates="machines", lazy="joined")
    batch = db.relationship("ImportBatch", back_populates="machines")
    errors = db.relationship(
        "Error",
        secondary="machine_errors",
        back_populates="machines",
        lazy="selectin",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "shop_id", "machine_code",
            name="uq_machine_shop_code",
        ),
    )

    def __repr__(self) -> str:
        return f"<Machine shop={self.shop_id} code={self.machine_code}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "shop_id": self.shop_id,
            "machine_name": self.machine_name,
            "machine_code": self.machine_code,
            "description": self.description,
            "image": self.image,
            "status": self.status,
            "data_version": self.data_version,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
