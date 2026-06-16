"""Series details, chapter lists, and adding a series (triggers download)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..db import get_session
from ..models import (
    Chapter,
    DownloadJob,
    JobState,
    LibraryEntry,
    ReadingProgress,
    Series,
    User,
)
from ..schemas import AddSeriesRequest, ChapterOut, JobOut, SeriesOut
from ..services.downloader import sync_chapters
from ..services.series_service import (
    build_series_out,
    ensure_series_from_source,
)
from ..workers.queue import enqueue_download

router = APIRouter(prefix="/api/series", tags=["series"])


async def _queue_full_download(session: AsyncSession, series: Series) -> DownloadJob:
    """Enqueue a whole-series download job (skips if one is active)."""
    active = (
        await session.execute(
            select(DownloadJob).where(
                DownloadJob.series_id == series.id,
                DownloadJob.state.in_([JobState.queued, JobState.running]),
            )
        )
    ).scalar_one_or_none()
    if active:
        return active
    job = DownloadJob(series_id=series.id)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    await enqueue_download(job.id)
    return job


@router.post("", response_model=SeriesOut, status_code=201)
async def add_series(
    body: AddSeriesRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Add a series to the user's library and queue a whole-series download."""
    series = await ensure_series_from_source(session, body.source, body.source_id)

    # follow
    existing = (
        await session.execute(
            select(LibraryEntry).where(
                LibraryEntry.user_id == user.id, LibraryEntry.series_id == series.id
            )
        )
    ).scalar_one_or_none()
    if not existing:
        session.add(LibraryEntry(user_id=user.id, series_id=series.id))
        await session.commit()

    await _queue_full_download(session, series)
    return await build_series_out(session, series, user.id)


@router.get("/{series_id}", response_model=SeriesOut)
async def get_series(
    series_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    series = await session.get(Series, series_id)
    if not series:
        raise HTTPException(404, "Series not found")
    return await build_series_out(session, series, user.id)


@router.get("/{series_id}/chapters", response_model=list[ChapterOut])
async def list_series_chapters(
    series_id: int,
    refresh: bool = False,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    series = await session.get(Series, series_id)
    if not series:
        raise HTTPException(404, "Series not found")

    async def _load() -> list[Chapter]:
        return list(
            (
                await session.execute(
                    select(Chapter)
                    .where(Chapter.series_id == series_id)
                    .order_by(Chapter.number)
                )
            ).scalars().all()
        )

    chapters = await _load()

    # Lazy fallback: if the chapter list is empty (e.g. a download job failed or
    # hasn't started) and no job is currently populating it, sync inline so the
    # series page is never stuck empty.
    if refresh or not chapters:
        active = (
            await session.execute(
                select(DownloadJob).where(
                    DownloadJob.series_id == series_id,
                    DownloadJob.state.in_([JobState.queued, JobState.running]),
                )
            )
        ).scalar_one_or_none()
        if refresh or not active:
            try:
                await sync_chapters(session, series)
                chapters = await _load()
            except Exception:  # noqa: BLE001 - surface as empty rather than 500
                pass

    # Batch-load this user's progress for the whole series in one query to
    # avoid an N+1 (this endpoint is polled while downloads run).
    progress_rows = (
        await session.execute(
            select(ReadingProgress).where(
                ReadingProgress.user_id == user.id,
                ReadingProgress.series_id == series_id,
            )
        )
    ).scalars().all()
    prog = {p.chapter_id: p for p in progress_rows}

    out = []
    for c in chapters:
        p = prog.get(c.id)
        out.append(
            ChapterOut(
                id=c.id,
                number=c.number,
                number_label=c.number_label,
                volume=c.volume,
                title=c.title,
                language=c.language,
                scanlation_group=c.scanlation_group,
                page_count=c.page_count,
                downloaded=c.downloaded,
                size_bytes=c.size_bytes,
                read=p.completed if p else False,
                current_page=p.page if p else 0,
            )
        )
    return out


@router.post("/{series_id}/download", response_model=JobOut)
async def trigger_download(
    series_id: int,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    series = await session.get(Series, series_id)
    if not series:
        raise HTTPException(404, "Series not found")
    job = await _queue_full_download(session, series)
    return JobOut(**job.model_dump())
