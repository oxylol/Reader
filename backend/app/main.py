"""InkVault FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import async_session, init_db
from .routers import admin, auth, browse, library, prefs, reader, series
from .services.http import close_client
from .workers.queue import start_workers, stop_workers
from .workers.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("inkvault")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with async_session() as session:
        await auth.ensure_bootstrap_admin(
            session, settings.admin_username, settings.admin_password
        )
    await start_workers(n=max(1, settings.max_parallel_downloads // 2 or 1))
    await start_scheduler()
    log.info("InkVault backend ready")
    yield
    await stop_scheduler()
    await stop_workers()
    await close_client()


app = FastAPI(title="InkVault", version="0.1.0", lifespan=lifespan)

# CORS is permissive for local/dev; in production the frontend is same-origin
# behind nginx so this mostly matters for `vite dev`.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth, library, series, browse, reader, prefs, admin):
    app.include_router(r.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": app.version}
