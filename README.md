# InkVault

A fast, ad-free, single-library, self-hosted **manga & manhwa** reader.
You run it on your own server in Docker and use it from your phone as an
installed PWA. Unlike public aggregators, InkVault **downloads the whole
series and compresses every image to WebP** the first time you read it, so
future reads are instant and storage stays small.

> Personal, self-hosted tool. Source adapters scrape sites that host
> scanlations without a license — keep your instance private and respect
> source rate limits.

## Highlights

- **Whole-series download on first read** — adding/opening a series queues a
  background job that downloads *every* chapter, not just the current one.
- **Compression pipeline** — every image is re-encoded to WebP (default
  quality `0.8`, configurable; AVIF optional) and packed into a per-chapter
  **CBZ**. Originals are discarded.
- **comick.io-style reader** — paged (LTR/RTL) for manga, continuous vertical
  (webtoon) for manhwa, minimal chrome, instant local page turns, resume.
- **Multi-user** with **per-user reading progress, library, and preferences**,
  all persisted server-side so it syncs across devices.
- **Discovery in its own Browse tab** — trending shelves + a deep multi-filter
  cross-source search, kept entirely separate from the minimal library/reader.
- **Cloudflare handling** via a FlareSolverr sidecar.
- **PWA** — installable, full-screen, offline app shell.

## Stack

- **Backend:** Python 3.11 + FastAPI (async), SQLModel + SQLite (Postgres-ready).
- **Image processing:** Pillow (WebP/AVIF), CBZ packaging.
- **Background jobs:** in-process asyncio worker with DB-persisted job state.
- **Frontend:** React + TypeScript + Vite, installable PWA (`vite-plugin-pwa`).
- **Cloudflare:** FlareSolverr sidecar container.

## Confirmed decisions

| Decision | Choice |
| --- | --- |
| Source | `comick` (configurable API host via `COMICK_API_URL`) |
| Compression | WebP @ `0.8` |
| HTTPS | via Tailscale / reverse proxy in front |
| Backend | Python / FastAPI |
| DB | SQLite (single-box); Postgres supported via `DATABASE_URL` |

> **Source note:** the original comick shut down and its data is now served by
> clone hosts on rotating domains, so the comick API host is **configurable**
> (`COMICK_API_URL`) rather than hard-coded. The pluggable adapter design means
> swapping or adding sources never touches the reader, library, download
> pipeline, or PWA. See [`docs/ADAPTERS.md`](docs/ADAPTERS.md).

## Quick start

```bash
cp .env.example .env
# edit .env: set ADMIN_PASSWORD and SECRET_KEY at minimum
docker compose up -d --build
```

Then open the app (default `http://localhost:8080`). Log in with the admin
account from `.env`. Put Tailscale / a reverse proxy in front for HTTPS so the
PWA installs.

**Full step-by-step setup** (Docker, Tailscale HTTPS, PWA install, backups,
Postgres, troubleshooting): see [`docs/INSTALL.md`](docs/INSTALL.md).

## Architecture

```
                 ┌──────────────┐
   PWA (React) ──┤   frontend   │  nginx: serves app, proxies /api -> backend
                 └──────┬───────┘
                        │ /api
                 ┌──────▼───────┐      ┌──────────────┐
                 │   backend    │◄────►│ flaresolverr │ (Cloudflare challenges)
                 │  FastAPI +   │      └──────────────┘
                 │  asyncio     │
                 │  worker      │
                 └──────┬───────┘
            ┌───────────┼────────────┐
        SQLite DB    CBZ library   adapters/ (comick, ...)
        (volume)     (volume)
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for details and
[`docs/ADAPTERS.md`](docs/ADAPTERS.md) for writing a new source adapter.

## Repository layout

```
backend/    FastAPI app, adapters, services, workers
frontend/   React + TS PWA
docs/        architecture & adapter docs
docker-compose.yml
.env.example
```
