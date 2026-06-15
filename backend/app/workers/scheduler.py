"""Periodic auto-update of followed series.

Every AUTO_UPDATE_INTERVAL_MINUTES, any series that at least one user follows
is re-checked for new chapters; new ones are downloaded + compressed via a
fresh download job.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from ..config import settings
from ..db import async_session
from ..models import DownloadJob, JobState, LibraryEntry, Series
from .queue import enqueue_download

log = logging.getLogger("inkvault.scheduler")

_task: asyncio.Task | None = None


async def _check_once() -> None:
    async with async_session() as s:
        followed_ids = (
            await s.execute(select(LibraryEntry.series_id).distinct())
        ).scalars().all()
        for sid in followed_ids:
            series = await s.get(Series, sid)
            if not series:
                continue
            # Skip if a job is already active for this series.
            active = (
                await s.execute(
                    select(DownloadJob).where(
                        DownloadJob.series_id == sid,
                        DownloadJob.state.in_([JobState.queued, JobState.running]),
                    )
                )
            ).first()
            if active:
                continue
            job = DownloadJob(series_id=sid)
            s.add(job)
            await s.commit()
            await s.refresh(job)
            await enqueue_download(job.id)
            log.info("auto-update queued job %s for series %s", job.id, sid)


async def _loop() -> None:
    interval = settings.auto_update_interval_minutes
    while True:
        await asyncio.sleep(interval * 60)
        try:
            await _check_once()
        except Exception:  # noqa: BLE001
            log.exception("auto-update cycle failed")


async def start_scheduler() -> None:
    global _task
    if settings.auto_update_interval_minutes <= 0:
        log.info("auto-update disabled")
        return
    _task = asyncio.create_task(_loop())


async def stop_scheduler() -> None:
    if _task:
        _task.cancel()
