"""
Machine Hub — Local SQLite → Render Postgres migration.

Usage:
    cd ~/machine_hub
    source venv/bin/activate
    python scripts/migrate_to_postgres.py

Requires:
    - pg8000 (installed)
    - ~/render_db_url.txt (External URL)
    - instance/machine_hub.db (Local DB)
"""
import os
import sys
import json
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---- STEP 1: Read local SQLite ----
print("=" * 60)
print("STEP 1: Read local SQLite")
print("=" * 60)

# Force SQLite for local
os.environ.pop("DATABASE_URL", None)

from app import create_app
from app.extensions import db
from app.models import (
    Shop, User, Machine, Error, ErrorImage,
    RepairHistory, Favorite,
)

LOCAL = create_app()
DATA = {}

with LOCAL.app_context():
    # Shops
    DATA["shops"] = [
        {
            "id": s.id,
            "shop_code": s.shop_code,
            "shop_name": s.shop_name,
            "status": s.status,
        }
        for s in Shop.query.all()
    ]
    print(f"  shops: {len(DATA['shops'])}")

    # Users
    DATA["users"] = [
        {
            "id": u.id,
            "username": u.username,
            "name": u.name,
            "password_hash": u.password_hash,
            "role": u.role,
            "status": u.status,
            "shop_id": u.shop_id,
        }
        for u in User.query.all()
    ]
    print(f"  users: {len(DATA['users'])}")

    # Machines
    DATA["machines"] = [
        {
            "id": m.id,
            "shop_id": m.shop_id,
            "machine_code": m.machine_code,
            "machine_name": m.machine_name,
            "status": m.status,
            "description": getattr(m, "description", None),
        }
        for m in Machine.query.all()
    ]
    print(f"  machines: {len(DATA['machines'])}")

    # Errors
    DATA["errors"] = [
        {
            "id": e.id,
            "error_code": e.error_code,
            "error_name": e.error_name,
            "error_fix": e.error_fix,
            "explanation": e.explanation,
            "category": e.category,
            "status": e.status,
            "machine_name": e.machine_name,
        }
        for e in Error.query.all()
    ]
    print(f"  errors: {len(DATA['errors'])}")

    # Error images (metadata only — files separate)
    DATA["error_images"] = [
        {
            "id": img.id,
            "error_id": img.error_id,
            "image_path": img.image_path,
            "caption": img.caption,
            "sort_order": img.sort_order,
        }
        for img in ErrorImage.query.all()
    ]
    print(f"  error_images: {len(DATA['error_images'])}")

# Save to JSON
OUT = ROOT / "scripts" / "local_data.json"
OUT.write_text(json.dumps(DATA, indent=2, default=str))
print(f"\n  → Saved: {OUT}")


# ---- STEP 2: Write to remote Postgres ----
print("\n" + "=" * 60)
print("STEP 2: Write to Render Postgres")
print("=" * 60)

# Read URL
URL_FILE = Path.home() / "render_db_url.txt"
if not URL_FILE.exists():
    print(f"❌ URL file not found: {URL_FILE}")
    sys.exit(1)

url = URL_FILE.read_text().strip()
if not url.startswith("postgresql://"):
    print(f"❌ Invalid URL — must start with postgresql://")
    sys.exit(1)

# Convert to pg8000 dialect
url_pg = url.replace("postgresql://", "postgresql+pg8000://", 1)
os.environ["DATABASE_URL"] = url_pg

print(f"  Target: {url.split('@')[1].split('/')[0] if '@' in url else '(unknown)'}")

REMOTE = create_app()
with REMOTE.app_context():
    # Ensure tables exist
    db.create_all()
    print("  ✓ Tables ensured")

    # Insert shops
    for row in DATA["shops"]:
        if not Shop.query.get(row["id"]):
            shop = Shop(
                id=row["id"],
                shop_code=row["shop_code"],
                shop_name=row["shop_name"],
                status=row["status"],
            )
            db.session.add(shop)
    db.session.commit()
    print(f"  ✓ shops inserted: {Shop.query.count()}")

    # Insert users
    for row in DATA["users"]:
        if not User.query.get(row["id"]):
            u = User(
                id=row["id"],
                username=row["username"],
                name=row["name"],
                password_hash=row["password_hash"],
                role=row["role"],
                status=row["status"],
                shop_id=row["shop_id"],
            )
            db.session.add(u)
    db.session.commit()
    print(f"  ✓ users inserted: {User.query.count()}")

    # Insert machines
    for row in DATA["machines"]:
        if not Machine.query.get(row["id"]):
            m = Machine(
                id=row["id"],
                shop_id=row["shop_id"],
                machine_code=row["machine_code"],
                machine_name=row["machine_name"],
                status=row["status"],
                description=row["description"],
            )
            db.session.add(m)
    db.session.commit()
    print(f"  ✓ machines inserted: {Machine.query.count()}")

    # Insert errors
    for row in DATA["errors"]:
        if not Error.query.get(row["id"]):
            e = Error(
                id=row["id"],
                error_code=row["error_code"],
                error_name=row["error_name"],
                error_fix=row["error_fix"],
                explanation=row["explanation"],
                category=row["category"],
                status=row["status"],
                machine_name=row["machine_name"],
            )
            db.session.add(e)
    db.session.commit()
    print(f"  ✓ errors inserted: {Error.query.count()}")

    # Insert error_images (metadata)
    for row in DATA["error_images"]:
        if not ErrorImage.query.get(row["id"]):
            img = ErrorImage(
                id=row["id"],
                error_id=row["error_id"],
                image_path=row["image_path"],
                caption=row["caption"],
                sort_order=row["sort_order"],
            )
            db.session.add(img)
    db.session.commit()
    print(f"  ✓ error_images inserted: {ErrorImage.query.count()}")

print("\n" + "=" * 60)
print("✅ Migration complete!")
print("=" * 60)
