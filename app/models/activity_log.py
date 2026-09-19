"""Activity log — tracks user actions for admin monitoring."""
from ..extensions import db
from .base import TimestampMixin


class ActivityLog(TimestampMixin, db.Model):
    __tablename__ = "activity_logs"

    # Action types
    ACTION_LOGIN = "LOGIN"
    ACTION_LOGOUT = "LOGOUT"
    ACTION_SEARCH = "SEARCH"
    ACTION_VIEW_MACHINE = "VIEW_MACHINE"
    ACTION_VIEW_ERROR = "VIEW_ERROR"
    ACTION_FAVORITE = "FAVORITE"
    ACTION_UNFAVORITE = "UNFAVORITE"
    ACTION_SYNC = "SYNC"
    ACTION_OFFLINE = "OFFLINE"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shop_id = db.Column(db.Integer, nullable=True, index=True)
    action = db.Column(db.String(40), nullable=False, index=True)
    target_type = db.Column(db.String(40), nullable=True)  # machine / error
    target_id = db.Column(db.Integer, nullable=True)
    target_label = db.Column(db.String(200), nullable=True)  # e.g. "DC001"
    meta = db.Column(db.String(500), nullable=True)  # e.g. search query
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)

    user = db.relationship("User", backref="activity_logs")

    def __repr__(self) -> str:
        return f"<ActivityLog {self.user_id} {self.action} @{self.created_at}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "shop_id": self.shop_id,
            "action": self.action,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "target_label": self.target_label,
            "meta": self.meta,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
