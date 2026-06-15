# Architecture

## Overview

InkVault is three containers behind a reverse proxy (Tailscale provides HTTPS):

- **frontend** — nginx serving the built React PWA and proxying `/api` → backend.
- **backend** — FastAPI app + in-process asyncio download/compress workers.
- **flaresolverr** — headless solver for Cloudflare-protected sources.

All persistent state lives in a single `data` volume:

```
/data/
  inkvault.db          # SQLite (or use external Postgres via DATABASE_URL)
  library/
    {source}/{slug}-{source_id}/
      ch-{label}-{chapter_id}.cbz   # compressed WebP pages, zipped
```

## Request / data flow

### Adding & downloading a series
1. `POST /api/series {source, source_id}` upserts the series, follows it for the
   user, and enqueues a **whole-series** `DownloadJob`.
2. The asyncio worker (`workers/queue.py`) runs `services/downloader.py`:
   - `sync_chapters` pulls the full chapter list from the adapter and de-dupes
     by chapter number.
   - Each chapter is fetched page-by-page through `services/http.py` (routing
     through FlareSolverr when the adapter declares `needs_cloudflare`),
     re-encoded to WebP via `services/compress.py`, and packed into a CBZ.
   - Job progress (`done/total/failed`) is written to the DB so the UI can poll
     `GET /api/admin/jobs/series/{id}`.
3. Reading is available as soon as the first chapters' CBZs land.

### Reading
- `GET /api/read/chapter/{id}` returns chapter info + prev/next ids.
- `GET /api/read/chapter/{id}/page/{index}` streams a single compressed page
  straight out of the CBZ with a long immutable cache header. No remote fetch
  happens mid-read — everything is local + compressed, so page turns are
  instant. The service worker also runtime-caches these.
- `PUT /api/read/progress` persists `{page, scroll, completed}` per user, so
  resume works across devices.

### Discovery (Browse tab)
- `GET /api/browse/trending` and `POST /api/browse/search` fan out across every
  registered adapter concurrently, then **de-duplicate** the same series seen on
  multiple sources by fuzzy title match (`difflib`). Kept entirely separate from
  the library/reader endpoints.

## Background work
- **Download queue** (`workers/queue.py`): in-process asyncio queue; job *state*
  is in the DB so it survives restarts (interrupted jobs are re-queued on boot).
  Concurrency is bounded by `MAX_PARALLEL_DOWNLOADS`.
- **Scheduler** (`workers/scheduler.py`): every
  `AUTO_UPDATE_INTERVAL_MINUTES`, re-checks each followed series and enqueues a
  job to fetch any new chapters.

To scale beyond one box, swap the asyncio queue for Redis + an external worker;
routers only ever call `enqueue_download`, so nothing else changes.

## Data model (SQLite/Postgres via SQLModel)
- `User`, `UserPrefs`, `SeriesModeOverride`
- `Series`, `Chapter`
- `LibraryEntry` (user ↔ series follow), `ReadingProgress` (per user/chapter)
- `DownloadJob`
- `SavedSearch`, `SearchHistory`

## Why these choices
- **SQLite default**: single-box simplicity; Postgres is a one-line
  `DATABASE_URL` swap (driver already async).
- **Pillow** for WebP: ships manylinux wheels with libwebp, no system deps;
  swap to pyvips later for speed if needed (the encoder lives behind
  `services/compress.py`).
- **CBZ per chapter**: portable, inspectable, plays nicely with a future OPDS
  feed, and keeps one file per chapter for easy pruning.
