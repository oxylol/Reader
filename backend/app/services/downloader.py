"""Whole-series download + compression orchestration."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters import get_adapter
from ..config import settings
from ..models import Chapter, DownloadJob, JobState, Series
from . import http, storage
from .compress import CbzWriter, compress_image

log = logging.getLogger("inkvault.downloader")


async def sync_chapters(session: AsyncSession, series: Series) -> list[Chapter]:
    """Fetch the chapter list from the source and upsert into the DB.

    De-duplicates by chapter number, keeping the first (newest group) entry.
    """
    adapter = get_adapter(series.source)
    remote = await adapter.list_chapters(series.source_id)

    seen: dict[float, object] = {}
    for ch in remote:
        if ch.number not in seen:
            seen[ch.number] = ch

    existing = (
        await session.execute(select(Chapter).where(Chapter.series_id == series.id))
    ).scalars().all()
    by_src = {c.source_chapter_id: c for c in existing}

    chapters: list[Chapter] = []
    for ch in seen.values():
        row = by_src.get(ch.source_chapter_id)
        if row is None:
            row = Chapter(
                series_id=series.id,
                source_chapter_id=ch.source_chapter_id,
                number=ch.number,
                number_label=ch.number_label,
                volume=ch.volume,
                title=ch.title,
                language=ch.language,
                scanlation_group=ch.scanlation_group,
            )
            session.add(row)
        chapters.append(row)
    await session.commit()
    for c in chapters:
        await session.refresh(c)
    return chapters


async def _download_chapter(series: Series, chapter: Chapter) -> tuple[int, int]:
    """Download + compress one chapter into a CBZ. Returns (pages, bytes)."""
    adapter = get_adapter(series.source)
    urls = await adapter.get_page_urls(chapter.source_chapter_id)
    if not urls:
        raise RuntimeError("no pages returned")

    dest = storage.chapter_cbz_path(series, chapter)
    writer = CbzWriter(dest)
    try:
        for i, url in enumerate(urls):
            raw = await http.fetch_bytes(url, needs_cloudflare=adapter.needs_cloudflare)
            compressed = await asyncio.to_thread(compress_image, raw)
            writer.add_page(i, compressed)
            if settings.source_rate_limit_seconds:
                await asyncio.sleep(settings.source_rate_limit_seconds)
        size = writer.finalize()
    except Exception:
        writer.abort()
        raise
    return writer.page_count, size


async def run_download_job(session_factory, job_id: int) -> None:
    """Execute a queued download job: sync chapters then fetch all of them."""
    async with session_factory() as session:
        job = await session.get(DownloadJob, job_id)
        if job is None or job.state in (JobState.cancelled, JobState.done):
            return
        series = await session.get(Series, job.series_id)
        if series is None:
            job.state = JobState.failed
            job.message = "series missing"
            await session.commit()
            return

        job.state = JobState.running
        job.message = "listing chapters"
        await session.commit()

        try:
            chapters = await sync_chapters(session, series)
        except Exception as exc:  # noqa: BLE001
            log.exception("chapter sync failed")
            job.state = JobState.failed
            job.message = f"chapter list failed: {exc}"
            await session.commit()
            return

        pending = [c for c in chapters if not c.downloaded]
        job.total_chapters = len(chapters)
        job.done_chapters = len(chapters) - len(pending)
        job.message = f"{job.done_chapters}/{job.total_chapters} chapters"
        await session.commit()

        sem = asyncio.Semaphore(max(1, settings.max_parallel_downloads))

        async def worker(chapter_id: int) -> None:
            async with sem:
                async with session_factory() as s2:
                    job2 = await s2.get(DownloadJob, job_id)
                    if job2 is None or job2.state == JobState.cancelled:
                        return
                    ch = await s2.get(Chapter, chapter_id)
                    ser = await s2.get(Series, series.id)
                    ok = False
                    try:
                        pages, size = await _download_chapter(ser, ch)
                        ch.downloaded = True
                        ch.page_count = pages
                        ch.size_bytes = size
                        ch.cbz_path = storage.relative_path(
                            storage.chapter_cbz_path(ser, ch)
                        )
                        ok = True
                    except Exception as exc:  # noqa: BLE001
                        log.warning("chapter %s failed: %s", chapter_id, exc)
                    await s2.commit()

            # Atomic counter bump in its own statement to avoid lost updates
            # when many workers finish concurrently.
            async with session_factory() as sc:
                col = DownloadJob.done_chapters if ok else DownloadJob.failed_chapters
                await sc.execute(
                    update(DownloadJob)
                    .where(DownloadJob.id == job_id)
                    .values({col: col + 1, DownloadJob.updated_at: datetime.utcnow()})
                )
                await sc.commit()

        await asyncio.gather(*(worker(c.id) for c in pending))

        async with session_factory() as s3:
            job3 = await s3.get(DownloadJob, job_id)
            if job3 and job3.state != JobState.cancelled:
                job3.state = JobState.done
                job3.message = (
                    f"done: {job3.done_chapters}/{job3.total_chapters}"
                    + (f" ({job3.failed_chapters} failed)" if job3.failed_chapters else "")
                )
                series_row = await s3.get(Series, series.id)
                if series_row:
                    series_row.updated_at = datetime.utcnow()
                await s3.commit()
