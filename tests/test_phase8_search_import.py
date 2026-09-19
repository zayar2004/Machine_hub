"""V1.8 — Universal search + Excel import tests."""
from io import BytesIO

import pytest
from openpyxl import Workbook

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

        # Machines in A3 and A4
        db.session.add(Machine(shop_id=a3.id, machine_name="Dream Castle",
                               machine_code="DC001"))
        db.session.add(Machine(shop_id=a3.id, machine_name="Dream World",
                               machine_code="DW001"))
        db.session.add(Machine(shop_id=a4.id, machine_name="Epic",
                               machine_code="EP001"))

        # Errors (global)
        db.session.add(Error(error_code="E81", error_name="Screen Error",
                             error_fix="Check HDMI cable"))
        db.session.add(Error(error_code="E12", error_name="Cable Error"))

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


def make_machine_xlsx(rows):
    """rows: list of tuples (code, name, description, status)."""
    wb = Workbook()
    ws = wb.active
    ws.append(["machine_code", "machine_name", "description", "status"])
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def make_error_xlsx(rows):
    """rows: list of tuples (code, name, fix, explanation, status)."""
    wb = Workbook()
    ws = wb.active
    ws.append(["error_code", "error_name", "error_fix", "explanation", "status"])
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ---------- Search API ----------

def test_search_requires_login(client):
    res = client.get("/api/search?q=Dream")
    assert res.status_code in (301, 302)


def test_search_admin_sees_all_machines(client):
    login_admin(client)
    res = client.get("/api/search?q=Dream&type=machine")
    assert res.status_code == 200
    data = res.get_json()
    assert data["counts"]["machines"] == 2
    codes = {m["machine_code"] for m in data["machines"]}
    assert codes == {"DC001", "DW001"}


def test_search_user_only_sees_own_shop_machines(client):
    login_user(client)
    res = client.get("/api/search?q=&type=machine")
    assert res.status_code == 200
    data = res.get_json()
    codes = {m["machine_code"] for m in data["machines"]}
    assert "DC001" in codes
    assert "DW001" in codes
    assert "EP001" not in codes    # belongs to A4


def test_search_errors_are_global(client):
    login_user(client)
    res = client.get("/api/search?q=E81&type=error")
    assert res.status_code == 200
    data = res.get_json()
    assert data["counts"]["errors"] == 1
    assert data["errors"][0]["error_code"] == "E81"


def test_search_all_types(client):
    login_admin(client)
    res = client.get("/api/search?q=Dream")
    assert res.status_code == 200
    data = res.get_json()
    assert data["counts"]["machines"] == 2
    assert data["counts"]["errors"] == 0


def test_search_invalid_type(client):
    login_admin(client)
    res = client.get("/api/search?q=x&type=bogus")
    assert res.status_code == 400


# ---------- Admin search UI ----------

def test_admin_search_page(client):
    login_admin(client)
    res = client.get("/admin/search?q=Dream")
    assert res.status_code == 200
    assert b"Dream Castle" in res.data
    assert b"Dream World" in res.data


def test_admin_search_blocks_user(client):
    login_user(client)
    res = client.get("/admin/search")
    assert res.status_code == 403


# ---------- Excel import: machines ----------

def test_import_machines_upload_form(client):
    login_admin(client)
    res = client.get("/admin/import/machines")
    assert res.status_code == 200
    assert b"Import Machines" in res.data


def test_import_machines_preview(client, app):
    login_admin(client)
    with app.app_context():
        a3 = Shop.query.filter_by(shop_code="A3").first()
        a3_id = a3.id

    xlsx = make_machine_xlsx([
        ("MW001", "Marble World", "Test", "ACTIVE"),
        ("NW001", "New World", "", "ACTIVE"),
        ("DC001", "Dream Castle", "Updated", "ACTIVE"),  # existing
    ])

    res = client.post(
        "/admin/import/machines",
        data={"shop_id": str(a3_id), "excel_file": (xlsx, "test.xlsx")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert b"Marble World" in res.data
    assert b"New World" in res.data
    # Preview shows counts
    assert b"New" in res.data
    assert b"Update" in res.data


def test_import_machines_confirm(client, app):
    login_admin(client)
    with app.app_context():
        a3 = Shop.query.filter_by(shop_code="A3").first()
        a3_id = a3.id

    xlsx = make_machine_xlsx([
        ("MW001", "Marble World", "", "ACTIVE"),
        ("DC001", "Dream Castle Renamed", "", "ACTIVE"),  # update
    ])

    res = client.post(
        "/admin/import/machines/confirm",
        data={"shop_id": str(a3_id), "excel_file": (xlsx, "test.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert res.status_code in (301, 302)

    with app.app_context():
        assert Machine.query.filter_by(machine_code="MW001").count() == 1
        m = Machine.query.filter_by(machine_code="DC001").first()
        assert m.machine_name == "Dream Castle Renamed"


def test_import_machines_rejects_non_xlsx(client, app):
    login_admin(client)
    with app.app_context():
        a3 = Shop.query.filter_by(shop_code="A3").first()
        a3_id = a3.id

    res = client.post(
        "/admin/import/machines",
        data={"shop_id": str(a3_id),
              "excel_file": (BytesIO(b"not excel"), "test.csv")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 400
    assert b"xlsx" in res.data.lower()


# ---------- Excel import: errors ----------

def test_import_errors_upload_form(client):
    login_admin(client)
    res = client.get("/admin/import/errors")
    assert res.status_code == 200
    assert b"Import Errors" in res.data


def test_import_errors_confirm(client, app):
    login_admin(client)

    xlsx = make_error_xlsx([
        ("E99", "New Error", "Fix steps", "Explanation", "ACTIVE"),
        ("E81", "Screen Error Updated", "New fix", "", "ACTIVE"),
    ])

    res = client.post(
        "/admin/import/errors/confirm",
        data={"excel_file": (xlsx, "errors.xlsx")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert res.status_code in (301, 302)

    with app.app_context():
        assert Error.query.filter_by(error_code="E99").count() == 1
        e = Error.query.filter_by(error_code="E81").first()
        assert e.error_name == "Screen Error Updated"
        assert e.error_fix == "New fix"


def test_import_errors_blocks_user(client):
    login_user(client)
    res = client.get("/admin/import/errors")
    assert res.status_code == 403
