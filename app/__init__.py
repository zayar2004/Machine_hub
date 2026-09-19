"""Flask application factory for Machine Hub."""
import os
from pathlib import Path

from flask import Flask, jsonify

from .config import CONFIG_MAP
from .extensions import db, login_manager, migrate, csrf


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure a Flask application instance."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(CONFIG_MAP.get(config_name, CONFIG_MAP["default"]))

    _ensure_runtime_dirs(app)
    _bind_extensions(app)
    _register_models()
    _auto_migrate(app)
    _auto_seed(app)
    _register_blueprints(app)
    _register_core_routes(app)

    return app


def _ensure_runtime_dirs(app: Flask) -> None:
    """Create instance/, uploads/, and SQLite parent dir if missing."""
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite:///") and ":memory:" not in uri:
        db_path = uri.replace("sqlite:///", "", 1)
        if db_path.startswith("//"):
            db_file = Path(db_path[1:])
        else:
            db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)


def _bind_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)


def _register_models() -> None:
    from . import models  # noqa: F401


def _auto_migrate(app: Flask) -> None:
    """Create tables on first run (idempotent — always safe)."""
    try:
        from .extensions import db
        with app.app_context():
            db.create_all()
            app.logger.info("[auto-migrate] tables ensured")
    except Exception as e:
        app.logger.error(f"[auto-migrate] FAILED: {e}")


def _auto_seed(app: Flask) -> None:
    """Seed default admin user (idempotent)."""
    try:
        from .extensions import db
        from .models import User
        with app.app_context():
            admin = User.query.filter_by(username="admin").first()
            if not admin:
                admin = User(
                    username="admin",
                    name="Admin",
                    role="ADMIN",
                    status="ACTIVE",
                )
                admin.set_password("admin123")
                db.session.add(admin)
                db.session.commit()
                app.logger.info("[auto-seed] admin created")
            else:
                app.logger.info("[auto-seed] admin exists")
    except Exception as e:
        app.logger.error(f"[auto-seed] FAILED: {e}")


def _register_blueprints(app: Flask) -> None:
    from .auth import auth_bp
    from .admin import admin_bp
    from .routes import search_bp
    from .routes.sync import sync_bp
    from .routes.favorites import favorites_bp
    from .routes.repair_history import repair_bp
    from .user import user_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(sync_bp)
    app.register_blueprint(favorites_bp)
    app.register_blueprint(repair_bp)
    app.register_blueprint(user_bp)


def _register_core_routes(app: Flask) -> None:
    @app.route("/health")
    def health():
        return jsonify(
            status="ok",
            app="machine_hub",
            version="5.0.0",
            phase="V5.0",
            env=app.config.get("ENV", "development"),
        )

    @app.route("/")
    def index():
        return jsonify(
            message="Machine Hub API — UI arrives in V1.9",
            health="/health",
            login="/auth/login",
            admin="/admin/",
        )

    @app.context_processor
    def _inject_admin_menu_shops():
        """Provide shops list for the admin sheet menu (dynamic submenu)."""
        from flask import request
        from flask_login import current_user

        # Only inject for admin templates — avoids DB hit on user pages
        if not (request.path or "").startswith("/admin"):
            return {}
        if not current_user.is_authenticated:
            return {}
        if getattr(current_user, "role", None) != "ADMIN":
            return {}

        from .models import Shop
        shops = (
            Shop.query
            .filter(Shop.status != Shop.STATUS_ARCHIVED)
            .order_by(Shop.shop_code)
            .all()
        )
        return {"menu_shops": shops}

    @app.errorhandler(404)
    def _not_found(e):
        from flask import render_template, request
        if request.path.startswith("/api/"):
            return jsonify(error="Not found"), 404
        try:
            return render_template("user/error_page.html",
                code=404,
                title="မတွေ့ပါ",
                message="ဒီ page ကို ရှာမတွေ့ပါ။",
            ), 404
        except Exception:
            return "404 Not Found", 404

    @app.errorhandler(500)
    def _server_error(e):
        from flask import render_template, request
        if request.path.startswith("/api/"):
            return jsonify(error="Server error"), 500
        try:
            return render_template("user/error_page.html",
                code=500,
                title="ပြဿနာ ရှိနေပါတယ်",
                message="ခဏအကြာတွင် ပြန်လည်ကြိုးစားပါ။",
            ), 500
        except Exception:
            return "500 Server Error", 500

    @app.after_request
    def _no_cache_for_admin(response):
        """Admin + Auth pages: always fresh (no browser/proxy cache).

        Prevents stale HTML after template updates.
        Static assets and public pages keep normal caching.
        """
        from flask import request

        path = request.path or ""
        if path.startswith("/admin") or path.startswith("/auth"):
            response.headers["Cache-Control"] = (
                "no-store, no-cache, must-revalidate, max-age=0"
            )
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
