"""Database models (SQLModel)."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SeriesType(str, Enum):
    manga = "manga"
    manhwa = "manhwa"
    manhua = "manhua"
    unknown = "unknown"


class SeriesStatus(str, Enum):
    ongoing = "ongoing"
    completed = "completed"
    hiatus = "hiatus"
    cancelled = "cancelled"
    unknown = "unknown"


class ReadingMode(str, Enum):
    paged = "paged"
    webtoon = "webtoon"
    auto = "auto"


class JobState(str, Enum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    is_admin: bool = False
    created_at: datetime = Field(default_factory=utcnow)


class Series(SQLModel, table=True):
    """A series acquired into the local library (deduped across sources)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    source_id: str = Field(index=True)
    slug: str = Field(index=True)
    title: str
    alt_titles: str = ""  # newline-separated
    description: str = ""
    cover_url: str = ""
    type: SeriesType = SeriesType.unknown
    status: SeriesStatus = SeriesStatus.unknown
    original_language: str = ""
    year: Optional[int] = None
    content_rating: str = ""
    tags: str = ""  # comma-separated
    default_mode: ReadingMode = ReadingMode.auto
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_series_source"),)


class Chapter(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    series_id: int = Field(foreign_key="series.id", index=True)
    source_chapter_id: str = Field(index=True)
    # numeric sort key; chapter "12.5" -> 12.5
    number: float = Field(index=True)
    number_label: str = ""  # original label, e.g. "12.5"
    volume: str = ""
    title: str = ""
    language: str = ""
    scanlation_group: str = ""
    page_count: int = 0
    # relative path of CBZ under LIBRARY_DIR once downloaded
    cbz_path: str = ""
    downloaded: bool = False
    size_bytes: int = 0
    published_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow)

    __table_args__ = (
        UniqueConstraint("series_id", "source_chapter_id", name="uq_chapter_source"),
    )


class LibraryEntry(SQLModel, table=True):
    """A user following a series (their personal library)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    series_id: int = Field(foreign_key="series.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "series_id", name="uq_library_user_series"),
    )


class ReadingProgress(SQLModel, table=True):
    """Per-user, per-chapter progress."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    series_id: int = Field(foreign_key="series.id", index=True)
    chapter_id: int = Field(foreign_key="chapter.id", index=True)
    page: int = 0
    # 0..1 scroll fraction for webtoon mode
    scroll: float = 0.0
    completed: bool = False
    updated_at: datetime = Field(default_factory=utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "chapter_id", name="uq_progress_user_chapter"),
    )


class UserPrefs(SQLModel, table=True):
    """Per-user reader preferences (defaults; per-series override on Series)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    reading_mode: ReadingMode = ReadingMode.auto
    rtl: bool = False
    fit: str = "width"  # width | height | original
    theme: str = "dark"  # dark | light
    double_page: bool = False


class SeriesModeOverride(SQLModel, table=True):
    """Per-user per-series reading-mode override."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    series_id: int = Field(foreign_key="series.id", index=True)
    reading_mode: ReadingMode = ReadingMode.auto
    rtl: Optional[bool] = None

    __table_args__ = (
        UniqueConstraint("user_id", "series_id", name="uq_override_user_series"),
    )


class DownloadJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    series_id: int = Field(foreign_key="series.id", index=True)
    state: JobState = Field(default=JobState.queued, index=True)
    total_chapters: int = 0
    done_chapters: int = 0
    failed_chapters: int = 0
    message: str = ""
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class SavedSearch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    name: str
    query_json: str  # serialized search params
    created_at: datetime = Field(default_factory=utcnow)


class SearchHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    query: str
    created_at: datetime = Field(default_factory=utcnow)
