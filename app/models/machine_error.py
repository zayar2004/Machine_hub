"""Many-to-many association: machine ↔ error."""
from ..extensions import db


machine_errors = db.Table(
    "machine_errors",
    db.Column(
        "machine_id",
        db.Integer,
        db.ForeignKey("machines.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "error_id",
        db.Integer,
        db.ForeignKey("errors.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
