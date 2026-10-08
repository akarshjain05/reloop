"""Upload validation + sanitising. Re-encodes to JPEG (strips EXIF/GPS), computes SHA-256 and a perceptual hash."""
from __future__ import annotations

import hashlib
import io

from PIL import Image, ImageOps, UnidentifiedImageError

from ..core.errors import AppError, bad_request

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
Image.MAX_IMAGE_PIXELS = 40_000_000  # decompression-bomb guard


def sniff(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def average_hash(im: Image.Image) -> str:
    g = im.convert("L").resize((8, 8), Image.LANCZOS)
    px = list(g.getdata())
    avg = sum(px) / 64
    return f"{int(''.join('1' if p > avg else '0' for p in px), 2):016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def prepare_image(data: bytes, max_mb: int) -> dict:
    if not data:
        raise bad_request("No image received.", "empty_file")
    if len(data) > max_mb * 1024 * 1024:
        raise AppError(413, "file_too_large", f"That image is larger than {max_mb} MB. Try a smaller photo.")
    if sniff(data) not in ALLOWED_TYPES:
        raise bad_request("Unsupported file type. Please upload a JPEG, PNG or WebP photo.", "unsupported_type")
    try:
        Image.open(io.BytesIO(data)).verify()
        im = Image.open(io.BytesIO(data))
        im.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise bad_request("That file couldn't be read as an image.", "unreadable_image") from e
    im = ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((1280, 1280))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=85, optimize=True)
    jpeg = buf.getvalue()
    return {"jpeg": jpeg, "sha256": hashlib.sha256(jpeg).hexdigest(), "ahash": average_hash(im), "width": im.width, "height": im.height, "size": len(jpeg)}
