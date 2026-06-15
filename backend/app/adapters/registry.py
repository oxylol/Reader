"""Adapter registry — adapters self-register; core looks them up by key."""
from __future__ import annotations

from ..config import settings
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
    # MangaDex is the default source (stable public API). comick is kept
    # registered as an option but its public API is currently locked down.
    from .mangadex import MangaDexAdapter

    register(MangaDexAdapter())

    if settings.enable_comick:
        from .comick import ComickAdapter

        register(ComickAdapter())


_bootstrap()
