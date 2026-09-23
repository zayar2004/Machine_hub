"""Admin package."""
from .routes import admin_bp
from .updates import admin_updates_bp

__all__ = ["admin_bp", "admin_updates_bp"]
