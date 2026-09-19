"""Shop model — arcade/workplace locations."""
from ..extensions import db
from .base import TimestampMixin, StatusMixin


class Shop(TimestampMixin, StatusMixin, db.Model):
    __tablename__ = "shops"

    id = db.Column(db.Integer, primary_key=True)
    shop_code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    shop_name = db.Column(db.String(120), nullable=False)

    # Relationships
    users = db.relationship(
        "User",
        back_populates="shop",
        lazy="selectin",
        cascade="save-update, merge",
    )
    machines = db.relationship(
        "Machine",
        back_populates="shop",
        lazy="selectin",
        cascade="save-update, merge",
    )

    def __repr__(self) -> str:
        return f"<Shop {self.shop_code} {self.shop_name}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "shop_code": self.shop_code,
            "shop_name": self.shop_name,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
