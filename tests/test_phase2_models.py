"""V1.2 — Model tests: creation, uniqueness, relationships."""
import pytest

from app import create_app
from app.extensions import db
from app.models import Shop, User, Machine, Error


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


# ---------- Shop ----------

def test_create_shop(app):
    with app.app_context():
        s = Shop(shop_code="A3", shop_name="Shop A3")
        db.session.add(s)
        db.session.commit()
        assert s.id is not None
        assert s.status == Shop.STATUS_ACTIVE


def test_shop_code_unique(app):
    with app.app_context():
        db.session.add(Shop(shop_code="A3", shop_name="Shop A3"))
        db.session.commit()
        db.session.add(Shop(shop_code="A3", shop_name="Other"))
        with pytest.raises(Exception):
            db.session.commit()


# ---------- User ----------

def test_user_password_hashing(app):
    with app.app_context():
        u = User(name="A", username="a", role=User.ROLE_USER)
        u.set_password("secret")
        assert u.password_hash != "secret"
        assert u.check_password("secret") is True
        assert u.check_password("wrong") is False


def test_admin_role_flag(app):
    with app.app_context():
        admin = User(name="Ad", username="ad", role=User.ROLE_ADMIN)
        admin.set_password("x")
        user = User(name="U", username="u", role=User.ROLE_USER)
        user.set_password("x")
        db.session.add_all([admin, user])
        db.session.commit()
        assert admin.is_admin is True
        assert user.is_admin is False


def test_user_belongs_to_shop(app):
    with app.app_context():
        s = Shop(shop_code="A3", shop_name="Shop A3")
        db.session.add(s)
        db.session.commit()
        u = User(name="Staff", username="staff", shop_id=s.id, role=User.ROLE_USER)
        u.set_password("x")
        db.session.add(u)
        db.session.commit()
        assert u.shop is not None
        assert u.shop.shop_code == "A3"


# ---------- Machine ----------

def test_machine_code_unique_per_shop(app):
    with app.app_context():
        s1 = Shop(shop_code="A3", shop_name="Shop A3")
        s2 = Shop(shop_code="A4", shop_name="Shop A4")
        db.session.add_all([s1, s2])
        db.session.commit()

        # Same code in different shops — OK
        m1 = Machine(shop_id=s1.id, machine_name="Dream Castle", machine_code="DC001")
        m2 = Machine(shop_id=s2.id, machine_name="Dream Castle", machine_code="DC001")
        db.session.add_all([m1, m2])
        db.session.commit()
        assert m1.id and m2.id

        # Same code within same shop — FAIL
        m3 = Machine(shop_id=s1.id, machine_name="Duplicate", machine_code="DC001")
        db.session.add(m3)
        with pytest.raises(Exception):
            db.session.commit()


# ---------- Error ----------

def test_error_code_unique_global(app):
    with app.app_context():
        e1 = Error(error_code="E81", error_name="Screen Error")
        db.session.add(e1)
        db.session.commit()
        e2 = Error(error_code="E81", error_name="Other")
        db.session.add(e2)
        with pytest.raises(Exception):
            db.session.commit()


# ---------- M2M ----------

def test_machine_error_m2m(app):
    with app.app_context():
        s = Shop(shop_code="A3", shop_name="Shop A3")
        db.session.add(s)
        db.session.commit()

        m = Machine(shop_id=s.id, machine_name="Dream Castle", machine_code="DC001")
        e = Error(error_code="E81", error_name="Screen Error")
        db.session.add_all([m, e])
        db.session.commit()

        m.errors.append(e)
        db.session.commit()

        assert e in m.errors
        assert m in e.machines


# ---------- Status ----------

def test_archive_instead_of_delete(app):
    with app.app_context():
        s = Shop(shop_code="A3", shop_name="Shop A3")
        db.session.add(s)
        db.session.commit()
        s.status = Shop.STATUS_ARCHIVED
        db.session.commit()
        assert s.is_active() is False
        assert Shop.query.count() == 1
