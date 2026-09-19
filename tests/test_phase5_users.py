"""V1.5 — User Management tests."""
import pytest

from app import create_app
from app.extensions import db
from app.models import Shop, User


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        s = Shop(shop_code="A3", shop_name="Shop A3")
        db.session.add(s)
        db.session.commit()

        admin = User(name="Admin", username="admin", role=User.ROLE_ADMIN)
        admin.set_password("admin123")
        db.session.add(admin)

        u = User(name="A3 Staff", username="a3user",
                 role=User.ROLE_USER, shop_id=s.id)
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


# ---------- List + permissions ----------

def test_user_list_requires_admin(client):
    res = client.get("/admin/users", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_user_list_blocks_normal_user(client):
    login_user(client)
    res = client.get("/admin/users")
    assert res.status_code == 403


def test_user_list_allows_admin(client):
    login_admin(client)
    res = client.get("/admin/users")
    assert res.status_code == 200
    assert b"admin" in res.data
    assert b"a3user" in res.data


def test_user_list_filter_by_role(client):
    login_admin(client)
    res = client.get("/admin/users?role=ADMIN")
    assert res.status_code == 200
    assert b"admin" in res.data
    assert b"a3user" not in res.data


# ---------- Create ----------

def test_user_create_success(client, app):
    login_admin(client)
    res = client.post("/admin/users/new", data={
        "name": "New Staff",
        "username": "newstaff",
        "password": "pass1234",
        "confirm_password": "pass1234",
        "role": "USER",
        "shop_id": "1",
        "status": "ACTIVE",
    }, follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        u = User.query.filter_by(username="newstaff").first()
        assert u is not None
        assert u.shop_id == 1
        assert u.check_password("pass1234") is True


def test_user_create_duplicate_username(client):
    login_admin(client)
    res = client.post("/admin/users/new", data={
        "name": "Dup",
        "username": "admin",
        "password": "pass1234",
        "confirm_password": "pass1234",
        "role": "ADMIN",
        "shop_id": "0",
        "status": "ACTIVE",
    })
    assert res.status_code == 400
    assert b"already taken" in res.data


def test_user_create_password_mismatch(client):
    login_admin(client)
    res = client.post("/admin/users/new", data={
        "name": "Test User",
        "username": "newuser",
        "password": "pass1234",
        "confirm_password": "different",
        "role": "USER",
        "shop_id": "1",
        "status": "ACTIVE",
    })
    assert res.status_code == 200  # form re-render
    assert b"must match" in res.data.lower() or b"Passwords" in res.data


def test_user_create_user_without_shop_rejected(client):
    login_admin(client)
    res = client.post("/admin/users/new", data={
        "name": "No Shop",
        "username": "nouser",
        "password": "pass1234",
        "confirm_password": "pass1234",
        "role": "USER",
        "shop_id": "0",
        "status": "ACTIVE",
    })
    assert res.status_code == 400
    assert b"must be assigned" in res.data


# ---------- Edit ----------

def test_user_edit_name_and_shop(client, app):
    with app.app_context():
        u = User.query.filter_by(username="a3user").first()
        uid = u.id

    login_admin(client)
    res = client.post(f"/admin/users/{uid}/edit", data={
        "name": "Renamed Staff",
        "username": "a3user",
        "role": "USER",
        "shop_id": "1",
        "status": "ACTIVE",
    }, follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        u = db.session.get(User, uid)
        assert u.name == "Renamed Staff"


def test_user_edit_duplicate_username(client, app):
    # Ensure both users exist in a clean state
    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        assert admin is not None

        u = User.query.filter_by(username="a3user").first()
        assert u is not None
        uid = u.id
        shop_id = u.shop_id

    login_admin(client)
    res = client.post(f"/admin/users/{uid}/edit", data={
        "name": "Test User",
        "username": "admin",  # already taken by another user
        "role": "USER",
        "shop_id": str(shop_id),
        "status": "ACTIVE",
    })

    # Either the form re-renders (200) with an error, or route returns 400.
    # We check the response body for the duplicate-username message.
    assert res.status_code in (200, 400), f"Unexpected: {res.status_code}"
    assert b"already taken" in res.data, "Duplicate username error not shown"


def test_user_cannot_deactivate_self(client, app):
    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        aid = admin.id

    login_admin(client)
    res = client.post(f"/admin/users/{aid}/edit", data={
        "name": "Admin",
        "username": "admin",
        "role": "ADMIN",
        "shop_id": "0",
        "status": "INACTIVE",
    })
    assert res.status_code == 400
    assert b"cannot deactivate yourself" in res.data.lower()


# ---------- Password reset ----------

def test_password_reset(client, app):
    with app.app_context():
        u = User.query.filter_by(username="a3user").first()
        uid = u.id

    login_admin(client)
    res = client.post(f"/admin/users/{uid}/password", data={
        "new_password": "newsecret99",
        "confirm_password": "newsecret99",
    }, follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        u = db.session.get(User, uid)
        assert u.check_password("newsecret99") is True
        assert u.check_password("user123") is False


# ---------- Toggle status ----------

def test_user_toggle_status(client, app):
    with app.app_context():
        u = User.query.filter_by(username="a3user").first()
        uid = u.id

    login_admin(client)
    res = client.post(f"/admin/users/{uid}/toggle-status",
                      follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        u = db.session.get(User, uid)
        assert u.status == User.STATUS_INACTIVE


def test_user_toggle_status_self_blocked(client, app):
    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        aid = admin.id

    login_admin(client)
    res = client.post(f"/admin/users/{aid}/toggle-status",
                      follow_redirects=False)
    assert res.status_code in (301, 302)

    # Admin should still be ACTIVE
    with app.app_context():
        admin = db.session.get(User, aid)
        assert admin.status == User.STATUS_ACTIVE
