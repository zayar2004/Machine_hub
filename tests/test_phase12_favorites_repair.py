"""V4 — Favorites + Repair History tests."""
from datetime import datetime, timezone

import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Shop, User, Machine, Error,
    Favorite, RepairHistory,
)


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

        m1 = Machine(shop_id=a3.id, machine_name="Dream Castle",
                     machine_code="DC001")
        m2 = Machine(shop_id=a4.id, machine_name="Epic",
                     machine_code="EP001")
        db.session.add_all([m1, m2])

        e1 = Error(error_code="E81", error_name="Screen Error")
        db.session.add(e1)

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


# ---------- Favorite model ----------

def test_favorite_machine_created(app):
    with app.app_context():
        u = User.query.filter_by(username="a3user").first()
        m = Machine.query.filter_by(machine_code="DC001").first()
        fav = Favorite(user_id=u.id, item_type=Favorite.ITEM_MACHINE,
                       machine_id=m.id)
        db.session.add(fav)
        db.session.commit()
        assert fav.id is not None
        assert fav.machine_id == m.id
        assert fav.error_id is None


# ---------- Favorites API ----------

def test_list_favorites_requires_login(client):
    res = client.get("/api/favorites", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_list_favorites_empty(client):
    login_user(client)
    res = client.get("/api/favorites")
    assert res.status_code == 200
    assert res.get_json()["count"] == 0


def test_toggle_machine_favorite(client, app):
    login_user(client)
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        mid = m.id

    res = client.post(f"/api/favorites/machine/{mid}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["is_favorite"] is True

    # List shows it
    res = client.get("/api/favorites")
    data = res.get_json()
    assert data["count"] == 1
    assert data["favorites"][0]["item"]["machine_code"] == "DC001"

    # Toggle off
    res = client.post(f"/api/favorites/machine/{mid}")
    assert res.get_json()["is_favorite"] is False


def test_toggle_error_favorite(client, app):
    login_user(client)
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        eid = e.id

    res = client.post(f"/api/favorites/error/{eid}")
    assert res.get_json()["is_favorite"] is True


def test_toggle_other_shop_machine_forbidden(client, app):
    login_user(client)
    with app.app_context():
        m = Machine.query.filter_by(machine_code="EP001").first()
        mid = m.id
    res = client.post(f"/api/favorites/machine/{mid}")
    assert res.status_code == 403


def test_check_favorites(client, app):
    login_user(client)
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        mid = m.id

    client.post(f"/api/favorites/machine/{mid}")
    res = client.get(f"/api/favorites/check?machine_ids={mid}")
    data = res.get_json()
    assert data["machines"][str(mid)] is True


# ---------- Repair History ----------

def test_add_repair_requires_login(client):
    res = client.post("/api/repair-history/machine/1")
    assert res.status_code in (301, 302)


def test_add_repair_success(client, app):
    login_admin(client)
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        mid = m.id

    res = client.post(
        f"/api/repair-history/machine/{mid}",
        json={
            "description": "Replaced HDMI cable",
            "notes": "Worked after replacement",
        },
    )
    assert res.status_code == 201
    data = res.get_json()
    assert data["repair"]["description"] == "Replaced HDMI cable"

    with app.app_context():
        assert RepairHistory.query.count() == 1


def test_list_repairs_user_scoped(client, app):
    login_user(client)
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        u = User.query.filter_by(username="a3user").first()
        db.session.add(RepairHistory(
            machine_id=m.id,
            performed_by=u.id,
            repaired_at=datetime.now(timezone.utc),
            description="Test repair",
        ))
        db.session.commit()

    res = client.get("/api/repair-history")
    data = res.get_json()
    assert data["count"] == 1
    assert data["repairs"][0]["description"] == "Test repair"


def test_add_repair_forbidden_other_shop(client, app):
    login_user(client)
    with app.app_context():
        m = Machine.query.filter_by(machine_code="EP001").first()
        mid = m.id

    res = client.post(f"/api/repair-history/machine/{mid}", json={})
    assert res.status_code == 403


def test_delete_repair_admin_only(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        u = User.query.filter_by(username="admin").first()
        r = RepairHistory(
            machine_id=m.id,
            performed_by=u.id,
            repaired_at=datetime.now(timezone.utc),
        )
        db.session.add(r)
        db.session.commit()
        rid = r.id

    # User cannot delete
    login_user(client)
    res = client.delete(f"/api/repair-history/{rid}")
    assert res.status_code == 403

    # Admin can
    client.get("/auth/logout")
    login_admin(client)
    res = client.delete(f"/api/repair-history/{rid}")
    assert res.status_code == 200
