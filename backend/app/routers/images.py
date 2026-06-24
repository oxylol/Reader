"""Image proxy for remote covers.

Browsers load cover <img> tags directly from the source CDN, which is
hotlink-protected (needs a Referer). This endpoint fetches the remote image
server-side with the right Referer and streams it back same-origin. It is
unauthenticated (covers aren't sensitive) but restricted to an allowlist of
image hosts to avoid being an open proxy.
"""
from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Query, Response

from ..config import settings
from ..services import http

router = APIRouter(prefix="/api/img", tags=["images"])


def _allowed(host: str) -> bool:
    h = host.lower()
    return h.endswith(".pictures") or "comick" in h or "mangadex" in h


@router.get("")
async def proxy(url: str = Query(..., description="remote image URL")):
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc or not _allowed(p.netloc):
        raise HTTPException(status_code=400, detail="URL not allowed")
    client = http.get_client()
    try:
        r = await client.get(
            url,
            headers={
                "User-Agent": http.DEFAULT_UA,
                "Referer": settings.comick_site_url + "/",
                "Accept": "image/avif,image/webp,image/*,*/*",
            },
        )
        r.raise_for_status()
    except Exception:
        raise HTTPException(status_code=502, detail="upstream image fetch failed")
    return Response(
        content=r.content,
        media_type=r.headers.get("content-type", "image/jpeg"),
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )
