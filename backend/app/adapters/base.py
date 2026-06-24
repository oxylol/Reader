"""Source adapter interface.

Every supported site is a self-contained module implementing `SourceAdapter`.
The core never imports a concrete adapter directly; it goes through the
registry, so new sources can be dropped in without touching core code.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


# --- DTOs returned by adapters (decoupled from DB models) ------------------


@dataclass
class SeriesResult:
    source: str
    source_id: str
    slug: str
    title: str
    cover_url: str = ""
    type: str = "unknown"  # manga | manhwa | manhua | unknown
    status: str = "unknown"
    description: str = ""
    alt_titles: list[str] = field(default_factory=list)
    original_language: str = ""
    year: Optional[int] = None
    content_rating: str = ""
    tags: list[str] = field(default_factory=list)
    rating: Optional[float] = None
    follow_count: Optional[int] = None
    chapter_count: Optional[int] = None
    last_updated: Optional[str] = None


@dataclass
class ChapterResult:
    source_chapter_id: str
    number: float
    number_label: str = ""
    volume: str = ""
    title: str = ""
    language: str = ""
    scanlation_group: str = ""
    published_at: Optional[str] = None


@dataclass
class SearchFilters:
    query: str = ""
    include_tags: list[str] = field(default_factory=list)
    exclude_tags: list[str] = field(default_factory=list)
    types: list[str] = field(default_factory=list)
    status: list[str] = field(default_factory=list)
    original_language: list[str] = field(default_factory=list)
    translated_language: list[str] = field(default_factory=list)
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    content_rating: list[str] = field(default_factory=list)
    scanlation_group: str = ""
    sort: str = "popularity"  # popularity|rating|latest|recent|alpha|chapters
    page: int = 1
    limit: int = 30


@dataclass
class TrendingParams:
    shelf: str = "trending"  # trending|latest|newly_added|top_rated
    timeframe: str = "week"  # today|week|month|all
    page: int = 1
    limit: int = 30


class AdapterError(RuntimeError):
    pass


class SourceAdapter(ABC):
    """Implement one of these per source site."""

    #: unique short id, e.g. "comick"
    key: str = ""
    #: human label
    name: str = ""
    base_url: str = ""
    needs_cloudflare: bool = False
    #: capability flags surfaced to the UI
    supports_trending: bool = False
    supports_advanced_search: bool = False

    @abstractmethod
    async def search(self, filters: SearchFilters) -> list[SeriesResult]:
        ...

    @abstractmethod
    async def trending(self, params: TrendingParams) -> list[SeriesResult]:
        ...

    @abstractmethod
    async def get_series(self, source_id: str) -> SeriesResult:
        ...

    @abstractmethod
    async def list_chapters(
        self, source_id: str, language: str = "en"
    ) -> list[ChapterResult]:
        ...

    @abstractmethod
    async def get_page_urls(self, source_chapter_id: str) -> list[str]:
        ...

    async def close(self) -> None:  # optional cleanup hook
        ...
