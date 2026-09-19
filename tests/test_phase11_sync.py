"""V3 — Sync API tests."""
import pytest

from app import create_app
from app.extensions import db
from app.models import (
    Shop, User, Machine, Error, SyncState, ChangeLog,
)
from app.sync import record_change


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

        # Initialize sync states
        for entity in ("shops", "users", "machines", "errors", "error_images"):
            db.session.add(SyncState(entity=entity, current_version=0))
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


# ---------- SyncState / ChangeLog ----------

def test_sync_state_bump(app):
    with app.app_context():
        v1 = SyncState.bump("machines")
        v2 = SyncState.bump("machines")
        assert v1 == 1
        assert v2 == 2
        assert SyncState.get_version("machines") == 2


def test_record_change_creates_log(app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        v = record_change("machines", m.id, "CREATE")
        db.session.commit()
        assert v == 1

        log = ChangeLog.query.filter_by(entity="machines", record_id=m.id).first()
        assert log is not None
        assert log.version == 1
        assert log.action == "CREATE"


def test_record_change_ignores_unknown_entity(app):
    with app.app_context():
        v = record_change("bogus", 1, "CREATE")
        assert v == 0


# ---------- /api/sync/version ----------

def test_sync_version_requires_login(client):
    res = client.get("/api/sync/version", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_sync_version_returns_entities(client):
    login_admin(client)
    res = client.get("/api/sync/version")
    assert res.status_code == 200
    data = res.get_json()
    assert "server_version" in data
    assert "entities" in data
    assert set(data["entities"].keys()) == {
        "shops", "users", "machines", "errors", "error_images",
        "repair_history",
    }


# ---------- /api/sync/changes ----------

def test_sync_changes_requires_login(client):
    res = client.get("/api/sync/changes", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_sync_changes_empty_when_no_changes(client):
    login_admin(client)
    res = client.get("/api/sync/changes?since=0")
    assert res.status_code == 200
    data = res.get_json()
    assert data["changes"]["machines"] == []


def test_sync_changes_returns_new_machine(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        record_change("machines", m.id, "CREATE")
        db.session.commit()

    login_admin(client)
    res = client.get("/api/sync/changes?since=0")
    data = res.get_json()
    assert len(data["changes"]["machines"]) == 1
    assert data["changes"]["machines"][0]["machine_code"] == "DC001"


def test_sync_changes_incremental(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        v = record_change("machines", m.id, "CREATE")
        db.session.commit()

    login_admin(client)

    # Since version 0 → get changes
    res = client.get("/api/sync/changes?since=0")
    assert len(res.get_json()["changes"]["machines"]) == 1

    # Since version 1 → no changes
    res = client.get("/api/sync/changes?since=1")
    assert len(res.get_json()["changes"]["machines"]) == 0


def test_sync_changes_user_scoped_machines(client, app):
    """Non-admin user should only see their own shop's machines."""
    with app.app_context():
        for m in Machine.query.all():
            record_change("machines", m.id, "CREATE")
        db.session.commit()

    login_user(client)
    res = client.get("/api/sync/changes?since=0")
    data = res.get_json()
    codes = {m["machine_code"] for m in data["changes"]["machines"]}
    assert "DC001" in codes
    assert "EP001" not in codes    # A4 machine filtered


def test_sync_changes_errors_global(client, app):
    """Errors are global — even for non-admin users."""
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        record_change("errors", e.id, "CREATE")
        db.session.commit()

    login_user(client)
    res = client.get("/api/sync/changes?since=0")
    data = res.get_json()
    assert len(data["changes"]["errors"]) == 1


def test_sync_changes_user_list_hidden_from_non_admin(client, app):
    with app.app_context():
        for u in User.query.all():
            record_change("users", u.id, "CREATE")
        db.session.commit()

    login_user(client)
    res = client.get("/api/sync/changes?since=0")
    data = res.get_json()
    assert data["changes"]["users"] == []


def test_sync_changes_user_list_visible_to_admin(client, app):
    with app.app_context():
        for u in User.query.all():
            record_change("users", u.id, "CREATE")
        db.session.commit()

    login_admin(client)
    res = client.get("/api/sync/changes?since=0")
    data = res.get_json()
    assert len(data["changes"]["users"]) == 2


def test_sync_changes_has_more_flag(client, app):
    with app.app_context():
        for m in Machine.query.all():
            record_change("machines", m.id, "CREATE")
        db.session.commit()

    login_admin(client)
    # Limit 1 → has_more=True
    res = client.get("/api/sync/changes?since=0&limit=1")
    data = res.get_json()
    assert data["has_more"] is True


def test_sync_changes_invalid_since_defaults_zero(client):
    login_admin(client)
    res = client.get("/api/sync/changes?since=abc")
    assert res.status_code == 200
