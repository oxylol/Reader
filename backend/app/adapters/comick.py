"""comick adapter (comick.live / api.comick.fun).

Uses comick's public JSON API. The reading site is comick.live; the JSON API
lives at api.comick.fun and is what we hit for search, metadata, chapters and
page images. Image blobs are served from meo.comick.pictures.
"""
from __future__ import annotations

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

API = "https://api.comick.fun"
IMG_BASE = "https://meo.comick.pictures"

# comick country code -> our type
_COUNTRY_TYPE = {"jp": "manga", "kr": "manhwa", "cn": "manhua"}
_TYPE_COUNTRY = {v: k for k, v in _COUNTRY_TYPE.items()}
# our status -> comick status int
_STATUS_INT = {"ongoing": 1, "completed": 2, "cancelled": 3, "hiatus": 4}
_STATUS_NAME = {1: "ongoing", 2: "completed", 3: "cancelled", 4: "hiatus"}
# our sort -> comick sort
_SORT = {
    "popularity": "follow",
    "rating": "rating",
    "latest": "uploaded",
    "recent": "created",
    "alpha": "user_follow_count",  # comick has no alpha; fall back
    "chapters": "follow",
}
_TIMEFRAME_DAYS = {"today": "7", "week": "7", "month": "30", "all": "90"}


def _cover_url(md_covers: Optional[list[dict[str, Any]]]) -> str:
    if md_covers:
        key = md_covers[0].get("b2key")
        if key:
            return f"{IMG_BASE}/{key}"
    return ""


def _series_from_json(d: dict[str, Any]) -> SeriesResult:
    comic = d.get("comic", d)
    country = (comic.get("country") or "").lower()
    md_titles = comic.get("md_titles") or []
    alt = [t.get("title", "") for t in md_titles if t.get("title")]
    genres: list[str] = []
    for g in comic.get("md_comic_md_genres", []) or []:
        name = (g.get("md_genres") or {}).get("name")
        if name:
            genres.append(name)
    return SeriesResult(
        source="comick",
        source_id=comic.get("hid", ""),
        slug=comic.get("slug", ""),
        title=comic.get("title", ""),
        cover_url=_cover_url(comic.get("md_covers")),
        type=_COUNTRY_TYPE.get(country, "unknown"),
        status=_STATUS_NAME.get(comic.get("status"), "unknown"),
        description=comic.get("desc", "") or "",
        alt_titles=alt,
        original_language=country,
        year=comic.get("year"),
        content_rating=comic.get("content_rating", "") or "",
        tags=genres,
        rating=_safe_float(comic.get("bayesian_rating") or comic.get("rating")),
        follow_count=comic.get("user_follow_count") or comic.get("follow_count"),
        last_updated=comic.get("uploaded_at") or comic.get("last_chapter"),
    )


def _safe_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_number(chap: str | None) -> tuple[float, str]:
    if not chap:
        return (0.0, "")
    label = str(chap)
    try:
        return (float(label), label)
    except ValueError:
        return (0.0, label)


class ComickAdapter(SourceAdapter):
    key = "comick"
    name = "Comick"
    base_url = "https://comick.live"
    needs_cloudflare = False  # JSON API is usually open; falls back automatically
    supports_trending = True
    supports_advanced_search = True

    async def search(self, filters: SearchFilters) -> list[SeriesResult]:
        params: dict[str, Any] = {
            "page": filters.page,
            "limit": filters.limit,
            "tachiyomi": "true",
        }
        if filters.query:
            params["q"] = filters.query
        params["sort"] = _SORT.get(filters.sort, "follow")
        if filters.include_tags:
            params["genres"] = filters.include_tags
        if filters.exclude_tags:
            params["excludes"] = filters.exclude_tags
        countries = [_TYPE_COUNTRY[t] for t in filters.types if t in _TYPE_COUNTRY]
        if countries:
            params["country"] = countries
        statuses = [_STATUS_INT[s] for s in filters.status if s in _STATUS_INT]
        if len(statuses) == 1:
            params["status"] = statuses[0]
        if filters.year_from:
            params["from"] = filters.year_from
        if filters.year_to:
            params["to"] = filters.year_to
        if filters.content_rating:
            params["content_rating"] = filters.content_rating

        data = await self._get("/v1.0/search", params=params)
        if not isinstance(data, list):
            return []
        return [_series_from_json(item) for item in data]

    async def trending(self, params: TrendingParams) -> list[SeriesResult]:
        data = await self._get("/top", params={"comic_types": "manga,manhwa,manhua"})
        if not isinstance(data, dict):
            return []
        results: list[dict[str, Any]] = []
        if params.shelf == "trending":
            days = _TIMEFRAME_DAYS.get(params.timeframe, "7")
            trending = data.get("trending") or {}
            results = trending.get(days) or trending.get("7") or []
        elif params.shelf == "latest":
            results = data.get("news") or data.get("extendedNews") or []
        elif params.shelf == "newly_added":
            nc = data.get("topFollowNewComics") or {}
            results = nc.get("7") or nc.get("30") or []
        elif params.shelf == "top_rated":
            results = data.get("rank") or []
        else:
            results = data.get("trending", {}).get("7", [])
        return [_series_from_json(item) for item in results]

    async def get_series(self, source_id: str) -> SeriesResult:
        # source_id may be hid or slug; comick accepts slug on /comic/{slug}
        data = await self._get(f"/comic/{source_id}", params={"tachiyomi": "true"})
        if not isinstance(data, dict) or "comic" not in data:
            raise AdapterError(f"Series not found: {source_id}")
        return _series_from_json(data)

    async def list_chapters(
        self, source_id: str, language: str = "en"
    ) -> list[ChapterResult]:
        # need hid; if a slug was passed, resolve to hid first
        hid = source_id
        if len(source_id) > 12 or "-" in source_id:
            series = await self.get_series(source_id)
            hid = series.source_id
        chapters: list[ChapterResult] = []
        page = 1
        while True:
            data = await self._get(
                f"/comic/{hid}/chapters",
                params={"lang": language, "page": page, "limit": 100, "tachiyomi": "true"},
            )
            items = (data or {}).get("chapters", []) if isinstance(data, dict) else []
            if not items:
                break
            for ch in items:
                num, label = _parse_number(ch.get("chap"))
                groups = ch.get("group_name") or []
                chapters.append(
                    ChapterResult(
                        source_chapter_id=ch.get("hid", ""),
                        number=num,
                        number_label=label,
                        volume=str(ch.get("vol") or ""),
                        title=ch.get("title") or "",
                        language=ch.get("lang") or language,
                        scanlation_group=", ".join(groups) if groups else "",
                        published_at=ch.get("created_at") or ch.get("publish_at"),
                    )
                )
            total = (data or {}).get("total", 0)
            if page * 100 >= total or len(items) < 100:
                break
            page += 1
        # de-dupe by number, keep first (comick returns newest groups first)
        return chapters

    async def get_page_urls(self, source_chapter_id: str) -> list[str]:
        data = await self._get(
            f"/chapter/{source_chapter_id}", params={"tachiyomi": "true"}
        )
        if not isinstance(data, dict):
            return []
        chapter = data.get("chapter", data)
        images = chapter.get("md_images") or chapter.get("images") or []
        urls: list[str] = []
        for img in images:
            key = img.get("b2key") or img.get("url")
            if not key:
                continue
            urls.append(key if key.startswith("http") else f"{IMG_BASE}/{key}")
        return urls

    async def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        return await http.fetch_json(
            f"{API}{path}",
            params=params,
            needs_cloudflare=self.needs_cloudflare,
            headers={"Accept": "application/json", "Referer": self.base_url},
        )
