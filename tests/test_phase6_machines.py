"""V1.6 — Machine Management tests."""
import pytest

from app import create_app
from app.extensions import db
from app.models import Shop, User, Machine


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        a3 = Shop(shop_code="A3", shop_name="Shop A3")
        a4 = Shop(shop_code="A4", shop_name="Shop A4")
        db.session.add_all([a3, a4])
        db.session.commit()

        admin = User(name="Admin", username="admin", role=User.ROLE_ADMIN)
        admin.set_password("admin123")
        db.session.add(admin)

        u = User(name="A3 Staff", username="a3user",
                 role=User.ROLE_USER, shop_id=a3.id)
        u.set_password("user123")
        db.session.add(u)

        # Seed a couple of machines
        db.session.add(Machine(
            shop_id=a3.id, machine_name="Dream Castle",
            machine_code="DC001", status=Machine.STATUS_ACTIVE,
        ))
        db.session.add(Machine(
            shop_id=a3.id, machine_name="Dream World",
            machine_code="DW001", status=Machine.STATUS_ACTIVE,
        ))
        db.session.add(Machine(
            shop_id=a4.id, machine_name="Epic",
            machine_code="DC001", status=Machine.STATUS_ACTIVE,
        ))

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


# ---------- Permissions ----------

def test_machine_list_requires_admin(client):
    res = client.get("/admin/machines", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_machine_list_blocks_normal_user(client):
    login_user(client)
    res = client.get("/admin/machines")
    assert res.status_code == 403


def test_machine_list_allows_admin(client):
    login_admin(client)
    res = client.get("/admin/machines")
    assert res.status_code == 200
    assert b"Dream Castle" in res.data
    assert b"Epic" in res.data


# ---------- Filters ----------

def test_machine_list_filter_by_shop(client):
    login_admin(client)
    with client.application.app_context():
        a4 = Shop.query.filter_by(shop_code="A4").first()
        a4_id = a4.id

    res = client.get(f"/admin/machines?shop_id={a4_id}")
    assert res.status_code == 200
    assert b"Epic" in res.data
    assert b"Dream Castle" not in res.data


def test_machine_list_search(client):
    login_admin(client)
    res = client.get("/admin/machines?q=Dream")
    assert res.status_code == 200
    assert b"Dream Castle" in res.data
    assert b"Dream World" in res.data
    assert b"Epic" not in res.data


def test_machine_list_filter_by_status(client):
    with client.application.app_context():
        m = Machine.query.filter_by(machine_code="DW001").first()
        m.status = Machine.STATUS_INACTIVE
        db.session.commit()

    login_admin(client)
    res = client.get("/admin/machines?status=INACTIVE")
    assert res.status_code == 200
    assert b"Dream World" in res.data
    assert b"Dream Castle" not in res.data


# ---------- Create ----------

def test_machine_create_success(client, app):
    with app.app_context():
        a3 = Shop.query.filter_by(shop_code="A3").first()
        a3_id = a3.id

    login_admin(client)
    res = client.post("/admin/machines/new", data={
        "shop_id": str(a3_id),
        "machine_name": "Marble World",
        "machine_code": "MW001",
        "description": "Test machine",
        "status": "ACTIVE",
    }, follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        m = Machine.query.filter_by(machine_code="MW001").first()
        assert m is not None
        assert m.shop_id == a3_id
        assert m.machine_name == "Marble World"


def test_machine_create_duplicate_code_in_same_shop(client, app):
    with app.app_context():
        a3 = Shop.query.filter_by(shop_code="A3").first()
        a3_id = a3.id

    login_admin(client)
    res = client.post("/admin/machines/new", data={
        "shop_id": str(a3_id),
        "machine_name": "Duplicate",
        "machine_code": "DC001",        # already in A3
        "description": "",
        "status": "ACTIVE",
    })
    assert res.status_code == 400
    assert b"already exists" in res.data


def test_machine_create_same_code_different_shop_ok(client, app):
    """Machine code DC001 exists in A3 and A4 — both should be allowed."""
    with app.app_context():
        a3 = Shop.query.filter_by(shop_code="A3").first()
        count_a3 = Machine.query.filter_by(
            shop_id=a3.id, machine_code="DC001"
        ).count()
        assert count_a3 == 1

        a4 = Shop.query.filter_by(shop_code="A4").first()
        count_a4 = Machine.query.filter_by(
            shop_id=a4.id, machine_code="DC001"
        ).count()
        assert count_a4 == 1

    # Create a 3rd in a NEW shop
    with app.app_context():
        new_shop = Shop(shop_code="A5", shop_name="Shop A5")
        db.session.add(new_shop)
        db.session.commit()
        new_id = new_shop.id

    login_admin(client)
    res = client.post("/admin/machines/new", data={
        "shop_id": str(new_id),
        "machine_name": "Another DC001",
        "machine_code": "DC001",
        "description": "",
        "status": "ACTIVE",
    }, follow_redirects=False)
    assert res.status_code in (301, 302)


# ---------- Edit ----------

def test_machine_edit(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001", shop_id=1).first()
        mid = m.id

    login_admin(client)
    res = client.post(f"/admin/machines/{mid}/edit", data={
        "shop_id": "1",
        "machine_name": "Dream Castle Renamed",
        "machine_code": "DC001",
        "description": "Updated",
        "status": "ACTIVE",
    }, follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        m = db.session.get(Machine, mid)
        assert m.machine_name == "Dream Castle Renamed"


def test_machine_edit_duplicate_code_in_same_shop(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DW001").first()
        mid = m.id

    login_admin(client)
    # Try to change DW001's code to DC001 (already in same shop)
    res = client.post(f"/admin/machines/{mid}/edit", data={
        "shop_id": "1",
        "machine_name": "Dream World",
        "machine_code": "DC001",
        "description": "",
        "status": "ACTIVE",
    })
    assert res.status_code == 400
    assert b"already exists" in res.data


# ---------- Status change ----------

def test_machine_status_change(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DW001").first()
        mid = m.id

    login_admin(client)
    res = client.post(f"/admin/machines/{mid}/status/INACTIVE",
                      follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        m = db.session.get(Machine, mid)
        assert m.status == Machine.STATUS_INACTIVE


def test_machine_invalid_status(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DW001").first()
        mid = m.id

    login_admin(client)
    res = client.post(f"/admin/machines/{mid}/status/BOGUS",
                      follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        m = db.session.get(Machine, mid)
        assert m.status == Machine.STATUS_ACTIVE  # unchanged
