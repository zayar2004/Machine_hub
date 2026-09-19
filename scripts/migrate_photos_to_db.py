"""
Migrate local error photos → Base64 → Postgres image_data column.

Usage:
    cd ~/machine_hub
    source venv/bin/activate
    python scripts/migrate_photos_to_db.py
"""
import os
import base64
import mimetypes
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def read_local_photos():
    """Read all error_images from local SQLite + read file bytes."""
    os.environ.pop("DATABASE_URL", None)

    from app import create_app
    from app.models import ErrorImage

    app = create_app()
    photos = []

    with app.app_context():
        for img in ErrorImage.query.all():
            # image_path: 'errors/ERROR_1/xxx.jpg'
            rel = (img.image_path or "").lstrip("/")
            if rel.startswith("uploads/"):
                rel = rel[8:]
            full = ROOT / "uploads" / rel

            if not full.is_file():
                print(f"  ⚠ missing: {full}")
                continue

            data = full.read_bytes()
            b64 = base64.b64encode(data).decode("ascii")
            mime = mimetypes.guess_type(str(full))[0] or "image/jpeg"

            photos.append({
                "id": img.id,
                "error_id": img.error_id,
                "image_path": img.image_path,
                "caption": img.caption,
                "sort_order": img.sort_order,
                "b64": b64,
                "mime": mime,
                "size": len(data),
            })

    return photos


def write_to_remote(photos):
    """Update image_data + mime_type in remote Postgres."""
    from pathlib import Path as P
    url = P.home().joinpath("render_db_url.txt").read_text().strip()
    url_pg = url.replace("postgresql://", "postgresql+pg8000://", 1)
    os.environ["DATABASE_URL"] = url_pg

    from app import create_app
    from app.extensions import db
    from app.models import ErrorImage

    app = create_app()
    count = 0

    with app.app_context():
        for p in photos:
            img = db.session.get(ErrorImage, p["id"])
            if img is None:
                print(f"  ⚠ not in remote: id={p['id']}")
                continue
            img.image_data = p["b64"]
            img.mime_type = p["mime"]
            count += 1
            print(f"  ✓ id={p['id']} ({p['size'] // 1024}KB) → {p['mime']}")

        db.session.commit()
        print(f"\n✓ Updated {count} photos in remote Postgres")


if __name__ == "__main__":
    print("=" * 60)
    print("STEP 1: Read local photos")
    print("=" * 60)
    photos = read_local_photos()
    print(f"  → {len(photos)} photos ready")
    for p in photos:
        print(f"     id={p['id']} {p['image_path']} ({p['size']//1024}KB)")

    print()
    print("=" * 60)
    print("STEP 2: Write base64 to remote Postgres")
    print("=" * 60)
    write_to_remote(photos)

    print()
    print("=" * 60)
    print("✅ Photo migration complete!")
    print("=" * 60)
