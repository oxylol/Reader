"""Predictable on-disk layout for the compressed library.

    LIBRARY_DIR/
      {source}/{series_slug}-{source_id}/
        ch-{number_label}-{chapter_id}.cbz
"""
from __future__ import annotations

import re
from pathlib import Path

from ..config import settings
from ..models import Chapter, Series

_slug_re = re.compile(r"[^a-z0-9]+")


def _safe(value: str, fallback: str = "x") -> str:
    s = _slug_re.sub("-", (value or "").lower()).strip("-")
    return s[:80] or fallback


def series_dir(series: Series) -> Path:
    name = f"{_safe(series.slug or series.title)}-{_safe(series.source_id)}"
    return settings.library_path / _safe(series.source) / name


def chapter_cbz_path(series: Series, chapter: Chapter) -> Path:
    label = _safe(chapter.number_label or str(chapter.number), "0")
    fname = f"ch-{label}-{_safe(chapter.source_chapter_id)}.cbz"
    return series_dir(series) / fname


def relative_path(p: Path) -> str:
    return str(p.relative_to(settings.library_path))


def absolute_path(rel: str) -> Path:
    return settings.library_path / rel


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
