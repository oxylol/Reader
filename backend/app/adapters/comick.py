"""comick adapter (comick.art clone of the shut-down comick.io).

The original comick.io shut down; its catalogue is now served by clone hosts
(comick.art / comick.live) running a Laravel API at the site origin under
``/api``. comick.art serves the API without Cloudflare. Endpoints (reverse
engineered from the site's JS bundles):

  - search    GET /api/search?q=&limit=&page=
  - trending  GET /api/comics/top?day=&type=
  - genres    GET /api/metadata
  - chapters  GET /api/comics/{slug}/chapter-list?page=        (paginated)
  - pages     GET /api/comics/{slug}/{hid}-chapter-{chap}-{lang}  -> images[].url

Page images are full URLs on cdn1.comicknew.pictures and are fetched with a
Referer to avoid hotlink protection (see ``image_headers``).
"""
from __future__ import annotations

import re
from typing import Any, Optional

from ..config import settings
from ..services import http
from .base import (
    AdapterError,
    ChapterResult,
    SearchFilters,
    SeriesResult,
    SourceAdapter,
    TrendingParams,
)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# comick country code -> our type
_COUNTRY_TYPE = {"kr": "manhwa", "jp": "manga", "cn": "manhua"}
_TYPE_COUNTRY = {v: k for k, v in _COUNTRY_TYPE.items()}
# comick status int -> our status
_STATUS = {1: "ongoing", 2: "completed", 3: "cancelled", 4: "hiatus"}
# trending timeframe -> top "day" param
_DAY = {"today": 1, "week": 7, "month": 30, "all": 180}


def _num(chap: Any) -> tuple[float, str]:
    if chap is None or chap == "":
        return (0.0, "")
    label = str(chap)
    try:
        return (float(label), label)
    except ValueError:
        return (0.0, label)


def _safe_float(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class ComickAdapter(SourceAdapter):
    key = "comick"
    name = "Comick"
    base_url = settings.comick_site_url
    needs_cloudflare = settings.comick_needs_cloudflare
    supports_trending = True
    supports_advanced_search = True

    def __init__(self) -> None:
        self._genres: dict[int, str] | None = None  # id -> name
        self._genre_ids: dict[str, int] | None = None  # lower name -> id

    @property
    def api(self) -> str:
        return settings.comick_api_url.rstrip("/")

    @property
    def image_headers(self) -> dict[str, str]:
        # cdn images are hotlink-protected; send a Referer + browser UA.
        return {"User-Agent": BROWSER_UA, "Referer": self.base_url + "/"}

    # ---- metadata / genres ----
    async def _load_genres(self) -> None:
        if self._genres is not None:
            return
        data = await self._get("/api/metadata")
        self._genres = {}
        self._genre_ids = {}
        for g in (data or {}).get("genres", []):
            gid, name = g.get("id"), g.get("name")
            if gid is not None and name:
                self._genres[gid] = name
                self._genre_ids[name.lower()] = gid

    def _genre_names(self, ids: list[Any]) -> list[str]:
        if not self._genres:
            return []
        out = []
        for i in ids or []:
            name = self._genres.get(i)
            if name:
                out.append(name)
        return out

    # ---- result mapping ----
    async def _to_series(self, item: dict[str, Any]) -> SeriesResult:
        await self._load_genres()
        country = (item.get("country") or "").lower()
        genres = item.get("genres") or []
        # genres are numeric ids (top/comic) -> map to names; ignore if names
        tags = self._genre_names([g for g in genres if isinstance(g, int)])
        alt = [t for t in (item.get("titles") or []) if isinstance(t, str)]
        return SeriesResult(
            source="comick",
            source_id=item.get("slug", ""),
            slug=item.get("slug", ""),
            title=item.get("title", "") or "(untitled)",
            cover_url=item.get("default_thumbnail", "") or "",
            type=_COUNTRY_TYPE.get(country, "unknown"),
            status=_STATUS.get(item.get("status"), "unknown"),
            description=(item.get("description") or item.get("parsed_description") or "").strip(),
            alt_titles=alt,
            original_language=country,
            year=item.get("year"),
            content_rating=item.get("content_rating", "") or "",
            tags=tags,
            rating=_safe_float(item.get("bayesian_rating")),
            follow_count=item.get("user_follow_count") or item.get("follow_count"),
            chapter_count=item.get("chapter_count"),
        )

    # ---- search ----
    async def search(self, filters: SearchFilters) -> list[SeriesResult]:
        if not filters.query:
            # No free-text query -> fall back to popular for a useful result set.
            return await self.trending(TrendingParams(timeframe="all", limit=filters.limit))
        params = {"q": filters.query, "limit": min(filters.limit, 50), "page": filters.page}
        data = await self._get("/api/search", params)
        items = (data or {}).get("data", []) if isinstance(data, dict) else []
        results = [await self._to_series(it) for it in items]
        return self._apply_client_filters(results, filters)

    def _apply_client_filters(
        self, results: list[SeriesResult], f: SearchFilters
    ) -> list[SeriesResult]:
        # comick's /api/search is title-only; apply the rest client-side so the
        # Browse filters still narrow results.
        def ok(r: SeriesResult) -> bool:
            if f.types and r.type not in f.types:
                return False
            if f.status and r.status not in f.status:
                return False
            if f.year_from and (r.year or 0) < f.year_from:
                return False
            if f.year_to and (r.year or 9999) > f.year_to:
                return False
            low = {t.lower() for t in r.tags}
            if f.include_tags and not all(t.lower() in low for t in f.include_tags):
                return False
            if f.exclude_tags and any(t.lower() in low for t in f.exclude_tags):
                return False
            return True

        return [r for r in results if ok(r)]

    # ---- trending ----
    async def trending(self, params: TrendingParams) -> list[SeriesResult]:
        q: dict[str, Any] = {"day": _DAY.get(params.timeframe, 7)}
        data = await self._get("/api/comics/top", q)
        items = (data or {}).get("data", []) if isinstance(data, dict) else []
        return [await self._to_series(it) for it in items[: params.limit]]

    # ---- series detail ----
    async def get_series(self, source_id: str) -> SeriesResult:
        slug = source_id
        # Best source of rich metadata is the search index; match by exact slug.
        q = re.sub(r"^[\d\s]+", "", slug.replace("-", " ")).strip() or slug
        data = await self._get("/api/search", {"q": q, "limit": 30})
        for it in (data or {}).get("data", []):
            if it.get("slug") == slug:
                return await self._to_series(it)
        # Fallback: pull the comic object embedded in a chapter read response.
        cl = await self._get(f"/api/comics/{slug}/chapter-list", {"page": 1})
        items = (cl or {}).get("data", []) if isinstance(cl, dict) else []
        if items:
            ch = items[0]
            seg = f"{ch['hid']}-chapter-{ch['chap']}-{ch.get('lang', 'en')}"
            rd = await self._get(f"/api/comics/{slug}/{seg}")
            comic = (rd or {}).get("chapter", {}).get("comic", {})
            if comic:
                comic.setdefault("slug", slug)
                return await self._to_series(comic)
        raise AdapterError(f"Series not found: {slug}")

    # ---- chapters ----
    async def list_chapters(
        self, source_id: str, language: str = "en"
    ) -> list[ChapterResult]:
        slug = source_id
        chapters: list[ChapterResult] = []
        page = 1
        while True:
            data = await self._get(f"/api/comics/{slug}/chapter-list", {"page": page})
            if not isinstance(data, dict):
                break
            for ch in data.get("data", []):
                lang = ch.get("lang", "")
                if language and lang != language:
                    continue
                num, label = _num(ch.get("chap"))
                hid = ch.get("hid")
                if not hid:
                    continue
                seg = f"{hid}-chapter-{ch.get('chap')}-{lang or language}"
                groups = ch.get("group_name") or []
                chapters.append(
                    ChapterResult(
                        # pack slug + segment so get_page_urls can rebuild the URL
                        source_chapter_id=f"{slug}/{seg}",
                        number=num,
                        number_label=label,
                        volume=str(ch.get("vol") or ""),
                        title=ch.get("title") or "",
                        language=lang or language,
                        scanlation_group=", ".join(groups) if isinstance(groups, list) else str(groups or ""),
                        published_at=ch.get("created_at") or ch.get("publish_at"),
                    )
                )
            pg = data.get("pagination") or {}
            last = pg.get("last_page", page)
            if page >= last:
                break
            page += 1
        return chapters

    # ---- pages ----
    async def get_page_urls(self, source_chapter_id: str) -> list[str]:
        # source_chapter_id == "{slug}/{hid}-chapter-{chap}-{lang}"
        data = await self._get(f"/api/comics/{source_chapter_id}")
        chapter = (data or {}).get("chapter", {}) if isinstance(data, dict) else {}
        images = chapter.get("images") or []
        urls = []
        for img in images:
            u = img.get("url") if isinstance(img, dict) else None
            if u:
                urls.append(u)
        return urls

    async def _get(self, path: str, params: Optional[dict[str, Any]] = None) -> Any:
        return await http.fetch_json(
            f"{self.api}{path}",
            params=params,
            needs_cloudflare=self.needs_cloudflare,
            headers={
                "Accept": "application/json",
                "User-Agent": BROWSER_UA,
                "Referer": self.base_url + "/",
            },
        )
