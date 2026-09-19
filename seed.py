"""Seed script — create initial shop + admin user + sync states.

Run:  python seed.py
"""
from app import create_app
from app.extensions import db
from app.models import Shop, User, SyncState, ChangeLog


def seed():
    app = create_app()
    with app.app_context():
        # --- Shop A3 ---
        a3 = Shop.query.filter_by(shop_code="A3").first()
        if a3 is None:
            a3 = Shop(shop_code="A3", shop_name="Shop A3")
            db.session.add(a3)
            db.session.commit()
            print("✓ Created shop A3")
        else:
            print("• Shop A3 already exists")

        # --- Admin user ---
        admin = User.query.filter_by(username="admin").first()
        if admin is None:
            admin = User(
                name="System Admin",
                username="admin",
                role=User.ROLE_ADMIN,
                shop_id=None,
                status=User.STATUS_ACTIVE,
            )
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            print("✓ Created admin user (username=admin, password=admin123)")
        else:
            print("• Admin user already exists")

        # --- Regular user in A3 ---
        user1 = User.query.filter_by(username="a3user").first()
        if user1 is None:
            user1 = User(
                name="A3 Staff",
                username="a3user",
                role=User.ROLE_USER,
                shop_id=a3.id,
                status=User.STATUS_ACTIVE,
            )
            user1.set_password("user123")
            db.session.add(user1)
            db.session.commit()
            print("✓ Created A3 user (username=a3user, password=user123)")
        else:
            print("• A3 user already exists")

        # --- Ensure sync_state rows exist ---
        for entity in ("shops", "users", "machines", "errors", "error_images", "repair_history"):
            row = SyncState.query.filter_by(entity=entity).first()
            if row is None:
                row = SyncState(entity=entity, current_version=0)
                db.session.add(row)
        db.session.commit()
        print("✓ Sync states initialized")

        # --- Ensure initial changelog for existing records ---
        for entity, model in (
            ("shops", Shop),
            ("users", User),
        ):
            for rec in model.query.all():
                existing = ChangeLog.query.filter_by(
                    entity=entity, record_id=rec.id
                ).first()
                if existing is None:
                    version = SyncState.bump(entity)
                    db.session.add(ChangeLog(
                        entity=entity,
                        record_id=rec.id,
                        version=version,
                        action="CREATE",
                    ))
        db.session.commit()
        print("✓ Initial changelog created")

        print("\n--- Final state ---")
        print(f"Shops: {Shop.query.count()}")
        print(f"Users: {User.query.count()}")
        for e in ("shops", "users", "machines", "errors", "error_images", "repair_history"):
            v = SyncState.get_version(e)
            print(f"  {e}: v{v}")


if __name__ == "__main__":
    seed()
