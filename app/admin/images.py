"""Image upload + compression helpers for error photos."""
import os
import secrets
from io import BytesIO
from pathlib import Path

from PIL import Image
from werkzeug.utils import secure_filename


# ---------- Config ----------
MAX_WIDTH = 1600
MAX_HEIGHT = 1600
JPEG_QUALITY = 82
THUMB_SIZE = (400, 400)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


def allowed_image(filename: str) -> bool:
    if not filename:
        return False
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_EXTENSIONS


def _safe_name(original: str) -> str:
    """Generate a safe unique filename preserving extension."""
    ext = Path(original).suffix.lower()
    if ext == ".jpeg":
        ext = ".jpg"
    token = secrets.token_hex(12)
    return f"{token}{ext}"


def save_error_image(
    file_storage,
    upload_root: str,
    error_code: str,
) -> dict | None:
    """Save an uploaded image, compress it, and return metadata.

    Returns dict with:
      - image_path (relative, e.g. "errors/E81/abc123.jpg")
      - file_size
      - width
      - height

    Returns None on failure.
    """
    if not file_storage or not file_storage.filename:
        return None

    original_name = file_storage.filename
    if not allowed_image(original_name):
        return None

    # Read file into memory
    data = file_storage.read()
    if not data:
        return None

    # Open with Pillow
    try:
        img = Image.open(BytesIO(data))
        img.load()  # force decode (catches corrupt files)
    except Exception:
        return None

    # Convert mode for JPEG compatibility
    if img.mode in ("RGBA", "LA", "P"):
        # Flatten onto white background
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Resize if needed
    img.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.LANCZOS)

    # Prepare directory
    safe_code = secure_filename(error_code) or "misc"
    rel_dir = Path("errors") / safe_code
    abs_dir = Path(upload_root) / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    # Filename
    new_name = _safe_name(original_name)
    if new_name.lower().endswith(".png") and img.mode == "RGB":
        # Keep PNG for transparency-less but original png — optional
        pass

    # Save as JPEG for size (except webp keeps webp)
    ext = Path(new_name).suffix.lower()
    abs_path = abs_dir / new_name
    rel_path = (rel_dir / new_name).as_posix()

    try:
        if ext == ".webp":
            img.save(abs_path, "WEBP", quality=JPEG_QUALITY, method=4)
        else:
            # Save all others as JPEG
            if not new_name.lower().endswith(".jpg"):
                new_name = Path(new_name).stem + ".jpg"
                abs_path = abs_dir / new_name
                rel_path = (rel_dir / new_name).as_posix()
            img.save(abs_path, "JPEG", quality=JPEG_QUALITY, optimize=True)
    except Exception:
        return None

    size = abs_path.stat().st_size

    return {
        "image_path": rel_path,
        "file_size": size,
        "width": img.width,
        "height": img.height,
    }


def delete_error_image(upload_root: str, rel_path: str) -> bool:
    """Delete a saved image file safely."""
    if not rel_path:
        return False
    # Prevent path traversal
    abs_root = Path(upload_root).resolve()
    abs_file = (Path(upload_root) / rel_path).resolve()
    if not str(abs_file).startswith(str(abs_root)):
        return False
    try:
        if abs_file.is_file():
            abs_file.unlink()
        return True
    except Exception:
        return False
