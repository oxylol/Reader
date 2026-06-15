"""Shared logic for upserting series and building API responses."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters import get_adapter
from ..adapters.base import SeriesResult
from ..models import (
    Chapter,
    LibraryEntry,
    ReadingProgress,
    ReadingMode,
    Series,
    SeriesStatus,
    SeriesType,
)
from ..schemas import ChapterOut, SeriesOut


def _enum(enum_cls, value, default):
    try:
        return enum_cls(value)
    except ValueError:
        return default


async def upsert_series(session: AsyncSession, result: SeriesResult) -> Series:
    """Insert or update a series from an adapter result; returns the row."""
    existing = (
        await session.execute(
            select(Series).where(
                Series.source == result.source, Series.source_id == result.source_id
            )
        )
    ).scalar_one_or_none()

    fields = dict(
        slug=result.slug,
        title=result.title,
        alt_titles="\n".join(result.alt_titles),
        description=result.description,
        cover_url=result.cover_url,
        type=_enum(SeriesType, result.type, SeriesType.unknown),
        status=_enum(SeriesStatus, result.status, SeriesStatus.unknown),
        original_language=result.original_language,
        year=result.year,
        content_rating=result.content_rating,
        tags=",".join(result.tags),
    )
    if existing is None:
        existing = Series(source=result.source, source_id=result.source_id, **fields)
        # auto-pick reader default by type
        existing.default_mode = (
            ReadingMode.webtoon
            if existing.type in (SeriesType.manhwa, SeriesType.manhua)
            else ReadingMode.paged
        )
        session.add(existing)
    else:
        for k, v in fields.items():
            setattr(existing, k, v)
    await session.commit()
    await session.refresh(existing)
    return existing


async def ensure_series_from_source(
    session: AsyncSession, source: str, source_id: str
) -> Series:
    adapter = get_adapter(source)
    result = await adapter.get_series(source_id)
    return await upsert_series(session, result)


async def build_series_out(
    session: AsyncSession, series: Series, user_id: int
) -> SeriesOut:
    chapter_count = (
        await session.execute(
            select(func.count(Chapter.id)).where(Chapter.series_id == series.id)
        )
    ).scalar_one()
    downloaded_count = (
        await session.execute(
            select(func.count(Chapter.id)).where(
                Chapter.series_id == series.id, Chapter.downloaded == True  # noqa: E712
            )
        )
    ).scalar_one()
    read_count = (
        await session.execute(
            select(func.count(ReadingProgress.id)).where(
                ReadingProgress.series_id == series.id,
                ReadingProgress.user_id == user_id,
                ReadingProgress.completed == True,  # noqa: E712
            )
        )
    ).scalar_one()
    in_library = (
        await session.execute(
            select(LibraryEntry.id).where(
                LibraryEntry.user_id == user_id, LibraryEntry.series_id == series.id
            )
        )
    ).scalar_one_or_none() is not None

    return SeriesOut(
        id=series.id,
        source=series.source,
        source_id=series.source_id,
        slug=series.slug,
        title=series.title,
        cover_url=series.cover_url,
        type=series.type.value,
        status=series.status.value,
        description=series.description,
        tags=[t for t in series.tags.split(",") if t],
        year=series.year,
        content_rating=series.content_rating,
        default_mode=series.default_mode.value,
        in_library=in_library,
        chapter_count=chapter_count,
        downloaded_count=downloaded_count,
        unread_count=max(0, chapter_count - read_count),
    )


async def build_chapter_out(
    session: AsyncSession, chapter: Chapter, user_id: int
) -> ChapterOut:
    progress = (
        await session.execute(
            select(ReadingProgress).where(
                ReadingProgress.user_id == user_id,
                ReadingProgress.chapter_id == chapter.id,
            )
        )
    ).scalar_one_or_none()
    return ChapterOut(
        id=chapter.id,
        number=chapter.number,
        number_label=chapter.number_label,
        volume=chapter.volume,
        title=chapter.title,
        language=chapter.language,
        scanlation_group=chapter.scanlation_group,
        page_count=chapter.page_count,
        downloaded=chapter.downloaded,
        size_bytes=chapter.size_bytes,
        read=progress.completed if progress else False,
        current_page=progress.page if progress else 0,
    )
