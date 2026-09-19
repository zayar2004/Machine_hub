"""V4.5 — Repair History UI + Change Logs + Favorites List tests."""
from datetime import datetime, timezone

import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Shop, User, Machine, Error, RepairHistory, Favorite, ChangeLog,
)


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

        m = Machine(shop_id=a3.id, machine_name="Dream Castle",
                    machine_code="DC001")
        e = Error(error_code="E81", error_name="Screen Error")
        db.session.add_all([m, e])
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


# ---------- Repair UI ----------

def test_repairs_page_admin_only(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        mid = m.id

    login_user(client)
    res = client.get(f"/admin/machines/{mid}/repairs")
    assert res.status_code == 403


def test_repairs_page_renders(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        mid = m.id

    login_admin(client)
    res = client.get(f"/admin/machines/{mid}/repairs")
    assert res.status_code == 200
    assert b"Repair History" in res.data


def test_add_repair_via_form(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        mid = m.id

    login_admin(client)
    res = client.post(f"/admin/machines/{mid}/repairs", data={
        "description": "Replaced HDMI cable",
        "notes": "Works now",
        "error_id": "0",
        "repaired_at": "",
    }, follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        r = RepairHistory.query.first()
        assert r is not None
        assert r.description == "Replaced HDMI cable"


def test_delete_repair(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        u = User.query.filter_by(username="admin").first()
        r = RepairHistory(
            machine_id=m.id, performed_by=u.id,
            repaired_at=datetime.now(timezone.utc),
            description="Test",
        )
        db.session.add(r)
        db.session.commit()
        rid = r.id
        mid = m.id

    login_admin(client)
    res = client.post(f"/admin/machines/{mid}/repairs/{rid}/delete",
                      follow_redirects=False)
    assert res.status_code in (301, 302)

    with app.app_context():
        assert db.session.get(RepairHistory, rid) is None


# ---------- Change Logs ----------

def test_change_logs_admin_only(client):
    login_user(client)
    res = client.get("/admin/change-logs")
    assert res.status_code == 403


def test_change_logs_page_renders(client, app):
    with app.app_context():
        db.session.add(ChangeLog(
            entity="machines", record_id=1, version=1, action="CREATE",
        ))
        db.session.commit()

    login_admin(client)
    res = client.get("/admin/change-logs")
    assert res.status_code == 200
    assert b"Change Logs" in res.data


# ---------- Favorites page ----------

def test_favorites_page_requires_login(client):
    res = client.get("/favorites", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_favorites_page_empty(client):
    login_user(client)
    res = client.get("/favorites")
    assert res.status_code == 200
    assert b"No favorites yet" in res.data


def test_favorites_page_shows_items(client, app):
    with app.app_context():
        u = User.query.filter_by(username="a3user").first()
        m = Machine.query.filter_by(machine_code="DC001").first()
        db.session.add(Favorite(
            user_id=u.id, item_type="machine", machine_id=m.id,
        ))
        db.session.commit()

    login_user(client)
    res = client.get("/favorites")
    assert res.status_code == 200
    assert b"Dream Castle" in res.data


# ---------- Machine detail shows repair history ----------

def test_machine_detail_shows_repairs(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        u = User.query.filter_by(username="admin").first()
        db.session.add(RepairHistory(
            machine_id=m.id, performed_by=u.id,
            repaired_at=datetime.now(timezone.utc),
            description="Fixed HDMI",
        ))
        db.session.commit()
        mid = m.id

    login_user(client)
    res = client.get(f"/machine/{mid}")
    assert res.status_code == 200
    assert b"Repair History" in res.data
    assert b"Fixed HDMI" in res.data
