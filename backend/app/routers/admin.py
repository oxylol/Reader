"""Admin: download jobs, storage dashboard, pruning. Admin-only."""
from __future__ import annotations

import shutil

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters import list_adapters
from ..adapters.base import SearchFilters, TrendingParams
from ..config import settings
from ..core.deps import get_current_admin, get_current_user
from ..db import get_session
from ..models import Chapter, DownloadJob, JobState, Series, User
from ..schemas import JobOut, StorageSeries, StorageStats
from ..services import storage

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/sources/diagnose")
async def diagnose_sources(
    q: str = "solo",
    _: User = Depends(get_current_admin),
):
    """Live-test each adapter from inside the server's network.

    Returns the real error for each source so empty Browse results can be
    diagnosed (wrong API host, Cloudflare challenge, network block, etc.).
    """
    out: list[dict] = []
    for adapter in list_adapters():
        entry: dict = {
            "key": adapter.key,
            "name": adapter.name,
            "base_url": adapter.base_url,
            "needs_cloudflare": adapter.needs_cloudflare,
        }
        if adapter.key == "comick":
            entry["api_url"] = settings.comick_api_url
        # trending
        try:
            t = await adapter.trending(TrendingParams())
            entry["trending_count"] = len(t)
            entry["trending_sample"] = t[0].title if t else None
        except Exception as exc:  # noqa: BLE001
            entry["trending_error"] = f"{type(exc).__name__}: {exc}"
        # search
        try:
            s = await adapter.search(SearchFilters(query=q, limit=5))
            entry["search_count"] = len(s)
            entry["search_sample"] = s[0].title if s else None
        except Exception as exc:  # noqa: BLE001
            entry["search_error"] = f"{type(exc).__name__}: {exc}"
        out.append(entry)
    return out


@router.get("/jobs", response_model=list[JobOut])
async def list_jobs(
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (
        await session.execute(
            select(DownloadJob).order_by(DownloadJob.created_at.desc()).limit(50)
        )
    ).scalars().all()
    return [JobOut(**j.model_dump()) for j in rows]


@router.get("/jobs/series/{series_id}", response_model=JobOut | None)
async def job_for_series(
    series_id: int,
    _: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    row = (
        await session.execute(
            select(DownloadJob)
            .where(DownloadJob.series_id == series_id)
            .order_by(DownloadJob.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return JobOut(**row.model_dump()) if row else None


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
async def cancel_job(
    job_id: int,
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(DownloadJob, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.state in (JobState.queued, JobState.running):
        job.state = JobState.cancelled
        job.message = "cancelled"
        await session.commit()
    return JobOut(**job.model_dump())


@router.get("/storage", response_model=StorageStats)
async def storage_stats(
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    series_rows = (await session.execute(select(Series))).scalars().all()
    per_series: list[StorageSeries] = []
    total = 0
    chapter_total = 0
    for s in series_rows:
        size = (
            await session.execute(
                select(func.coalesce(func.sum(Chapter.size_bytes), 0)).where(
                    Chapter.series_id == s.id
                )
            )
        ).scalar_one()
        count = (
            await session.execute(
                select(func.count(Chapter.id)).where(
                    Chapter.series_id == s.id, Chapter.downloaded == True  # noqa: E712
                )
            )
        ).scalar_one()
        if size or count:
            per_series.append(
                StorageSeries(
                    series_id=s.id, title=s.title, size_bytes=size, chapter_count=count
                )
            )
            total += size
            chapter_total += count
    per_series.sort(key=lambda x: x.size_bytes, reverse=True)
    return StorageStats(
        total_bytes=total,
        series_count=len(per_series),
        chapter_count=chapter_total,
        series=per_series,
    )


@router.delete("/storage/series/{series_id}", status_code=204)
async def prune_series(
    series_id: int,
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Delete downloaded files for a series (keeps DB metadata + progress)."""
    series = await session.get(Series, series_id)
    if not series:
        raise HTTPException(404, "Series not found")
    sdir = storage.series_dir(series)
    if sdir.exists():
        shutil.rmtree(sdir, ignore_errors=True)
    chapters = (
        await session.execute(select(Chapter).where(Chapter.series_id == series_id))
    ).scalars().all()
    for c in chapters:
        c.downloaded = False
        c.cbz_path = ""
        c.size_bytes = 0
        c.page_count = 0
    await session.commit()
