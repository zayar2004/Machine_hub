"""V1.9 — User UI tests."""
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

        # Machines
        m1 = Machine(shop_id=a3.id, machine_name="Dream Castle",
                     machine_code="DC001")
        m2 = Machine(shop_id=a4.id, machine_name="Epic",
                     machine_code="EP001")
        db.session.add_all([m1, m2])

        # Errors
        e1 = Error(error_code="E81", error_name="Screen Error",
                   error_fix="Check HDMI\nCheck power")
        db.session.add(e1)

        db.session.commit()

        # Link E81 to m1
        m1.errors.append(e1)
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


# ---------- Home ----------

def test_home_requires_login(client):
    res = client.get("/", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_home_renders_for_user(client):
    login_user(client)
    res = client.get("/")
    assert res.status_code == 200
    # V2 home — greeting or search hero marker
    data = res.data
    assert (
        b"search-hero" in data
        or b"home-v2-hero" in data
        or b"Machine Hub" in data
    )
    assert b"A3" in res.data
    # V2 home — ASCII-only markers
    assert (
        b"search-hero" in res.data
        or b"home-v2-hero" in res.data
        or b"Dream" in res.data
        or b"Machine Hub" in res.data
    )


def test_home_renders_for_admin(client):
    login_admin(client)
    res = client.get("/")
    assert res.status_code == 200
    assert b"Admin Dashboard" in res.data or b"Admin" in res.data


# ---------- Search page ----------

def test_search_page_requires_login(client):
    res = client.get("/search", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_search_empty_query(client):
    login_user(client)
    res = client.get("/search")
    assert res.status_code == 200
    assert (b"Search" in res.data) or (b"Type a machine" in res.data)


def test_search_machine_by_name(client):
    login_user(client)
    res = client.get("/search?q=Dream")
    assert res.status_code == 200
    assert b"Dream Castle" in res.data
    assert b"DC001" in res.data


def test_search_error_by_code(client):
    login_user(client)
    res = client.get("/search?q=E81")
    assert res.status_code == 200
    assert b"Screen Error" in res.data
    assert b"E81" in res.data


def test_search_no_results_message(client):
    login_user(client)
    res = client.get("/search?q=zzzzz")
    assert res.status_code == 200
    assert b"No results" in res.data


def test_search_user_cannot_see_other_shop_machines(client):
    """A3 user searching for EP001 (A4) should not see it."""
    login_user(client)
    res = client.get("/search?q=EP001")
    assert res.status_code == 200
    assert b"Epic" not in res.data


def test_search_admin_sees_other_shop_machines(client):
    login_admin(client)
    res = client.get("/search?q=EP001")
    assert res.status_code == 200
    assert b"Epic" in res.data


# ---------- Machine detail ----------

def test_machine_detail_requires_login(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        mid = m.id
    res = client.get(f"/machine/{mid}", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_machine_detail_shows_machine_and_errors(client, app):
    with app.app_context():
        m = Machine.query.filter_by(machine_code="DC001").first()
        mid = m.id

    login_user(client)
    res = client.get(f"/machine/{mid}")
    assert res.status_code == 200
    assert b"Dream Castle" in res.data
    assert b"DC001" in res.data
    assert b"Screen Error" in res.data


def test_machine_detail_blocks_other_shop_user(client, app):
    """A3 user trying to access A4 machine should get 403."""
    with app.app_context():
        m = Machine.query.filter_by(machine_code="EP001").first()
        mid = m.id

    login_user(client)
    res = client.get(f"/machine/{mid}")
    assert res.status_code == 403


def test_machine_detail_404(client):
    login_user(client)
    res = client.get("/machine/9999")
    assert res.status_code == 404


# ---------- Error detail ----------

def test_error_detail_requires_login(client, app):
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        eid = e.id
    res = client.get(f"/error/{eid}", follow_redirects=False)
    assert res.status_code in (301, 302)


def test_error_detail_global_for_user(client, app):
    """Errors are global — any logged-in user can see them."""
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        eid = e.id

    login_user(client)
    res = client.get(f"/error/{eid}")
    assert res.status_code == 200
    assert b"Screen Error" in res.data
    assert b"E81" in res.data
    assert b"Check HDMI" in res.data


def test_error_detail_shows_related_machines_scoped_to_user(client, app):
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        eid = e.id

    login_user(client)
    res = client.get(f"/error/{eid}")
    assert res.status_code == 200
    assert b"Dream Castle" in res.data


def test_error_detail_404(client):
    login_user(client)
    res = client.get("/error/9999")
    assert res.status_code == 404


# ---------- Login page redesign sanity ----------

def test_login_page_uses_design_system(client):
    res = client.get("/auth/login")
    assert res.status_code == 200
    # Design system CSS link should be present
    assert (b"user.css" in res.data) or (b"design-system.css" in res.data)
