"""V1.3 — Authentication tests."""
import pytest

from app import create_app
from app.extensions import db
from app.models import Shop, User


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        # Create A3 shop
        a3 = Shop(shop_code="A3", shop_name="Shop A3")
        db.session.add(a3)
        db.session.commit()

        # Admin
        admin = User(name="Admin", username="admin", role=User.ROLE_ADMIN)
        admin.set_password("admin123")
        db.session.add(admin)

        # A3 user
        u = User(name="A3 Staff", username="a3user",
                 role=User.ROLE_USER, shop_id=a3.id)
        u.set_password("user123")
        db.session.add(u)

        # Inactive user
        inactive = User(name="Inactive", username="ghost",
                        role=User.ROLE_USER, shop_id=a3.id,
                        status=User.STATUS_INACTIVE)
        inactive.set_password("ghost123")
        db.session.add(inactive)

        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


# ---------- Login page ----------

def test_login_page_renders(client):
    res = client.get("/auth/login")
    assert res.status_code == 200
    assert b"Machine Hub" in res.data
    assert b"Username" in res.data


# ---------- Login success ----------

def test_login_admin_success(client):
    res = client.post("/auth/login", data={
        "username": "admin", "password": "admin123",
    }, follow_redirects=False)
    assert res.status_code in (301, 302)
    # V1.9 — everyone is redirected to the user home
    assert res.headers.get("Location", "").rstrip("/") in ("", "/") \
        or res.headers.get("Location", "").endswith("/")


def test_login_user_success(client):
    res = client.post("/auth/login", data={
        "username": "a3user", "password": "user123",
    }, follow_redirects=False)
    assert res.status_code in (301, 302)


# ---------- Login failure ----------

def test_login_wrong_password(client):
    res = client.post("/auth/login", data={
        "username": "admin", "password": "wrong",
    })
    assert res.status_code == 401
    assert b"Invalid username or password" in res.data


def test_login_unknown_user(client):
    res = client.post("/auth/login", data={
        "username": "nobody", "password": "xxxx",
    })
    assert res.status_code == 401


def test_login_inactive_user(app, client):
    """Inactive user cannot login (403)."""
    from app.extensions import db
    from app.models import User

    with app.app_context():
        u = User.query.filter_by(username="ghost").first()
        if not u:
            u = User(username="ghost", name="Ghost", role="USER",
                     status=User.STATUS_INACTIVE)
            u.set_password("ghost123")
            db.session.add(u)
            db.session.commit()

    res = client.post("/auth/login", data={
        "username": "ghost", "password": "ghost123",
    })
    # Accept 403 or 401 depending on implementation
    assert res.status_code in (401, 403)


# ---------- Protected route ----------

# ---------- Logout ----------

def test_logout(client):
    client.post("/auth/login", data={
        "username": "admin", "password": "admin123",
    })
    res = client.get("/auth/logout", follow_redirects=False)
    assert res.status_code in (301, 302)
    assert "/auth/login" in res.headers.get("Location", "")

    # After logout, protected page should redirect to login
    res2 = client.get("/", follow_redirects=False)
    assert res2.status_code in (301, 302)
    assert "/auth/login" in res2.headers.get("Location", "")


# ---------- Role guards ----------

def test_admin_required_allows_admin(app, client):
    from app.utils import admin_required

    @app.route("/test/admin-only")
    @admin_required
    def _admin_only():
        return {"ok": True}

    client.post("/auth/login", data={
        "username": "admin", "password": "admin123",
    })
    res = client.get("/test/admin-only")
    assert res.status_code == 200


def test_admin_required_blocks_user(app, client):
    from app.utils import admin_required

    @app.route("/test/admin-only-2")
    @admin_required
    def _admin_only_2():
        return {"ok": True}

    client.post("/auth/login", data={
        "username": "a3user", "password": "user123",
    })
    res = client.get("/test/admin-only-2")
    assert res.status_code == 403


def test_admin_required_redirects_anonymous(app, client):
    from app.utils import admin_required

    @app.route("/test/admin-only-3")
    @admin_required
    def _admin_only_3():
        return {"ok": True}

    res = client.get("/test/admin-only-3", follow_redirects=False)
    assert res.status_code in (301, 302)
