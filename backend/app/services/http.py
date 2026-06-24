"""Shared HTTP client and FlareSolverr-backed fetch.

Adapters use `fetch_json` / `fetch_bytes`. When a source declares
`needs_cloudflare`, requests are routed through FlareSolverr to obtain valid
clearance cookies, which are then cached and reused for subsequent direct
requests.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

import httpx

from ..config import settings

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# domain -> {"cookies": {...}, "ua": str, "ts": float}
_cf_cache: dict[str, dict[str, Any]] = {}
_cf_ttl = 60 * 20  # 20 min

_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={"User-Agent": DEFAULT_UA},
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _solve_cloudflare(url: str) -> dict[str, Any]:
    """Ask FlareSolverr to fetch a URL, returning cookies + UA."""
    payload = {"cmd": "request.get", "url": url, "maxTimeout": 60000}
    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as c:
        r = await c.post(settings.flaresolverr_url, json=payload)
        r.raise_for_status()
        data = r.json()
    sol = data.get("solution", {})
    cookies = {ck["name"]: ck["value"] for ck in sol.get("cookies", [])}
    ua = sol.get("userAgent", DEFAULT_UA)
    return {"cookies": cookies, "ua": ua, "ts": time.time(), "html": sol.get("response")}


def _domain(url: str) -> str:
    return httpx.URL(url).host or url


async def _ensure_clearance(url: str) -> dict[str, Any]:
    dom = _domain(url)
    cached = _cf_cache.get(dom)
    if cached and (time.time() - cached["ts"]) < _cf_ttl:
        return cached
    sol = await _solve_cloudflare(url)
    _cf_cache[dom] = sol
    return sol


async def fetch_json(
    url: str,
    *,
    needs_cloudflare: bool = False,
    headers: Optional[dict[str, str]] = None,
    params: Optional[dict[str, Any]] = None,
    retries: int = 3,
) -> Any:
    raw = await fetch_bytes(
        url,
        needs_cloudflare=needs_cloudflare,
        headers=headers,
        params=params,
        retries=retries,
    )
    return json.loads(raw)


async def fetch_bytes(
    url: str,
    *,
    needs_cloudflare: bool = False,
    headers: Optional[dict[str, str]] = None,
    params: Optional[dict[str, Any]] = None,
    retries: int = 3,
) -> bytes:
    client = get_client()
    req_headers = dict(headers or {})
    cookies = None

    if needs_cloudflare:
        clearance = await _ensure_clearance(url)
        cookies = clearance["cookies"]
        req_headers.setdefault("User-Agent", clearance["ua"])

    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            r = await client.get(
                url, headers=req_headers, params=params, cookies=cookies
            )
            if r.status_code in (403, 503) and not needs_cloudflare:
                # Hit Cloudflare unexpectedly — solve and retry once.
                clearance = await _ensure_clearance(url)
                cookies = clearance["cookies"]
                req_headers["User-Agent"] = clearance["ua"]
                needs_cloudflare = True
                continue
            r.raise_for_status()
            return r.content
        except (httpx.HTTPError, httpx.TransportError) as exc:
            last_exc = exc
            await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"Request failed for {url}: {last_exc}")
