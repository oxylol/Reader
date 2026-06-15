"""API request/response schemas."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from .models import ReadingMode


# --- Auth ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool


class UserCreate(BaseModel):
    username: str
    password: str
    is_admin: bool = False


# --- Series / chapters ---
class SeriesOut(BaseModel):
    id: int
    source: str
    source_id: str
    slug: str
    title: str
    cover_url: str
    type: str
    status: str
    description: str
    tags: list[str]
    year: Optional[int]
    content_rating: str
    default_mode: str
    in_library: bool = False
    chapter_count: int = 0
    downloaded_count: int = 0
    unread_count: int = 0


class ChapterOut(BaseModel):
    id: int
    number: float
    number_label: str
    volume: str
    title: str
    language: str
    scanlation_group: str
    page_count: int
    downloaded: bool
    size_bytes: int
    read: bool = False
    current_page: int = 0


class DiscoverItem(BaseModel):
    """A discovery result (may not yet be in the local DB)."""
    source: str
    source_id: str
    slug: str
    title: str
    cover_url: str
    type: str
    status: str
    description: str = ""
    tags: list[str] = []
    year: Optional[int] = None
    rating: Optional[float] = None
    follow_count: Optional[int] = None
    in_library: bool = False
    sources: list[str] = []  # other sources that also have this (dedupe)


class SearchRequest(BaseModel):
    query: str = ""
    include_tags: list[str] = []
    exclude_tags: list[str] = []
    types: list[str] = []
    status: list[str] = []
    original_language: list[str] = []
    translated_language: list[str] = []
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    content_rating: list[str] = []
    scanlation_group: str = ""
    sort: str = "popularity"
    sources: list[str] = []  # empty = all configured
    page: int = 1
    limit: int = 30


class AddSeriesRequest(BaseModel):
    source: str
    source_id: str


class JobOut(BaseModel):
    id: int
    series_id: int
    state: str
    total_chapters: int
    done_chapters: int
    failed_chapters: int
    message: str


class ProgressUpdate(BaseModel):
    chapter_id: int
    page: int = 0
    scroll: float = 0.0
    completed: bool = False


class PrefsOut(BaseModel):
    reading_mode: str = "auto"
    rtl: bool = False
    fit: str = "width"
    theme: str = "dark"
    double_page: bool = False


class PrefsUpdate(BaseModel):
    reading_mode: Optional[str] = None
    rtl: Optional[bool] = None
    fit: Optional[str] = None
    theme: Optional[str] = None
    double_page: Optional[bool] = None


class ModeOverrideUpdate(BaseModel):
    reading_mode: ReadingMode = ReadingMode.auto
    rtl: Optional[bool] = None


class SavedSearchOut(BaseModel):
    id: int
    name: str
    query: SearchRequest


class StorageSeries(BaseModel):
    series_id: int
    title: str
    size_bytes: int
    chapter_count: int


class StorageStats(BaseModel):
    total_bytes: int
    series_count: int
    chapter_count: int
    series: list[StorageSeries]
