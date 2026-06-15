# Writing a source adapter

Each source is a self-contained module implementing `SourceAdapter`
(`backend/app/adapters/base.py`). The core never imports a concrete adapter; it
goes through the registry, so adding a source means adding one file and one line.

## Interface

```python
class SourceAdapter(ABC):
    key: str                 # unique short id, e.g. "comick"
    name: str                # human label
    base_url: str
    needs_cloudflare: bool   # route requests through FlareSolverr
    supports_trending: bool
    supports_advanced_search: bool

    async def search(self, filters: SearchFilters) -> list[SeriesResult]: ...
    async def trending(self, params: TrendingParams) -> list[SeriesResult]: ...
    async def get_series(self, source_id: str) -> SeriesResult: ...
    async def list_chapters(self, source_id, language="en") -> list[ChapterResult]: ...
    async def get_page_urls(self, source_chapter_id: str) -> list[str]: ...
```

Return the plain dataclasses from `adapters/base.py` (`SeriesResult`,
`ChapterResult`) — they're decoupled from the DB models, and the core maps them
into the database for you.

## HTTP & Cloudflare

Use the shared client so rate-limiting, retries, and Cloudflare solving are
handled for you:

```python
from ..services import http

data = await http.fetch_json(url, needs_cloudflare=self.needs_cloudflare)
raw  = await http.fetch_bytes(image_url, needs_cloudflare=self.needs_cloudflare)
```

If a request unexpectedly hits a Cloudflare challenge (403/503), the client
automatically solves it once via FlareSolverr and retries. Clearance cookies are
cached per-domain.

## Registering

Add your adapter to `adapters/registry.py`:

```python
def _bootstrap() -> None:
    from .comick import ComickAdapter
    from .mysource import MySourceAdapter   # <-- new

    register(ComickAdapter())
    register(MySourceAdapter())             # <-- new
```

That's it — it now appears in `GET /api/browse/sources`, participates in
cross-source search/trending (with de-duplication), and can back downloads.

## Conventions
- Respect `SOURCE_RATE_LIMIT_SECONDS` between page requests (the downloader
  already sleeps between pages; keep extra per-source politeness inside the
  adapter if the site needs it).
- Set a sane `User-Agent`/`Referer` (the shared client sets a browser UA by
  default).
- Map the site's type/status vocab to ours: type ∈ {manga, manhwa, manhua},
  status ∈ {ongoing, completed, hiatus, cancelled}.

## Reference: the comick adapter
See `backend/app/adapters/comick.py`. It uses comick's JSON API
(`api.comick.fun`), maps country → type (`jp`→manga, `kr`→manhwa, `cn`→manhua),
and builds image URLs from `meo.comick.pictures/{b2key}`.
