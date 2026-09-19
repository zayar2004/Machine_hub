"""Photo migration v3 — robust with verification."""
import os
import base64
import mimetypes
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


print("=" * 60)
print("STEP 1 — Read local photos")
print("=" * 60)

os.environ.pop("DATABASE_URL", None)

from app import create_app
from app.models import ErrorImage as LocalImg

local_app = create_app()

photos = []
with local_app.app_context():
    for img in LocalImg.query.all():
        rel = (img.image_path or "").lstrip("/")
        if rel.startswith("uploads/"):
            rel = rel[8:]
        full = ROOT / "uploads" / rel

        if not full.is_file():
            print(f"  ✗ id={img.id} MISSING FILE: {full}")
            continue

        data = full.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        mime = mimetypes.guess_type(str(full))[0] or "image/jpeg"

        photos.append({
            "id": img.id,
            "error_id": img.error_id,
            "image_path": img.image_path,
            "b64": b64,
            "mime": mime,
            "size": len(data),
        })
        print(f"  ✓ id={img.id} | {rel} | {len(data)//1024}KB")

print(f"\n→ Loaded {len(photos)} photos")


print()
print("=" * 60)
print("STEP 2 — Connect remote Postgres")
print("=" * 60)

url_file = Path.home() / "render_db_url.txt"
url = url_file.read_text().strip()
host = url.split("@")[1].split("/")[0] if "@" in url else "?"
print(f"  Host: {host}")

url_pg = url.replace("postgresql://", "postgresql+pg8000://", 1)
os.environ["DATABASE_URL"] = url_pg


print()
print("=" * 60)
print("STEP 3 — Remote state BEFORE")
print("=" * 60)

from app import create_app as create_remote
from app.extensions import db
from app.models import ErrorImage as RemoteImg

remote_app = create_remote()

with remote_app.app_context():
    before = RemoteImg.query.all()
    for img in before:
        dl = len(img.image_data) if img.image_data else 0
        print(f"  id={img.id} | error_id={img.error_id} | path={img.image_path} | data_len={dl}")

    print(f"\n  Total remote images: {len(before)}")


print()
print("=" * 60)
print("STEP 4 — Match + Update")
print("=" * 60)

with remote_app.app_context():
    matched = 0
    created = 0

    for p in photos:
        # Strategy 1: Match by id
        img = db.session.get(RemoteImg, p["id"])

        # Strategy 2: Match by image_path if id mismatch
        if img is None or img.error_id != p["error_id"]:
            # Try path-based match
            img = RemoteImg.query.filter_by(image_path=p["image_path"]).first()

        if img is None:
            # Strategy 3: Create new row
            print(f"  + CREATE id={p['id']} path={p['image_path']}")
            img = RemoteImg(
                id=p["id"],
                error_id=p["error_id"],
                image_path=p["image_path"],
                image_data=p["b64"],
                mime_type=p["mime"],
                sort_order=0,
            )
            db.session.add(img)
            created += 1
        else:
            print(f"  ↻ UPDATE id={img.id} path={img.image_path} → data_len={len(p['b64'])}")
            img.image_data = p["b64"]
            img.mime_type = p["mime"]
            matched += 1

    try:
        db.session.commit()
        print(f"\n✓ Commit OK — matched={matched}, created={created}")
    except Exception as e:
        db.session.rollback()
        print(f"\n❌ Commit FAILED: {e}")
        raise


print()
print("=" * 60)
print("STEP 5 — Remote state AFTER")
print("=" * 60)

with remote_app.app_context():
    for img in RemoteImg.query.all():
        dl = len(img.image_data) if img.image_data else 0
        print(f"  id={img.id} | error_id={img.error_id} | path={img.image_path} | data_len={dl}")


print()
print("=" * 60)
print("✅ Migration v3 done")
print("=" * 60)
