"""Error image model — photos attached to an error."""
from ..extensions import db
from .base import TimestampMixin


class ErrorImage(TimestampMixin, db.Model):
    __tablename__ = "error_images"

    id = db.Column(db.Integer, primary_key=True)
    error_id = db.Column(
        db.Integer,
        db.ForeignKey("errors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_path = db.Column(db.String(255), nullable=False)

    # 🆕 Base64 image data (for Render persistence — 386K small photos)
    # Format: raw base64 string WITHOUT data: prefix
    image_data = db.Column(db.Text, nullable=True)
    mime_type = db.Column(db.String(60), nullable=True, default="image/jpeg")

    caption = db.Column(db.String(200), nullable=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    file_size = db.Column(db.Integer, nullable=True)  # bytes
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)

    # Relationship
    error = db.relationship("Error", back_populates="images")

    def __repr__(self) -> str:
        return f"<ErrorImage error={self.error_id} path={self.image_path}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "error_id": self.error_id,
            "image_path": self.image_path,
            "caption": self.caption,
            "sort_order": self.sort_order,
            "file_size": self.file_size,
            "width": self.width,
            "height": self.height,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
