"""Image compression + CBZ packaging.

Every downloaded page is re-encoded to WebP (or AVIF) at the configured
quality, then packed into a per-chapter CBZ (a ZIP of images). Originals are
never persisted to disk.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image

from ..config import settings

# Pillow needs this enabled for some progressive/large images
Image.MAX_IMAGE_PIXELS = None


def compress_image(raw: bytes, fmt: str | None = None, quality: int | None = None) -> bytes:
    """Re-encode an image to WebP/AVIF. Returns the encoded bytes."""
    fmt = (fmt or settings.image_format).lower()
    quality = quality or settings.quality_int

    with Image.open(io.BytesIO(raw)) as im:
        # Normalize mode for the encoder.
        if fmt == "webp":
            if im.mode not in ("RGB", "RGBA", "L"):
                im = im.convert("RGB")
            out = io.BytesIO()
            im.save(out, format="WEBP", quality=quality, method=4)
            return out.getvalue()
        elif fmt == "avif":
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGB")
            out = io.BytesIO()
            # Requires pillow built with AVIF support (pillow-avif-plugin or
            # libavif). Falls back to WebP on failure.
            try:
                im.save(out, format="AVIF", quality=quality)
                return out.getvalue()
            except (OSError, KeyError, ValueError):
                out = io.BytesIO()
                if im.mode not in ("RGB", "RGBA", "L"):
                    im = im.convert("RGB")
                im.save(out, format="WEBP", quality=quality, method=4)
                return out.getvalue()
        else:
            raise ValueError(f"Unsupported image format: {fmt}")


def _ext_for_format(fmt: str | None = None) -> str:
    fmt = (fmt or settings.image_format).lower()
    return "avif" if fmt == "avif" else "webp"


class CbzWriter:
    """Accumulates compressed pages and writes a single CBZ atomically."""

    def __init__(self, dest: Path):
        self.dest = dest
        self.tmp = dest.with_suffix(".cbz.part")
        self.dest.parent.mkdir(parents=True, exist_ok=True)
        self._zip = zipfile.ZipFile(self.tmp, "w", zipfile.ZIP_STORED)
        self._count = 0

    def add_page(self, index: int, data: bytes, fmt: str | None = None) -> None:
        ext = _ext_for_format(fmt)
        name = f"{index:04d}.{ext}"
        # Images are already compressed; STORED avoids wasteful double work.
        self._zip.writestr(name, data)
        self._count += 1

    @property
    def page_count(self) -> int:
        return self._count

    def finalize(self) -> int:
        self._zip.close()
        self.tmp.replace(self.dest)
        return self.dest.stat().st_size

    def abort(self) -> None:
        try:
            self._zip.close()
        finally:
            self.tmp.unlink(missing_ok=True)


def read_page_from_cbz(cbz_path: Path, index: int) -> tuple[bytes, str]:
    """Return (bytes, media_type) for the page at `index` (0-based)."""
    with zipfile.ZipFile(cbz_path) as zf:
        names = sorted(n for n in zf.namelist() if not n.endswith("/"))
        if index < 0 or index >= len(names):
            raise IndexError("page out of range")
        name = names[index]
        data = zf.read(name)
    media = "image/avif" if name.lower().endswith(".avif") else "image/webp"
    return data, media


def count_pages(cbz_path: Path) -> int:
    with zipfile.ZipFile(cbz_path) as zf:
        return sum(1 for n in zf.namelist() if not n.endswith("/"))
