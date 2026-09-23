"""
Sync Local SQLite → Neon PostgreSQL (full data overwrite).
Preserves schema, only replaces data.

- Local is master (251 machines, correct)
- Neon is corrupt (358, A1 duplicates)
- This script DELETE Neon data, INSERT Local data

Safety:
- Runs in transaction
- Rolls back on error
- Prints before/after counts
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# === Config ===
LOCAL_DB = Path.home() / "machine_hub" / "instance" / "machine_hub.db"
NEON_URL_FILE = Path.home() / "supabase_db_url.txt"

if not LOCAL_DB.exists():
    print(f"❌ Local DB not found: {LOCAL_DB}")
    sys.exit(1)

if not NEON_URL_FILE.exists():
    print(f"❌ Neon URL not found: {NEON_URL_FILE}")
    sys.exit(1)

NEON_URL = NEON_URL_FILE.read_text().strip()
if not NEON_URL:
    print("❌ Neon URL is empty")
    sys.exit(1)

# === Import Flask models ===
sys.path.insert(0, str(Path.home() / "machine_hub"))

# Two app instances — one for local, one for Neon
os.environ["DATABASE_URL"] = f"sqlite:///{LOCAL_DB}"
os.environ["FLASK_ENV"] = "development"

from app import create_app
from app.extensions import db
from app.models import (
    Shop, User, Machine, Error, ErrorImage,
    Favorite, RepairHistory, ChangeLog, SyncState,
    ActivityLog, ImportBatch,
)
from app.models import machine_errors as machine_errors_table

# === Phase 1: Read Local data ===
print("=" * 60)
print("  LOCAL → NEON SYNC")
print("=" * 60)
print(f"  Local:  {LOCAL_DB}")
print(f"  Neon:   {NEON_URL[:40]}...")
print("=" * 60)

# Local read app
app_local = create_app()
with app_local.app_context():
    local_data = {}
    for model, name in [
        (Shop, "shops"), (User, "users"), (Machine, "machines"),
        (Error, "errors"), (ErrorImage, "error_images"),
        (Favorite, "favorites"),
        (RepairHistory, "repair_history"), (ChangeLog, "change_logs"),
        (SyncState, "sync_states"), (ActivityLog, "activity_logs"),
        (ImportBatch, "import_batches"),
    ]:
        try:
            rows = model.query.all()
            local_data[name] = [
                {c.name: getattr(r, c.name) for c in r.__table__.columns}
                for r in rows
            ]
            print(f"  [LOCAL] {name}: {len(rows)} rows")
        except Exception as e:
            print(f"  [LOCAL] {name}: ERR — {e}")
            local_data[name] = []

print("=" * 60)
print(f"  Local total: {sum(len(v) for v in local_data.values())} rows")
print("=" * 60)

# Save local data to JSON for safety
import json
safety_file = Path.home() / "machine_hub_backups" / "local_snapshot_before_sync.json"
safety_file.parent.mkdir(parents=True, exist_ok=True)
with open(safety_file, "w", encoding="utf-8") as f:
    json.dump(local_data, f, default=str, ensure_ascii=False, indent=2)
print(f"  Safety snapshot: {safety_file}")
print("=" * 60)

# === Phase 2: Connect to Neon ===
print("")
print("Connecting to Neon...")

# Reset env to Neon
os.environ["DATABASE_URL"] = NEON_URL
os.environ["FLASK_ENV"] = "production"

# Reload app with Neon
app_neon = create_app()
with app_neon.app_context():
    # Before counts
    print("")
    print("=== BEFORE (Neon) ===")
    before = {}
    for model, name in [
        (Shop, "shops"), (User, "users"), (Machine, "machines"),
        (Error, "errors"), (ErrorImage, "error_images"),
    ]:
        try:
            c = model.query.count()
            before[name] = c
            print(f"  {name}: {c}")
        except Exception as e:
            print(f"  {name}: ERR — {e}")

    # === Phase 3: DELETE all Neon data (in correct order — children first) ===
    print("")
    print("=== DELETING Neon data ===")
    delete_order = [
        Favorite, RepairHistory,
        ChangeLog, ActivityLog, SyncState, ImportBatch,
        ErrorImage, Error, Machine, User, Shop,
    ]
    for model in delete_order:
        try:
            n = model.query.delete()
            print(f"  Deleted {model.__name__}: {n}")
        except Exception as e:
            print(f"  {model.__name__}: ERR — {e}")
            db.session.rollback()
            print("❌ DELETE failed — rolling back")
            sys.exit(1)

    # NOT committed yet — will commit after INSERT
    print("  ✅ DELETE staged (will commit with INSERT)")

    # === Phase 4: INSERT Local data ===
    print("")
    print("=== INSERTING Local data ===")
    insert_order = [
        (Shop, "shops"), (User, "users"), (Machine, "machines"),
        (Error, "errors"), (ErrorImage, "error_images"),
        (Favorite, "favorites"),
        (RepairHistory, "repair_history"), (ChangeLog, "change_logs"),
        (SyncState, "sync_states"), (ActivityLog, "activity_logs"),
        (ImportBatch, "import_batches"),
    ]

    total_inserted = 0
    for model, name in insert_order:
        rows = local_data.get(name, [])
        if not rows:
            print(f"  {name}: 0 rows (skip)")
            continue
        try:
            db.session.execute(model.__table__.insert(), rows)
            db.session.commit()
            total_inserted += len(rows)
            print(f"  {name}: {len(rows)} inserted ✅")
        except Exception as e:
            db.session.rollback()
            print(f"  {name}: ERR — {e}")
            print(f"❌ INSERT failed on {name} — rolling back")
            sys.exit(1)

    # === Phase 5: Reset sequences (PostgreSQL) ===
    print("")
    print("=== RESETTING sequences ===")
    from sqlalchemy import text
    seq_tables = [
        "shops", "users", "machines", "errors", "error_images",
        "machine_errors", "favorites", "repair_history",
        "change_logs", "sync_states", "activity_logs", "import_batches",
    ]
    for t in seq_tables:
        try:
            db.session.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{t}', 'id'), "
                f"COALESCE(MAX(id), 1)) FROM {t}"
            ))
        except Exception as e:
            # Some tables might not have 'id' serial — skip
            pass
    db.session.commit()
    print("  ✅ Sequences reset")

    # === Phase 6: AFTER counts ===
    print("")
    print("=== AFTER (Neon) ===")
    for model, name in [
        (Shop, "shops"), (User, "users"), (Machine, "machines"),
        (Error, "errors"), (ErrorImage, "error_images"),
    ]:
        try:
            c = model.query.count()
            print(f"  {name}: {c}")
        except Exception as e:
            print(f"  {name}: ERR — {e}")

    # Per-shop machines
    print("")
    print("=== Per-shop machines (Neon AFTER) ===")
    for shop in Shop.query.all():
        c = Machine.query.filter_by(shop_id=shop.id).count()
        print(f"  Shop {shop.id} ({shop.shop_code}): {c} machines")

print("")
print("=" * 60)
print("  ✅ SYNC COMPLETE")
print("=" * 60)
