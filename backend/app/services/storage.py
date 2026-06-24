"""Predictable on-disk layout for the compressed library.

    LIBRARY_DIR/
      {source}/{series_slug}-{source_id}/
        ch-{number_label}-{chapter_id}.cbz
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from ..config import settings
from ..models import Chapter, Series

_slug_re = re.compile(r"[^a-z0-9]+")


def _safe(value: str, fallback: str = "x") -> str:
    s = _slug_re.sub("-", (value or "").lower()).strip("-")
    return s[:80] or fallback


def _hash(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()[:8]


def series_dir(series: Series) -> Path:
    # A short hash of (source, source_id) guarantees uniqueness even when two
    # different series share a slug prefix after truncation.
    base = _safe(series.slug or series.title, "series")[:48]
    uniq = _hash(f"{series.source}:{series.source_id}")
    return settings.library_path / _safe(series.source) / f"{base}-{uniq}"


def chapter_cbz_path(series: Series, chapter: Chapter) -> Path:
    label = _safe(chapter.number_label or str(chapter.number), "0")[:24]
    # The chapter's DB id is unique within the series; fall back to a hash of the
    # source id if it isn't persisted yet. This avoids filename collisions that
    # would make one chapter's pages serve for another.
    cid = chapter.id if chapter.id is not None else _hash(chapter.source_chapter_id)
    return series_dir(series) / f"ch-{label}-{cid}.cbz"


def relative_path(p: Path) -> str:
    return str(p.relative_to(settings.library_path))


def absolute_path(rel: str) -> Path:
    return settings.library_path / rel


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
