"""STEP 2: Import JSON → Neon (isolated process)."""
import os
import sys
import json
import ssl
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load JSON
json_path = Path.home() / "machine_hub_export.json"
if not json_path.exists():
    print(f"❌ Not found: {json_path}")
    print("   Run scripts/export_local.py first.")
    sys.exit(1)
data = json.loads(json_path.read_text())

# Set Neon URL BEFORE any app imports
url = Path.home().joinpath("neon_db_url.txt").read_text().strip()
os.environ["DATABASE_URL"] = url

from app import create_app
from app.extensions import db
from app.models import Shop, User, Machine, Error, ErrorImage

app = create_app()
with app.app_context():
    print("Clearing Neon...")
    db.session.query(ErrorImage).delete()
    db.session.query(Error).delete()
    db.session.query(Machine).delete()
    db.session.query(User).delete()
    db.session.query(Shop).delete()
    db.session.commit()
    print("✓ Cleared")

    for row in data["shops"]:
        db.session.add(Shop(**row))
    db.session.commit()
    print(f"✓ shops: {Shop.query.count()}")

    for row in data["users"]:
        db.session.add(User(**row))
    db.session.commit()
    print(f"✓ users: {User.query.count()}")

    for row in data["machines"]:
        db.session.add(Machine(**row))
    db.session.commit()
    print(f"✓ machines: {Machine.query.count()}")

    for row in data["errors"]:
        db.session.add(Error(**row))
    db.session.commit()
    print(f"✓ errors: {Error.query.count()}")

    for row in data["error_images"]:
        db.session.add(ErrorImage(**row))
    db.session.commit()
    print(f"✓ images: {ErrorImage.query.count()}")

    print()
    print("Same-process verify:")
    print(f"  Shops: {Shop.query.count()}")
