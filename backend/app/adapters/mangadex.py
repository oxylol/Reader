"""MangaDex adapter (api.mangadex.org).

MangaDex has a stable, fully public, documented JSON API with no Cloudflare and
no auth required for reads. Page images are served from a per-chapter "at-home"
server. This is the default source.

Docs: https://api.mangadex.org/docs/
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..services import http
from .base import (
    AdapterError,
    ChapterResult,
    SearchFilters,
    SeriesResult,
    SourceAdapter,
    TrendingParams,
)

API = "https://api.mangadex.org"
COVERS = "https://uploads.mangadex.org/covers"

# MangaDex originalLanguage -> our type
_LANG_TYPE = {"ja": "manga", "ko": "manhwa", "zh": "manhua", "zh-hk": "manhua"}
_TYPE_LANG = {"manga": "ja", "manhwa": "ko", "manhua": "zh"}

_SORT = {
    "popularity": ("followedCount", "desc"),
    "rating": ("rating", "desc"),
    "latest": ("latestUploadedChapter", "desc"),
    "recent": ("createdAt", "desc"),
    "alpha": ("title", "asc"),
    "chapters": ("followedCount", "desc"),  # no direct chapter-count sort
}
_SHELF_ORDER = {
    "trending": ("followedCount", "desc"),
    "latest": ("latestUploadedChapter", "desc"),
    "newly_added": ("createdAt", "desc"),
    "top_rated": ("rating", "desc"),
}
_TIMEFRAME_DAYS = {"today": 1, "week": 7, "month": 30, "all": None}
_ALL_RATINGS = ["safe", "suggestive", "erotica", "pornographic"]


def _pick_lang(d: Optional[dict[str, str]], prefer: str = "en") -> str:
    if not d:
        return ""
    if prefer in d:
        return d[prefer]
    for k in ("en", "ja-ro", "ja"):
        if k in d:
            return d[k]
    return next(iter(d.values()), "")


def _cover_filename(relationships: list[dict[str, Any]]) -> str:
    for rel in relationships:
        if rel.get("type") == "cover_art":
            return (rel.get("attributes") or {}).get("fileName", "")
    return ""


def _manga_to_series(m: dict[str, Any]) -> SeriesResult:
    attr = m.get("attributes", {})
    rels = m.get("relationships", [])
    mid = m.get("id", "")
    title = _pick_lang(attr.get("title"))
    alt = [list(a.values())[0] for a in attr.get("altTitles", []) if a]
    orig = attr.get("originalLanguage", "")
    tags = []
    for t in attr.get("tags", []):
        name = _pick_lang((t.get("attributes") or {}).get("name"))
        if name:
            tags.append(name)
    cover_file = _cover_filename(rels)
    cover_url = f"{COVERS}/{mid}/{cover_file}.512.jpg" if cover_file else ""
    rating = (attr.get("rating") or {}) if isinstance(attr.get("rating"), dict) else {}
    return SeriesResult(
        source="mangadex",
        source_id=mid,
        slug=_slugify(title) or mid,
        title=title or "(untitled)",
        cover_url=cover_url,
        type=_LANG_TYPE.get(orig, "unknown"),
        status=attr.get("status") or "unknown",
        description=_pick_lang(attr.get("description")),
        alt_titles=alt,
        original_language=orig,
        year=attr.get("year"),
        content_rating=attr.get("contentRating", "") or "",
        tags=tags,
        rating=rating.get("bayesian"),
    )


def _slugify(s: str) -> str:
    return "-".join("".join(c if c.isalnum() else " " for c in s.lower()).split())[:80]


def _parse_number(chap: str | None) -> tuple[float, str]:
    if chap is None or chap == "":
        return (0.0, "")
    label = str(chap)
    try:
        return (float(label), label)
    except ValueError:
        return (0.0, label)


class MangaDexAdapter(SourceAdapter):
    key = "mangadex"
    name = "MangaDex"
    base_url = "https://mangadex.org"
    needs_cloudflare = False
    supports_trending = True
    supports_advanced_search = True

    def __init__(self) -> None:
        self._tag_map: dict[str, str] | None = None  # lower name -> uuid

    # ---- tags ----
    async def _tags(self) -> dict[str, str]:
        if self._tag_map is None:
            data = await self._get("/manga/tag")
            mapping: dict[str, str] = {}
            for t in data.get("data", []):
                name = _pick_lang((t.get("attributes") or {}).get("name"))
                if name:
                    mapping[name.lower()] = t.get("id", "")
            self._tag_map = mapping
        return self._tag_map

    async def _tag_ids(self, names: list[str]) -> list[str]:
        if not names:
            return []
        tags = await self._tags()
        return [tags[n.lower()] for n in names if n.lower() in tags]

    # ---- search ----
    async def search(self, filters: SearchFilters) -> list[SeriesResult]:
        params: list[tuple[str, Any]] = [
            ("limit", min(filters.limit, 100)),
            ("offset", (filters.page - 1) * filters.limit),
            ("includes[]", "cover_art"),
        ]
        if filters.query:
            params.append(("title", filters.query))
        col, direction = _SORT.get(filters.sort, ("followedCount", "desc"))
        params.append((f"order[{col}]", direction))

        for tid in await self._tag_ids(filters.include_tags):
            params.append(("includedTags[]", tid))
        if filters.include_tags:
            params.append(("includedTagsMode", "AND"))
        for tid in await self._tag_ids(filters.exclude_tags):
            params.append(("excludedTags[]", tid))

        for t in filters.types:
            if t in _TYPE_LANG:
                params.append(("originalLanguage[]", _TYPE_LANG[t]))
        for s in filters.status:
            params.append(("status[]", s))
        for lang in filters.translated_language:
            params.append(("availableTranslatedLanguage[]", lang))
        for lang in filters.original_language:
            params.append(("originalLanguage[]", lang))

        ratings = filters.content_rating or _ALL_RATINGS
        for r in ratings:
            params.append(("contentRating[]", r))

        # MangaDex supports a single `year`; for an exact year use it,
        # otherwise filter the range client-side below.
        if filters.year_from and filters.year_from == filters.year_to:
            params.append(("year", filters.year_from))

        data = await self._get("/manga", params)
        results = [_manga_to_series(m) for m in data.get("data", [])]

        if filters.year_from or filters.year_to:
            lo = filters.year_from or 0
            hi = filters.year_to or 9999
            results = [r for r in results if r.year is None or lo <= r.year <= hi]
        return results

    # ---- trending ----
    async def trending(self, params: TrendingParams) -> list[SeriesResult]:
        col, direction = _SHELF_ORDER.get(params.shelf, ("followedCount", "desc"))
        q: list[tuple[str, Any]] = [
            ("limit", min(params.limit, 100)),
            ("offset", (params.page - 1) * params.limit),
            ("includes[]", "cover_art"),
            (f"order[{col}]", direction),
        ]
        for r in _ALL_RATINGS:
            q.append(("contentRating[]", r))
        # For "trending" with a timeframe, bias toward titles updated recently.
        days = _TIMEFRAME_DAYS.get(params.timeframe)
        if params.shelf in ("trending", "newly_added") and days:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            key = "createdAtSince" if params.shelf == "newly_added" else "updatedAtSince"
            q.append((key, since.strftime("%Y-%m-%dT%H:%M:%S")))
        data = await self._get("/manga", q)
        return [_manga_to_series(m) for m in data.get("data", [])]

    # ---- series ----
    async def get_series(self, source_id: str) -> SeriesResult:
        data = await self._get(
            f"/manga/{source_id}", [("includes[]", "cover_art")]
        )
        m = data.get("data")
        if not m:
            raise AdapterError(f"Series not found: {source_id}")
        return _manga_to_series(m)

    # ---- chapters ----
    async def list_chapters(
        self, source_id: str, language: str = "en"
    ) -> list[ChapterResult]:
        chapters: list[ChapterResult] = []
        offset = 0
        limit = 500
        while True:
            q: list[tuple[str, Any]] = [
                ("limit", limit),
                ("offset", offset),
                ("translatedLanguage[]", language),
                ("includes[]", "scanlation_group"),
                ("order[chapter]", "asc"),
                ("order[volume]", "asc"),
            ]
            for r in _ALL_RATINGS:
                q.append(("contentRating[]", r))
            data = await self._get(f"/manga/{source_id}/feed", q)
            items = data.get("data", [])
            for ch in items:
                attr = ch.get("attributes", {})
                # Skip chapters hosted off-site (no readable pages here).
                if attr.get("externalUrl"):
                    continue
                if not attr.get("pages"):
                    continue
                num, label = _parse_number(attr.get("chapter"))
                group = ""
                for rel in ch.get("relationships", []):
                    if rel.get("type") == "scanlation_group":
                        group = (rel.get("attributes") or {}).get("name", "")
                        break
                chapters.append(
                    ChapterResult(
                        source_chapter_id=ch.get("id", ""),
                        number=num,
                        number_label=label,
                        volume=str(attr.get("volume") or ""),
                        title=attr.get("title") or "",
                        language=attr.get("translatedLanguage") or language,
                        scanlation_group=group,
                        published_at=attr.get("publishAt"),
                    )
                )
            total = data.get("total", 0)
            offset += limit
            if offset >= total or not items:
                break
        return chapters

    # ---- pages ----
    async def get_page_urls(self, source_chapter_id: str) -> list[str]:
        data = await self._get(f"/at-home/server/{source_chapter_id}")
        base = data.get("baseUrl", "")
        chapter = data.get("chapter", {})
        h = chapter.get("hash", "")
        files = chapter.get("data", [])  # full quality; we re-compress to WebP
        if not base or not h or not files:
            return []
        return [f"{base}/data/{h}/{f}" for f in files]

    async def _get(
        self, path: str, params: Optional[list[tuple[str, Any]]] = None
    ) -> Any:
        return await http.fetch_json(
            f"{API}{path}",
            params=params,
            needs_cloudflare=self.needs_cloudflare,
            headers={
                "Accept": "application/json",
                "User-Agent": "InkVault/0.1 (self-hosted manga reader)",
            },
        )
