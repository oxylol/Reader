# InkVault — Installation Guide

A complete, from-scratch guide to running InkVault on your own Ubuntu server
with Docker, exposed privately over HTTPS via Tailscale.

> **Heads up:** InkVault's source adapters scrape sites that host scanlations
> without a license — the same legal gray area as the public aggregators it
> replaces. Keep your instance **private** (Tailscale, not a public domain) and
> respect source rate limits.

---

## Contents

1. [What you'll end up with](#1-what-youll-end-up-with)
2. [Requirements](#2-requirements)
3. [Install Docker](#3-install-docker)
4. [Get the code](#4-get-the-code)
5. [Configure `.env`](#5-configure-env)
6. [First start](#6-first-start)
7. [HTTPS with Tailscale (recommended)](#7-https-with-tailscale-recommended)
8. [Install the PWA on your phone](#8-install-the-pwa-on-your-phone)
9. [First run: add a series & read](#9-first-run-add-a-series--read)
10. [Day-2 operations](#10-day-2-operations)
11. [Configuration reference](#11-configuration-reference)
12. [Using PostgreSQL instead of SQLite](#12-using-postgresql-instead-of-sqlite)
13. [Backups](#13-backups)
14. [Updating](#14-updating)
15. [Troubleshooting](#15-troubleshooting)
16. [Uninstall](#16-uninstall)

---

## 1. What you'll end up with

Three containers managed by Docker Compose:

| Container | Role | Port |
| --- | --- | --- |
| `frontend` | nginx serving the React PWA + proxying `/api` | `8080` (host) |
| `backend` | FastAPI app + download/compress workers | internal only |
| `flaresolverr` | solves Cloudflare challenges for protected sources | internal only |

All persistent data (SQLite DB + compressed CBZ library) lives in a single
Docker named volume, so container rebuilds never lose your library or progress.

```
Phone (PWA) ──HTTPS──> Tailscale ──> :8080 frontend ──/api──> backend ──> flaresolverr
                                                              │
                                                          data volume
                                                       (DB + CBZ library)
```

---

## 2. Requirements

- **Ubuntu 22.04 / 24.04** (or any Linux that runs Docker). amd64 or arm64.
- **2 GB RAM** minimum (4 GB comfortable — image re-encoding is CPU/RAM bound).
- **Disk**: a few GB to start; compressed series are small (WebP @ 0.8 is
  typically 50–80% smaller than source), but a large library still adds up.
- **A Tailscale account** (free) if you want HTTPS without a public domain.
- Outbound internet from the server (to reach the source site + FlareSolverr's
  image fetches).

---

## 3. Install Docker

```bash
# Official convenience script
curl -fsSL https://get.docker.com | sudo sh

# Run docker without sudo (log out/in afterwards)
sudo usermod -aG docker "$USER"

# Verify
docker --version
docker compose version
```

If `docker compose version` fails, install the plugin:

```bash
sudo apt-get update && sudo apt-get install -y docker-compose-plugin
```

---

## 4. Get the code

```bash
git clone https://github.com/oxylol/reader.git inkvault
cd inkvault
```

> Replace the URL with your fork if you have one.

---

## 5. Configure `.env`

Copy the template and edit it:

```bash
cp .env.example .env
nano .env
```

**You must change at least these two values:**

```ini
# Generate with: openssl rand -hex 32
SECRET_KEY=<paste a long random hex string>

# Your admin login (created automatically on first start)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<a strong password>
```

Sensible defaults are already set for everything else (WebP @ 0.8, SQLite,
4 parallel downloads, 6-hour auto-update). See the
[configuration reference](#11-configuration-reference) for the full list.

Generate a strong secret quickly:

```bash
echo "SECRET_KEY=$(openssl rand -hex 32)"
```

---

## 6. First start

```bash
docker compose up -d --build
```

The first build takes a few minutes (it builds the frontend and installs Python
deps). Once it's up:

```bash
# Watch logs until you see "InkVault backend ready"
docker compose logs -f backend

# Health check
curl http://localhost:8080/api/health
# -> {"status":"ok","version":"0.1.0"}
```

Open `http://<server-ip>:8080` in a browser and log in with the admin
credentials from your `.env`. You now have a working instance over plain HTTP on
your LAN. Next, add HTTPS so the PWA installs.

---

## 7. HTTPS with Tailscale (recommended)

A PWA only installs over HTTPS. Tailscale gives you a free, valid TLS
certificate on a private network — no public exposure, no domain to buy.

### 7.1 Install Tailscale on the server

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

Follow the printed link to authenticate. Note your machine's name, e.g.
`my-server`, and your tailnet, e.g. `tailxxxx.ts.net`.

### 7.2 Enable HTTPS in the Tailscale admin

In the [Tailscale admin console](https://login.tailscale.com/admin/dns):
enable **MagicDNS** and **HTTPS Certificates**.

### 7.3 Serve InkVault over HTTPS

Tailscale's built-in proxy terminates TLS and forwards to InkVault's port `8080`:

```bash
sudo tailscale serve --bg 8080
```

That publishes `https://my-server.tailxxxx.ts.net` to every device on your
tailnet. Check it:

```bash
tailscale serve status
```

Now install Tailscale on your phone and join the same tailnet — you can reach
the HTTPS URL from anywhere.

> **Alternative (public domain + Caddy/Nginx):** if you'd rather use a real
> domain, point a reverse proxy at `127.0.0.1:8080` and let it handle TLS (e.g.
> a two-line Caddyfile: `your.domain { reverse_proxy 127.0.0.1:8080 }`). Only do
> this if you understand the legal note at the top.

---

## 8. Install the PWA on your phone

Open `https://my-server.tailxxxx.ts.net` in your phone browser:

- **iOS / Safari:** Share → **Add to Home Screen**.
- **Android / Chrome:** menu (⋮) → **Install app** / **Add to Home screen**.

Launch from the home-screen icon — it opens full-screen (no browser chrome),
caches the app shell for instant cold starts, and resumes where you left off.

---

## 9. First run: add a series & read

1. Tap the **Browse** tab.
2. Either scroll **Trending** or switch to **Search**, type a title, and apply
   filters (type, status, genres include/exclude, year, sort).
3. Tap **+ Add** on a series. This:
   - adds it to your **Library**, and
   - queues a **whole-series download** — every chapter is fetched and each page
     re-encoded to WebP, packed into a per-chapter CBZ.
4. Open the series page to watch the download progress bar. Reading is available
   as soon as the first chapters land.
5. Tap a downloaded chapter to open the **Reader**:
   - **Manhwa/manhua** auto-open in webtoon (vertical) mode; **manga** in paged
     mode. Override per series or globally in **Settings**.
   - Tap **center** to toggle chrome; tap **left/right** edges to turn pages
     (paged); pinch to zoom; it always resumes at your exact position.

---

## 10. Day-2 operations

All admin tools live in **Settings** (admin accounts only):

- **Users** — create standard/admin accounts; each gets their own library and
  progress. Standard users never see admin/acquisition screens.
- **Download jobs** — live status; cancel a running job.
- **Storage** — total size, per-series breakdown, and **Prune** to reclaim space
  (deletes downloaded files, keeps metadata + your progress so you can
  re-download later).
- **Reader defaults** — mode, fit, LTR/RTL, dark/light theme.

**Auto-update:** followed series are re-checked every
`AUTO_UPDATE_INTERVAL_MINUTES` (default 6h) and new chapters download
automatically. Set to `0` to disable.

Useful commands:

```bash
docker compose ps                 # status
docker compose logs -f backend    # follow backend logs
docker compose restart backend    # restart after config change
docker compose down               # stop everything (keeps data volume)
```

---

## 11. Configuration reference

All settings live in `.env` (see `.env.example`). Changes take effect after
`docker compose up -d`.

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | — | **Required.** JWT signing key. `openssl rand -hex 32`. |
| `ADMIN_USERNAME` | `admin` | Bootstrap admin, created if no users exist. |
| `ADMIN_PASSWORD` | `changeme` | **Change this.** Bootstrap admin password. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `43200` | Login lifetime (default 30 days). |
| `DATABASE_URL` | SQLite at `/data/inkvault.db` | DB connection. See §12 for Postgres. |
| `LIBRARY_DIR` | `/data/library` | Where CBZs are stored (inside the volume). |
| `IMAGE_FORMAT` | `webp` | `webp` or `avif` (AVIF needs Pillow AVIF support; falls back to WebP). |
| `IMAGE_QUALITY` | `0.8` | `0.0`–`1.0` encoder quality. |
| `MAX_PARALLEL_DOWNLOADS` | `4` | Concurrent chapter downloads. |
| `SOURCE_RATE_LIMIT_SECONDS` | `0.5` | Polite delay between page requests. |
| `FLARESOLVERR_URL` | `http://flaresolverr:8191/v1` | Cloudflare solver endpoint. |
| `AUTO_UPDATE_INTERVAL_MINUTES` | `360` | Followed-series re-check interval; `0` disables. |
| `APP_PORT` | `8080` | Host port the app is served on. |

---

## 12. Using PostgreSQL instead of SQLite

SQLite is the default and fine for a single-box, single-household setup. For
heavier multi-user use, switch to Postgres:

1. In `docker-compose.yml`, **uncomment** the `db:` service and the `pgdata`
   volume.
2. In `backend/requirements.txt`, **uncomment** `asyncpg`.
3. In `.env`, set:
   ```ini
   DATABASE_URL=postgresql+asyncpg://inkvault:inkvault@db:5432/inkvault
   ```
4. Rebuild:
   ```bash
   docker compose up -d --build
   ```

Tables are created automatically on startup. (There's no automated SQLite→
Postgres data migration — switch before building a large library, or re-add
series afterward.)

---

## 13. Backups

Everything important is in the `data` Docker volume (DB + CBZ library). Back it
up while the stack is stopped for a consistent snapshot:

```bash
docker compose down
docker run --rm -v inkvault_data:/data -v "$PWD":/backup alpine \
  tar czf /backup/inkvault-backup-$(date +%F).tar.gz -C /data .
docker compose up -d
```

Restore:

```bash
docker compose down
docker run --rm -v inkvault_data:/data -v "$PWD":/backup alpine \
  sh -c "rm -rf /data/* && tar xzf /backup/inkvault-backup-YYYY-MM-DD.tar.gz -C /data"
docker compose up -d
```

> The volume name is `<project>_data`; the project defaults to the folder name
> (`inkvault`). Confirm with `docker volume ls`.

---

## 14. Updating

```bash
cd inkvault
git pull
docker compose pull            # refresh flaresolverr image
docker compose up -d --build   # rebuild app images
```

Your data volume is untouched. The PWA auto-updates its service worker on next
launch.

---

## 15. Troubleshooting

**`docker compose` says `.env` not found**
Run commands from the repo root where your `.env` lives, or pass
`--env-file ./.env`.

**Can't log in / "Bad credentials"**
The admin account is created **only when the database has no users**. If you
changed `ADMIN_PASSWORD` after first start, it won't retroactively apply —
create/reset the user from another admin in Settings, or wipe the volume to
re-bootstrap (destroys data).

**PWA won't install / no "Add to Home Screen"**
You must be on **HTTPS**. Use the Tailscale URL (§7), not the raw
`http://ip:8080`.

**Downloads stay at 0 or jobs fail**
Check `docker compose logs -f backend`. Common causes:
- Source temporarily unreachable or rate-limiting — InkVault retries with
  backoff; lower `MAX_PARALLEL_DOWNLOADS` and raise `SOURCE_RATE_LIMIT_SECONDS`
  if you're being throttled.
- Cloudflare challenge — confirm flaresolverr is healthy:
  `docker compose logs flaresolverr`.

**Cloudflare solver errors / high memory**
FlareSolverr runs a headless browser and is memory-hungry. Ensure the host has
enough RAM; restart it with `docker compose restart flaresolverr`.

**Images are slow to encode on a Raspberry Pi**
Lower `MAX_PARALLEL_DOWNLOADS` (e.g. `2`) so encoding doesn't saturate the CPU,
and/or raise `IMAGE_QUALITY` slightly to trade size for speed.

**Reset everything (destroys library + DB):**
```bash
docker compose down -v
```

---

## 16. Uninstall

```bash
docker compose down -v        # stop + delete the data volume
cd .. && rm -rf inkvault      # remove the code
sudo tailscale serve --https=443 off   # if you used Tailscale serve
```

---

Need to add a new source site? See [`docs/ADAPTERS.md`](ADAPTERS.md). For how it
all fits together, see [`docs/ARCHITECTURE.md`](ARCHITECTURE.md).
