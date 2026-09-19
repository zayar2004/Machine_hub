"""V2 — Photos tests."""
from io import BytesIO

import pytest
from PIL import Image

from app import create_app
from app.extensions import db
from app.models import Shop, User, Machine, Error, ErrorImage


def make_image_bytes(fmt="JPEG", size=(100, 100), color=(255, 0, 0)):
    """Return BytesIO of a small test image."""
    img = Image.new("RGB", size, color)
    buf = BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


@pytest.fixture
def app():
    app = create_app("testing")
    # Use a temp upload dir
    import tempfile, os
    tmp_upload = tempfile.mkdtemp(prefix="mh_test_upload_")
    app.config["UPLOAD_FOLDER"] = tmp_upload

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
        db.session.add(m)

        e = Error(error_code="E81", error_name="Screen Error",
                  error_fix="Check HDMI")
        db.session.add(e)

        db.session.commit()

        m.errors.append(e)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()

    # Cleanup temp dir
    import shutil
    shutil.rmtree(tmp_upload, ignore_errors=True)


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


# ---------- Model ----------

def test_error_image_model(app):
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        img = ErrorImage(
            error_id=e.id,
            image_path="errors/E81/test.jpg",
            caption="Test photo",
            sort_order=0,
            file_size=1234,
            width=800,
            height=600,
        )
        db.session.add(img)
        db.session.commit()

        assert img.id is not None
        assert img.error.error_code == "E81"
        assert len(e.images) == 1


# ---------- Permissions ----------

def test_photos_page_requires_admin(client, app):
    login_user(client)
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        eid = e.id
    res = client.get(f"/admin/errors/{eid}/photos")
    assert res.status_code == 403


def test_photos_page_renders_for_admin(client, app):
    login_admin(client)
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        eid = e.id
    res = client.get(f"/admin/errors/{eid}/photos")
    assert res.status_code == 200
    assert b"Photos" in res.data
    assert b"Upload" in res.data


# ---------- Upload ----------

def test_photo_upload_jpeg(client, app):
    login_admin(client)
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        eid = e.id

    img_bytes = make_image_bytes("JPEG", (200, 150))
    data = {
        "images": (img_bytes, "test.jpg"),
        "caption": "Test caption",
    }
    res = client.post(
        f"/admin/errors/{eid}/photos",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert res.status_code in (301, 302)

    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        assert len(e.images) == 1
        img = e.images[0]
        assert img.caption == "Test caption"
        assert img.width == 200
        assert img.height == 150
        assert img.file_size > 0


def test_photo_upload_png(client, app):
    login_admin(client)
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        eid = e.id

    img_bytes = make_image_bytes("PNG", (120, 80))
    data = {"images": (img_bytes, "test.png")}
    res = client.post(
        f"/admin/errors/{eid}/photos",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert res.status_code in (301, 302)

    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        assert len(e.images) == 1


def test_photo_upload_rejects_invalid_extension(client, app):
    login_admin(client)
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        eid = e.id

    data = {"images": (BytesIO(b"not an image"), "test.txt")}
    res = client.post(
        f"/admin/errors/{eid}/photos",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert res.status_code in (301, 302)

    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        assert len(e.images) == 0  # rejected


def test_photo_upload_rejects_corrupt_image(client, app):
    login_admin(client)
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        eid = e.id

    # .jpg extension but not a real image
    data = {"images": (BytesIO(b"garbage bytes"), "test.jpg")}
    res = client.post(
        f"/admin/errors/{eid}/photos",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert res.status_code in (301, 302)

    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        assert len(e.images) == 0


# ---------- Edit ----------

def test_photo_edit_caption(client, app):
    login_admin(client)
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        eid = e.id
        # Add image directly
        img = ErrorImage(error_id=e.id, image_path="errors/E81/test.jpg",
                         sort_order=0)
        db.session.add(img)
        db.session.commit()
        img_id = img.id

    res = client.post(
        f"/admin/errors/{eid}/photos/{img_id}/edit",
        data={"caption": "Updated caption", "sort_order": "5"},
        follow_redirects=False,
    )
    assert res.status_code in (301, 302)

    with app.app_context():
        img = db.session.get(ErrorImage, img_id)
        assert img.caption == "Updated caption"
        assert img.sort_order == 5


# ---------- Delete ----------

def test_photo_delete(client, app):
    login_admin(client)
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        eid = e.id
        img = ErrorImage(error_id=e.id, image_path="errors/E81/missing.jpg",
                         sort_order=0)
        db.session.add(img)
        db.session.commit()
        img_id = img.id

    res = client.post(
        f"/admin/errors/{eid}/photos/{img_id}/delete",
        follow_redirects=False,
    )
    assert res.status_code in (301, 302)

    with app.app_context():
        assert db.session.get(ErrorImage, img_id) is None


# ---------- User can view photos ----------

def test_user_error_detail_shows_photos(client, app):
    """User sees photo thumbnails on error detail page."""
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        eid = e.id
        img = ErrorImage(error_id=e.id, image_path="errors/E81/thumb.jpg",
                         sort_order=0)
        db.session.add(img)
        db.session.commit()

    login_user(client)
    res = client.get(f"/error/{eid}")
    assert res.status_code == 200
    assert b"Photos" in res.data


# ---------- Serve upload ----------

def test_serve_upload_requires_login(client):
    res = client.get("/admin/uploads/errors/E81/x.jpg", follow_redirects=False)
    assert res.status_code in (301, 302)


# ---------- Sorting ----------

def test_photo_sort_order_respected(app):
    with app.app_context():
        e = Error.query.filter_by(error_code="E81").first()
        db.session.add(ErrorImage(error_id=e.id, image_path="a.jpg", sort_order=2))
        db.session.add(ErrorImage(error_id=e.id, image_path="b.jpg", sort_order=0))
        db.session.add(ErrorImage(error_id=e.id, image_path="c.jpg", sort_order=1))
        db.session.commit()

        e = Error.query.filter_by(error_code="E81").first()
        paths = [img.image_path for img in e.images]
        assert paths == ["b.jpg", "c.jpg", "a.jpg"]


# =========================================================
# PWA tests (Part C)
# =========================================================

def test_manifest_served(client):
    res = client.get("/static/manifest.json")
    assert res.status_code == 200
    data = res.get_json()
    assert data["name"] == "Machine Hub"
    assert data["short_name"] == "MachineHub"
    assert data["display"] == "standalone"
    assert len(data["icons"]) >= 2


def test_service_worker_served(client):
    res = client.get("/static/js/service-worker.js")
    assert res.status_code == 200
    assert b"VERSION" in res.data
    assert b"caches" in res.data


def test_design_system_css_served(client):
    """V5: user.css is the new design system."""
    res = client.get("/static/css/user.css")
    assert res.status_code == 200
    assert b"--accent" in res.data or b"--primary" in res.data


def test_theme_js_served(client):
    res = client.get("/static/js/theme.js")
    assert res.status_code == 200


def test_pwa_icons_exist(client):
    res = client.get("/static/icons/icon-192.png")
    assert res.status_code == 200
    assert res.data[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic

    res = client.get("/static/icons/icon-512.png")
    assert res.status_code == 200


def test_login_page_has_manifest_link(client):
    res = client.get("/auth/login")
    assert res.status_code == 200
    assert b"manifest.json" in res.data
