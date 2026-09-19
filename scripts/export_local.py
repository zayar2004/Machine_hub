"""STEP 1: Export local SQLite → JSON."""
import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.pop("DATABASE_URL", None)

from app import create_app
from app.models import Shop, User, Machine, Error, ErrorImage

app = create_app()
with app.app_context():
    data = {
        "shops": [{
            "id": s.id, "shop_code": s.shop_code, "shop_name": s.shop_name,
            "status": s.status,
        } for s in Shop.query.all()],
        "users": [{
            "id": u.id, "username": u.username, "name": u.name,
            "password_hash": u.password_hash, "role": u.role,
            "status": u.status, "shop_id": u.shop_id,
        } for u in User.query.all()],
        "machines": [{
            "id": m.id, "shop_id": m.shop_id,
            "machine_code": m.machine_code, "machine_name": m.machine_name,
            "status": m.status,
            "description": getattr(m, "description", None),
        } for m in Machine.query.all()],
        "errors": [{
            "id": e.id, "error_code": e.error_code, "error_name": e.error_name,
            "error_fix": e.error_fix, "explanation": e.explanation,
            "category": e.category, "status": e.status,
            "machine_name": getattr(e, "machine_name", None),
        } for e in Error.query.all()],
        "error_images": [{
            "id": i.id, "error_id": i.error_id, "image_path": i.image_path,
            "caption": i.caption, "sort_order": i.sort_order,
            "image_data": i.image_data, "mime_type": i.mime_type,
            "file_size": i.file_size, "width": i.width, "height": i.height,
        } for i in ErrorImage.query.all()],
    }

out = Path.home() / "machine_hub_export.json"
out.write_text(json.dumps(data, indent=2, default=str))

for k, v in data.items():
    print(f"  {k}: {len(v)}")
print(f"\n✓ Exported to: {out}")
