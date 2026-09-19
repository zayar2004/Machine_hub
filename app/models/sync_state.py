"""Global sync version tracker — one row per entity type."""
from ..extensions import db
from .base import TimestampMixin


class SyncState(TimestampMixin, db.Model):
    """Tracks the current version number for each entity type.

    There is exactly ONE row per entity (shops, users, machines,
    errors, error_images). Increment `current_version` whenever
    a record of that type is created/updated.
    """
    __tablename__ = "sync_states"

    id = db.Column(db.Integer, primary_key=True)
    entity = db.Column(db.String(40), unique=True, nullable=False, index=True)
    current_version = db.Column(db.Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<SyncState {self.entity}={self.current_version}>"

    @classmethod
    def get_version(cls, entity: str) -> int:
        row = cls.query.filter_by(entity=entity).first()
        return row.current_version if row else 0

    @classmethod
    def bump(cls, entity: str) -> int:
        """Increment and return the new version."""
        row = cls.query.filter_by(entity=entity).first()
        if row is None:
            row = cls(entity=entity, current_version=1)
            db.session.add(row)
        else:
            row.current_version += 1
        return row.current_version
