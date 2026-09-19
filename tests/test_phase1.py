"""Phase 1 smoke tests — app factory, config, health route."""
from app import create_app


def test_app_factory_returns_flask_app():
    app = create_app("testing")
    assert app.name == "app"


def test_health_endpoint():
    app = create_app("testing")
    client = app.test_client()
    res = client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert data["app"] == "machine_hub"
    assert data["version"] == "5.0.0"
    assert data["phase"] == "V5.0"


def test_root_endpoint_redirects_to_login_when_anonymous():
    """In V1.9, `/` is the user home and requires login."""
    app = create_app("testing")
    client = app.test_client()
    res = client.get("/", follow_redirects=False)
    assert res.status_code in (301, 302)
    # Should redirect to the login page
    assert "/auth/login" in res.headers.get("Location", "")


def test_unknown_route_returns_404():
    app = create_app("testing")
    client = app.test_client()
    res = client.get("/does-not-exist")
    assert res.status_code == 404


def test_config_has_secret_key():
    app = create_app("testing")
    assert app.config["SECRET_KEY"]


def test_testing_db_is_in_memory():
    app = create_app("testing")
    assert app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:"
