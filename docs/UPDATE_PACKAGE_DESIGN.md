# Machine Hub — Update Package Design

## Purpose
Offline data transfer: Admin → User
- No Internet required
- Manual share (USB, email, Bluetooth)
- Version control
- Rollback

## Package Format
knowledge_update_1.0.0.zip
- manifest.json
- data/shops.json
- data/machines.json
- data/errors.json
- data/error_images.json
- data/machine_errors.json
- images/<error_id>/<photo>.jpg
- checksums.txt

## Manifest Schema
{
  "app": "Machine Hub",
  "package_version": "1.0.0",
  "data_version": 1,
  "created_at": "2026-09-23T17:00:00Z",
  "created_by": "admin",
  "shop_ids": [1, 3, 4],
  "counts": {
    "shops": 3,
    "machines": 251,
    "errors": 2,
    "error_images": 4
  },
  "checksums": {
    "data/machines.json": "sha256:...",
    "images/error_1/1.jpg": "sha256:..."
  }
}

## Version Scheme
MAJOR.MINOR.PATCH
- 1.0.0 initial
- 1.0.1 patch
- 1.1.0 minor
- 2.0.0 major

## Validation Rules
- manifest.json required
- version format: X.Y.Z
- checksums must match
- shop_ids authorized
- No duplicate machine_code per shop
- Image size < 10 MB

## User Import Flow
1. Select file (.zip)
2. Validate (manifest + checksums)
3. Show changes
4. Backup (auto)
5. Apply
6. Verify
7. Complete
If fail → Rollback

## Admin Export Flow
1. Select shops
2. Options (machines, errors, images, users)
3. Preview (counts, size)
4. Generate (.zip)
5. Download

## Rollback
- Auto-backup before apply
- Restore on fail
- Keep last 3 versions
