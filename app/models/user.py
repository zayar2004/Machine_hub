"""User model."""
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from ..extensions import db
from .base import TimestampMixin


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    ROLE_ADMIN = "ADMIN"
    ROLE_USER = "USER"
    ALL_ROLES = (ROLE_ADMIN, ROLE_USER)

    STATUS_ACTIVE = "ACTIVE"
    STATUS_INACTIVE = "INACTIVE"
    STATUS_ARCHIVED = "ARCHIVED"
    STATUS_PENDING = "PENDING"
    ALL_STATUSES = ("ACTIVE", "INACTIVE", "ARCHIVED", "PENDING")

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(60), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    shop_id = db.Column(
        db.Integer,
        db.ForeignKey("shops.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    role = db.Column(db.String(20), default=ROLE_USER, nullable=False, index=True)
    status = db.Column(db.String(20), default=STATUS_ACTIVE, nullable=False, index=True)
    last_login = db.Column(db.DateTime(timezone=True), nullable=True)

    shop = db.relationship("Shop", back_populates="users", lazy="joined")

    def set_password(self, raw: str) -> None:
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    @property
    def is_admin(self) -> bool:
        return self.role == self.ROLE_ADMIN

    @property
    def is_active(self) -> bool:
        return self.status == self.STATUS_ACTIVE

    @property
    def is_pending(self) -> bool:
        return self.status == self.STATUS_PENDING

    def get_id(self) -> str:
        return str(self.id)

    def __repr__(self) -> str:
        return f"<User {self.username} role={self.role} status={self.status}>"

    # ---- helpers ----
    @staticmethod
    def generate_username(full_name: str) -> str:
        """Generate a unique username from a full name.

        "Aung Aung" → "aungaung", then "aungaung2", ...
        """
        import re
        base = re.sub(r'[^a-z0-9]', '', full_name.lower())
        if not base:
            base = "user"
        base = base[:40]

        # Find available
        candidate = base
        counter = 1
        while User.query.filter_by(username=candidate).first() is not None:
            counter += 1
            candidate = f"{base}{counter}"
        return candidate

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "shop_id": self.shop_id,
            "role": self.role,
            "status": self.status,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
