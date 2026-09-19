"""Application configuration classes."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _default_sqlite_uri() -> str:
    """Absolute SQLite URI — avoids 'unable to open database file'."""
    db_path = BASE_DIR / "instance" / "machine_hub.db"
    return f"sqlite:///{db_path}"


def _absolute_upload_folder() -> str:
    return str(BASE_DIR / "uploads")


class Config:
    """Base configuration shared by all environments."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-fallback-change-me")

    # Database — prefer DATABASE_URL from .env; fall back to absolute path.
    _db_url = os.environ.get("DATABASE_URL", _default_sqlite_uri())
    # Render/Heroku give postgres:// — SQLAlchemy 2.x needs postgresql://
    if _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "future": True,
    }

    # Uploads
    UPLOAD_FOLDER = os.environ.get(
        "UPLOAD_FOLDER", _absolute_upload_folder()
    )
    MAX_CONTENT_LENGTH = int(
        os.environ.get("MAX_CONTENT_LENGTH", 10 * 1024 * 1024)  # 10 MB
    )

    # Session / Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    WTF_CSRF_TIME_LIMIT = None

    # Long-lived sessions (1 year) — user logs in once, stays logged in
    from datetime import timedelta
    PERMANENT_SESSION_LIFETIME = timedelta(days=365)
    REMEMBER_COOKIE_DURATION = timedelta(days=365)
    REMEMBER_COOKIE_SECURE = False  # Termux localhost — set True in production
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # Pagination
    ITEMS_PER_PAGE = 20

    # Templates
    TEMPLATES_AUTO_RELOAD = True


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


CONFIG_MAP = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
