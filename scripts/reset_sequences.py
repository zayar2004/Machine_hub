"""Reset Postgres sequences to MAX(id) — after explicit-id migration."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

url = Path.home().joinpath("neon_db_url.txt").read_text().strip()
os.environ["DATABASE_URL"] = url

from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    tables = [
        "shops", "users", "machines", "errors", "error_images",
        "import_batches", "repair_history", "favorites",
        "activity_logs", "change_logs", "sync_states",
    ]
    for tbl in tables:
        try:
            db.session.execute(text(f"""
                SELECT setval(
                    pg_get_serial_sequence('{tbl}', 'id'),
                    COALESCE((SELECT MAX(id) FROM {tbl}), 0) + 1,
                    false
                )
            """))
            db.session.commit()
            print(f"✓ {tbl}")
        except Exception as e:
            print(f"  ⚠ {tbl}: {str(e)[:80]}")
            db.session.rollback()
    print("\n✓ Sequences reset")
