"""V1.4 — Shop Management tests."""
import pytest

from app import create_app
from app.extensions import db
from app.models import Shop, User, Machine


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        admin = User(name="Admin", username="admin", role=User.ROLE_ADMIN)
        admin.set_password("admin123")
        db.session.add(admin)

        u = User(name="User", username="user", role=User.ROLE_USER)
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
        "username": "user", "password": "user123",
    })


# ---------- Permission ----------

def test_shop_list_requires_login(client):
    res = client.get("/admin/shops", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_shop_list_blocks_normal_user(client):
    login_user(client)
    res = client.get("/admin/shops")
    assert res.status_code == 403


def test_shop_list_allows_admin(client):
    login_admin(client)
    res = client.get("/admin/shops")
    assert res.status_code == 200
    assert b"Shops" in res.data


# ---------- Create ----------

def test_shop_create_via_form(client, app):
    login_admin(client)
    res = client.post("/admin/shops/new", data={
        "shop_code": "A3",
        "shop_name": "Shop A3",
        "status": "ACTIVE",
    }, follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        s = Shop.query.filter_by(shop_code="A3").first()
        assert s is not None
        assert s.shop_name == "Shop A3"


def test_shop_create_duplicate_code(client, app):
    with app.app_context():
        db.session.add(Shop(shop_code="A3", shop_name="Existing"))
        db.session.commit()

    login_admin(client)
    res = client.post("/admin/shops/new", data={
        "shop_code": "A3",
        "shop_name": "Duplicate",
        "status": "ACTIVE",
    })
    assert res.status_code == 400
    assert b"already exists" in res.data


# ---------- Edit ----------

def test_shop_edit(client, app):
    with app.app_context():
        s = Shop(shop_code="A3", shop_name="Old Name")
        db.session.add(s)
        db.session.commit()
        sid = s.id

    login_admin(client)
    res = client.post(f"/admin/shops/{sid}/edit", data={
        "shop_code": "A3",
        "shop_name": "New Name",
        "status": "ACTIVE",
    }, follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        s = db.session.get(Shop, sid)
        assert s.shop_name == "New Name"


# ---------- Status changes ----------

def test_shop_deactivate(client, app):
    with app.app_context():
        s = Shop(shop_code="A3", shop_name="S", status=Shop.STATUS_ACTIVE)
        db.session.add(s)
        db.session.commit()
        sid = s.id

    login_admin(client)
    res = client.post(f"/admin/shops/{sid}/status/INACTIVE",
                      follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        s = db.session.get(Shop, sid)
        assert s.status == Shop.STATUS_INACTIVE


def test_shop_archive(client, app):
    with app.app_context():
        s = Shop(shop_code="A3", shop_name="S")
        db.session.add(s)
        db.session.commit()
        sid = s.id

    login_admin(client)
    client.post(f"/admin/shops/{sid}/status/ARCHIVED")

    with app.app_context():
        s = db.session.get(Shop, sid)
        assert s.status == Shop.STATUS_ARCHIVED


def test_shop_invalid_status(client, app):
    with app.app_context():
        s = Shop(shop_code="A3", shop_name="S")
        db.session.add(s)
        db.session.commit()
        sid = s.id

    login_admin(client)
    res = client.post(f"/admin/shops/{sid}/status/BOGUS",
                      follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        s = db.session.get(Shop, sid)
        assert s.status == Shop.STATUS_ACTIVE  # unchanged


# ---------- Dashboard ----------

def test_dashboard_shows_counts(client, app):
    with app.app_context():
        db.session.add(Shop(shop_code="A3", shop_name="S"))
        db.session.commit()

    login_admin(client)
    res = client.get("/admin/")
    assert res.status_code == 200
    assert (b"Shops" in res.data) or (b"Total Shops" in res.data)


# ---------- Counts in list ----------

def test_shop_list_shows_counts(client, app):
    with app.app_context():
        s = Shop(shop_code="A3", shop_name="Shop A3")
        db.session.add(s)
        db.session.commit()
        db.session.add(Machine(shop_id=s.id, machine_name="M1", machine_code="M1"))
        db.session.add(Machine(shop_id=s.id, machine_name="M2", machine_code="M2"))
        db.session.commit()

    login_admin(client)
    res = client.get("/admin/shops")
    assert res.status_code == 200
    assert b"2" in res.data
