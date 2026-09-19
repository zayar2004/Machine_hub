"""V4.6 — UI/UX + Help text tests."""
import pytest

from app import create_app
from app.extensions import db
from app.models import Shop, User, Machine, Error


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        a3 = Shop(shop_code="A3", shop_name="Shop A3")
        db.session.add(a3)
        db.session.commit()

        admin = User(name="Admin", username="admin", role=User.ROLE_ADMIN)
        admin.set_password("admin123")
        db.session.add(admin)

        u = User(name="A3 Staff", username="a3user",
                 role=User.ROLE_USER, shop_id=a3.id)
        u.set_password("user123")
        db.session.add(u)
        db.session.commit()

        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def login_admin(client):
    return client.post("/auth/login", data={
        "username": "admin", "password": "admin123",
    })


def login_user(client):
    return client.post("/auth/login", data={
        "username": "a3user", "password": "user123",
    })


# ---------- Setup Guide ----------

def test_setup_guide_requires_admin(client):
    login_user(client)
    res = client.get("/admin/setup-guide")
    assert res.status_code == 403


def test_setup_guide_renders(client):
    login_admin(client)
    res = client.get("/admin/setup-guide")
    assert res.status_code == 200
    assert b"Setup Guide" in res.data
    assert b"Shop" in res.data


# ---------- Help Center ----------

def test_help_requires_login(client):
    res = client.get("/help", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_help_renders(client):
    login_user(client)
    res = client.get("/help")
    assert res.status_code == 200
    assert b"Help Center" in res.data


# ---------- Docs ----------

def test_docs_renders(client):
    login_user(client)
    res = client.get("/docs")
    assert res.status_code == 200
    assert b"Documentation" in res.data


# ---------- Admin sidebar ----------

def test_admin_sidebar_renders(client):
    login_admin(client)
    res = client.get("/admin/")
    assert res.status_code == 200
    assert b"Dashboard" in res.data
    assert b"Change Logs" in res.data
    assert b"Setup Guide" in res.data


# ---------- Help banners ----------

def test_shop_list_renders(client):
    login_admin(client)
    res = client.get("/admin/shops")
    assert res.status_code == 200
    assert b"Shops" in res.data


def test_machine_list_renders(client):
    login_admin(client)
    res = client.get("/admin/machines")
    assert res.status_code == 200
    assert b"Machines" in res.data


def test_error_list_renders(client):
    login_admin(client)
    res = client.get("/admin/errors")
    assert res.status_code == 200
    assert b"Errors" in res.data


def test_user_list_renders(client):
    login_admin(client)
    res = client.get("/admin/users")
    assert res.status_code == 200
    assert b"Users" in res.data


# ---------- Drawer links ----------

def test_drawer_has_help_links(client):
    login_user(client)
    res = client.get("/")
    assert b"Help Center" in res.data
    assert b"Documentation" in res.data
