"""Migrate local SQLite → Neon Postgres."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def read_local():
    os.environ.pop("DATABASE_URL", None)
    from app import create_app
    from app.models import Shop, User, Machine, Error, ErrorImage

    app = create_app()
    data = {}
    with app.app_context():
        data["shops"] = [{
            "id": s.id, "shop_code": s.shop_code, "shop_name": s.shop_name,
            "status": s.status,
        } for s in Shop.query.all()]
        data["users"] = [{
            "id": u.id, "username": u.username, "name": u.name,
            "password_hash": u.password_hash, "role": u.role,
            "status": u.status, "shop_id": u.shop_id,
        } for u in User.query.all()]
        data["machines"] = [{
            "id": m.id, "shop_id": m.shop_id,
            "machine_code": m.machine_code, "machine_name": m.machine_name,
            "status": m.status,
            "description": getattr(m, "description", None),
        } for m in Machine.query.all()]
        data["errors"] = [{
            "id": e.id, "error_code": e.error_code, "error_name": e.error_name,
            "error_fix": e.error_fix, "explanation": e.explanation,
            "category": e.category, "status": e.status,
            "machine_name": getattr(e, "machine_name", None),
        } for e in Error.query.all()]
        data["error_images"] = [{
            "id": i.id, "error_id": i.error_id, "image_path": i.image_path,
            "caption": i.caption, "sort_order": i.sort_order,
            "image_data": i.image_data, "mime_type": i.mime_type,
            "file_size": i.file_size, "width": i.width, "height": i.height,
        } for i in ErrorImage.query.all()]
    return data


def write_remote(data):
    url = Path.home().joinpath("neon_db_url.txt").read_text().strip()
    os.environ["DATABASE_URL"] = url

    from app import create_app
    from app.extensions import db
    from app.models import Shop, User, Machine, Error, ErrorImage

    app = create_app()
    with app.app_context():
        print("  Clearing Neon...")
        db.session.query(ErrorImage).delete()
        db.session.query(Error).delete()
        db.session.query(Machine).delete()
        db.session.query(User).delete()
        db.session.query(Shop).delete()
        db.session.commit()
        print("  ✓ Cleared")

        for row in data["shops"]:
            db.session.add(Shop(**row))
        db.session.commit()
        print(f"  ✓ shops: {Shop.query.count()}")

        for row in data["users"]:
            db.session.add(User(**row))
        db.session.commit()
        print(f"  ✓ users: {User.query.count()}")

        for row in data["machines"]:
            db.session.add(Machine(**row))
        db.session.commit()
        print(f"  ✓ machines: {Machine.query.count()}")

        for row in data["errors"]:
            db.session.add(Error(**row))
        db.session.commit()
        print(f"  ✓ errors: {Error.query.count()}")

        for row in data["error_images"]:
            db.session.add(ErrorImage(**row))
        db.session.commit()
        print(f"  ✓ images: {ErrorImage.query.count()}")


if __name__ == "__main__":
    print("=" * 60)
    print("STEP 1: Read local SQLite")
    print("=" * 60)
    data = read_local()
    for k, v in data.items():
        print(f"  {k}: {len(v)}")

    print()
    print("=" * 60)
    print("STEP 2: Write to Neon")
    print("=" * 60)
    write_remote(data)

    print()
    print("✅ Migration complete!")
