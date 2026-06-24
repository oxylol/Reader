"""Adapter registry — adapters self-register; core looks them up by key."""
from __future__ import annotations

from .base import SourceAdapter

_REGISTRY: dict[str, SourceAdapter] = {}


def register(adapter: SourceAdapter) -> None:
    _REGISTRY[adapter.key] = adapter


def get_adapter(key: str) -> SourceAdapter:
    if key not in _REGISTRY:
        raise KeyError(f"Unknown source adapter: {key}")
    return _REGISTRY[key]


def list_adapters() -> list[SourceAdapter]:
    return list(_REGISTRY.values())


def _bootstrap() -> None:
    # Register built-in adapters. New sources only need to be imported here.
    # comick is the source. The original comick shut down; the live data is
    # served by clone hosts, so the API host is configurable via COMICK_API_URL.
    from .comick import ComickAdapter

    register(ComickAdapter())


_bootstrap()
