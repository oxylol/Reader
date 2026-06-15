"""Reader: serve compressed pages from local CBZ + reading progress.

Pages are served straight from the per-chapter CBZ on disk, already
compressed, so there is no live fetch from a remote CDN mid-read.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..db import get_session
from ..models import Chapter, ReadingProgress, Series, User
from ..models import utcnow
from ..schemas import ProgressUpdate
from ..services import storage
from ..services.compress import read_page_from_cbz
from ..services.series_service import build_chapter_out

router = APIRouter(prefix="/api/read", tags=["reader"])


@router.get("/chapter/{chapter_id}/page/{index}")
async def get_page(
    chapter_id: int,
    index: int,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chapter = await session.get(Chapter, chapter_id)
    if not chapter or not chapter.downloaded or not chapter.cbz_path:
        raise HTTPException(404, "Chapter not downloaded")
    cbz = storage.absolute_path(chapter.cbz_path)
    if not cbz.exists():
        raise HTTPException(404, "CBZ missing")
    try:
        data, media = read_page_from_cbz(cbz, index)
    except IndexError:
        raise HTTPException(404, "Page out of range")
    return Response(
        content=data,
        media_type=media,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/chapter/{chapter_id}")
async def chapter_info(
    chapter_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chapter = await session.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    series = await session.get(Series, chapter.series_id)

    # Compute prev/next chapter ids by number ordering.
    siblings = (
        await session.execute(
            select(Chapter)
            .where(Chapter.series_id == chapter.series_id)
            .order_by(Chapter.number)
        )
    ).scalars().all()
    ids = [c.id for c in siblings]
    pos = ids.index(chapter.id)
    prev_id = ids[pos - 1] if pos > 0 else None
    next_id = ids[pos + 1] if pos < len(ids) - 1 else None

    return {
        "chapter": await build_chapter_out(session, chapter, user.id),
        "series_id": chapter.series_id,
        "series_title": series.title if series else "",
        "series_type": series.type.value if series else "unknown",
        "default_mode": series.default_mode.value if series else "auto",
        "page_count": chapter.page_count,
        "prev_chapter_id": prev_id,
        "next_chapter_id": next_id,
    }


@router.put("/progress")
async def update_progress(
    body: ProgressUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chapter = await session.get(Chapter, body.chapter_id)
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    progress = (
        await session.execute(
            select(ReadingProgress).where(
                ReadingProgress.user_id == user.id,
                ReadingProgress.chapter_id == body.chapter_id,
            )
        )
    ).scalar_one_or_none()
    if progress is None:
        progress = ReadingProgress(
            user_id=user.id,
            series_id=chapter.series_id,
            chapter_id=body.chapter_id,
        )
        session.add(progress)
    progress.page = body.page
    progress.scroll = body.scroll
    progress.completed = body.completed
    progress.updated_at = utcnow()
    await session.commit()
    return {"ok": True}


@router.post("/chapter/{chapter_id}/read")
async def mark_read(
    chapter_id: int,
    read: bool = True,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    chapter = await session.get(Chapter, chapter_id)
    if not chapter:
        raise HTTPException(404, "Chapter not found")
    progress = (
        await session.execute(
            select(ReadingProgress).where(
                ReadingProgress.user_id == user.id,
                ReadingProgress.chapter_id == chapter_id,
            )
        )
    ).scalar_one_or_none()
    if progress is None:
        progress = ReadingProgress(
            user_id=user.id, series_id=chapter.series_id, chapter_id=chapter_id
        )
        session.add(progress)
    progress.completed = read
    progress.updated_at = utcnow()
    await session.commit()
    return {"ok": True, "read": read}
