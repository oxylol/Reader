"""In-process asyncio job queue with DB-persisted job state.

Single-box friendly: no Redis required. Job *state* lives in the DB so it
survives restarts; on startup, any jobs left `running`/`queued` are re-queued.
If you outgrow one box, swap this for Redis + an external worker without
touching the routers (they only enqueue via `enqueue_download`).
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from ..db import async_session
from ..models import DownloadJob, JobState
from ..services.downloader import run_download_job

log = logging.getLogger("inkvault.queue")

_queue: "asyncio.Queue[int]" = asyncio.Queue()
_workers: list[asyncio.Task] = []
_running = False


async def enqueue_download(job_id: int) -> None:
    await _queue.put(job_id)


async def _worker_loop(worker_id: int) -> None:
    while True:
        job_id = await _queue.get()
        try:
            log.info("worker %s picked job %s", worker_id, job_id)
            await run_download_job(async_session, job_id)
        except Exception:  # noqa: BLE001
            log.exception("job %s crashed", job_id)
        finally:
            _queue.task_done()


async def start_workers(n: int = 2) -> None:
    global _running
    if _running:
        return
    _running = True
    for i in range(n):
        _workers.append(asyncio.create_task(_worker_loop(i)))
    # Re-queue jobs that were interrupted by a restart.
    async with async_session() as s:
        rows = (
            await s.execute(
                select(DownloadJob).where(
                    DownloadJob.state.in_([JobState.queued, JobState.running])
                )
            )
        ).scalars().all()
        for job in rows:
            job.state = JobState.queued
            await s.commit()
            await enqueue_download(job.id)
    log.info("started %s download workers, re-queued %s jobs", n, len(rows))


async def stop_workers() -> None:
    for t in _workers:
        t.cancel()
    _workers.clear()
