"""Application configuration loaded from environment / .env."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    secret_key: str = "dev-insecure-secret-change-me"
    access_token_expire_minutes: int = 43200  # 30 days
    algorithm: str = "HS256"

    # Bootstrap admin
    admin_username: str = "admin"
    admin_password: str = "changeme"

    # Database
    database_url: str = "sqlite+aiosqlite:////data/inkvault.db"

    # Storage
    library_dir: str = "/data/library"

    # Compression
    image_format: str = "webp"  # webp | avif
    image_quality: float = 0.8  # 0..1

    # Downloader
    max_parallel_downloads: int = 4
    source_rate_limit_seconds: float = 0.5

    # Cloudflare solver
    flaresolverr_url: str = "http://flaresolverr:8191/v1"

    # Auto-update
    auto_update_interval_minutes: int = 360

    # comick source. The original comick shut down; live data is served by
    # clone hosts (comick.art / comick.live) running a Laravel API at the site
    # origin under /api. comick.art serves it without Cloudflare; comick.live
    # fronts /api/search with Cloudflare (set COMICK_NEEDS_CLOUDFLARE=true).
    comick_api_url: str = "https://comick.art"
    comick_site_url: str = "https://comick.art"
    comick_needs_cloudflare: bool = False

    @property
    def library_path(self) -> Path:
        p = Path(self.library_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def quality_int(self) -> int:
        """Encoder quality 1..100 from the 0..1 setting."""
        return max(1, min(100, round(self.image_quality * 100)))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
