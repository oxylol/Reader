"""The user's personal library + continue-reading."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..db import get_session
from ..models import Chapter, LibraryEntry, ReadingProgress, Series, User
from ..schemas import ChapterOut, SeriesOut
from ..services.series_service import build_chapter_out, build_series_out

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("", response_model=list[SeriesOut])
async def my_library(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    series = (
        await session.execute(
            select(Series)
            .join(LibraryEntry, LibraryEntry.series_id == Series.id)
            .where(LibraryEntry.user_id == user.id)
            .order_by(Series.updated_at.desc())
        )
    ).scalars().all()
    return [await build_series_out(session, s, user.id) for s in series]


@router.delete("/{series_id}", status_code=204)
async def unfollow(
    series_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entry = (
        await session.execute(
            select(LibraryEntry).where(
                LibraryEntry.user_id == user.id, LibraryEntry.series_id == series_id
            )
        )
    ).scalar_one_or_none()
    if entry:
        await session.delete(entry)
        await session.commit()


@router.get("/continue", response_model=list[dict])
async def continue_reading(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Most recently-read, not-yet-completed chapters across the library."""
    rows = (
        await session.execute(
            select(ReadingProgress)
            .where(
                ReadingProgress.user_id == user.id,
                ReadingProgress.completed == False,  # noqa: E712
            )
            .order_by(ReadingProgress.updated_at.desc())
            .limit(20)
        )
    ).scalars().all()
    out = []
    seen_series: set[int] = set()
    for p in rows:
        if p.series_id in seen_series:
            continue
        seen_series.add(p.series_id)
        series = await session.get(Series, p.series_id)
        chapter = await session.get(Chapter, p.chapter_id)
        if not series or not chapter:
            continue
        out.append(
            {
                "series": await build_series_out(session, series, user.id),
                "chapter": await build_chapter_out(session, chapter, user.id),
                "page": p.page,
                "scroll": p.scroll,
            }
        )
    return out
