"""Discovery (Browse tab): trending shelves + cross-source advanced search.

Kept entirely separate from the library/reader. Aggregates across every
configured adapter and de-duplicates the same series seen on multiple sources.
"""
from __future__ import annotations

import asyncio
import json
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters import get_adapter, list_adapters
from ..adapters.base import SearchFilters, SeriesResult, TrendingParams
from ..core.deps import get_current_user
from ..db import get_session
from ..models import LibraryEntry, SavedSearch, SearchHistory, Series, User
from ..schemas import (
    DiscoverItem,
    SavedSearchOut,
    SearchRequest,
)

router = APIRouter(prefix="/api/browse", tags=["browse"])


def _norm_title(t: str) -> str:
    return "".join(c for c in t.lower() if c.isalnum())


def _dedupe(results: list[SeriesResult]) -> list[DiscoverItem]:
    """Merge the same series appearing across sources by fuzzy title match."""
    items: list[DiscoverItem] = []
    norms: list[str] = []
    for r in results:
        n = _norm_title(r.title)
        merged = False
        for i, existing_n in enumerate(norms):
            if existing_n == n or SequenceMatcher(None, existing_n, n).ratio() > 0.9:
                if r.source not in items[i].sources:
                    items[i].sources.append(r.source)
                merged = True
                break
        if merged:
            continue
        norms.append(n)
        items.append(
            DiscoverItem(
                source=r.source,
                source_id=r.source_id,
                slug=r.slug,
                title=r.title,
                cover_url=r.cover_url,
                type=r.type,
                status=r.status,
                description=r.description,
                tags=r.tags,
                year=r.year,
                rating=r.rating,
                follow_count=r.follow_count,
                sources=[r.source],
            )
        )
    return items


async def _mark_in_library(
    session: AsyncSession, user_id: int, items: list[DiscoverItem]
) -> None:
    if not items:
        return
    rows = (
        await session.execute(
            select(Series.source, Series.source_id)
            .join(LibraryEntry, LibraryEntry.series_id == Series.id)
            .where(LibraryEntry.user_id == user_id)
        )
    ).all()
    owned = {(s, sid) for s, sid in rows}
    for it in items:
        it.in_library = (it.source, it.source_id) in owned


@router.get("/sources")
async def sources(_: User = Depends(get_current_user)):
    return [
        {
            "key": a.key,
            "name": a.name,
            "needs_cloudflare": a.needs_cloudflare,
            "supports_trending": a.supports_trending,
            "supports_advanced_search": a.supports_advanced_search,
        }
        for a in list_adapters()
    ]


@router.get("/trending", response_model=list[DiscoverItem])
async def trending(
    shelf: str = Query("trending"),
    timeframe: str = Query("week"),
    page: int = Query(1, ge=1),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    params = TrendingParams(shelf=shelf, timeframe=timeframe, page=page)
    all_results: list[SeriesResult] = []
    for adapter in list_adapters():
        if not adapter.supports_trending:
            continue
        try:
            all_results.extend(await adapter.trending(params))
        except Exception:  # noqa: BLE001
            continue
    items = _dedupe(all_results)
    await _mark_in_library(session, user.id, items)
    return items


@router.post("/search", response_model=list[DiscoverItem])
async def search(
    body: SearchRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    target_keys = body.sources or [a.key for a in list_adapters()]
    filters = SearchFilters(
        query=body.query,
        include_tags=body.include_tags,
        exclude_tags=body.exclude_tags,
        types=body.types,
        status=body.status,
        original_language=body.original_language,
        translated_language=body.translated_language,
        year_from=body.year_from,
        year_to=body.year_to,
        content_rating=body.content_rating,
        scanlation_group=body.scanlation_group,
        sort=body.sort,
        page=body.page,
        limit=body.limit,
    )

    async def run(key: str) -> list[SeriesResult]:
        try:
            return await get_adapter(key).search(filters)
        except Exception:  # noqa: BLE001
            return []

    gathered = await asyncio.gather(*(run(k) for k in target_keys))
    flat: list[SeriesResult] = [r for sub in gathered for r in sub]
    items = _dedupe(flat)
    await _mark_in_library(session, user.id, items)

    # Record search history (best-effort).
    if body.query:
        session.add(SearchHistory(user_id=user.id, query=body.query))
        await session.commit()
    return items


# --- Saved searches & history (P1) ---
@router.get("/saved", response_model=list[SavedSearchOut])
async def list_saved(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(SavedSearch).where(SavedSearch.user_id == user.id)
        )
    ).scalars().all()
    return [
        SavedSearchOut(id=r.id, name=r.name, query=SearchRequest(**json.loads(r.query_json)))
        for r in rows
    ]


@router.post("/saved", response_model=SavedSearchOut, status_code=201)
async def save_search(
    name: str,
    body: SearchRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    row = SavedSearch(user_id=user.id, name=name, query_json=body.model_dump_json())
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return SavedSearchOut(id=row.id, name=row.name, query=body)


@router.delete("/saved/{saved_id}", status_code=204)
async def delete_saved(
    saved_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    row = await session.get(SavedSearch, saved_id)
    if row and row.user_id == user.id:
        await session.delete(row)
        await session.commit()


@router.get("/history")
async def history(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(SearchHistory)
            .where(SearchHistory.user_id == user.id)
            .order_by(SearchHistory.created_at.desc())
            .limit(30)
        )
    ).scalars().all()
    return [{"query": r.query, "at": r.created_at.isoformat()} for r in rows]
