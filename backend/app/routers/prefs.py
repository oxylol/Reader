"""Per-user reader preferences and per-series mode override."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_user
from ..db import get_session
from ..models import ReadingMode, SeriesModeOverride, User, UserPrefs
from ..schemas import ModeOverrideUpdate, PrefsOut, PrefsUpdate

router = APIRouter(prefix="/api/prefs", tags=["prefs"])


async def _get_or_create(session: AsyncSession, user_id: int) -> UserPrefs:
    prefs = (
        await session.execute(select(UserPrefs).where(UserPrefs.user_id == user_id))
    ).scalar_one_or_none()
    if prefs is None:
        prefs = UserPrefs(user_id=user_id)
        session.add(prefs)
        await session.commit()
        await session.refresh(prefs)
    return prefs


@router.get("", response_model=PrefsOut)
async def get_prefs(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    p = await _get_or_create(session, user.id)
    return PrefsOut(
        reading_mode=p.reading_mode.value,
        rtl=p.rtl,
        fit=p.fit,
        theme=p.theme,
        double_page=p.double_page,
    )


@router.put("", response_model=PrefsOut)
async def update_prefs(
    body: PrefsUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    p = await _get_or_create(session, user.id)
    if body.reading_mode is not None:
        p.reading_mode = ReadingMode(body.reading_mode)
    if body.rtl is not None:
        p.rtl = body.rtl
    if body.fit is not None:
        p.fit = body.fit
    if body.theme is not None:
        p.theme = body.theme
    if body.double_page is not None:
        p.double_page = body.double_page
    await session.commit()
    await session.refresh(p)
    return PrefsOut(
        reading_mode=p.reading_mode.value,
        rtl=p.rtl,
        fit=p.fit,
        theme=p.theme,
        double_page=p.double_page,
    )


@router.get("/series/{series_id}")
async def get_override(
    series_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    o = (
        await session.execute(
            select(SeriesModeOverride).where(
                SeriesModeOverride.user_id == user.id,
                SeriesModeOverride.series_id == series_id,
            )
        )
    ).scalar_one_or_none()
    if not o:
        return {"reading_mode": "auto", "rtl": None}
    return {"reading_mode": o.reading_mode.value, "rtl": o.rtl}


@router.put("/series/{series_id}")
async def set_override(
    series_id: int,
    body: ModeOverrideUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    o = (
        await session.execute(
            select(SeriesModeOverride).where(
                SeriesModeOverride.user_id == user.id,
                SeriesModeOverride.series_id == series_id,
            )
        )
    ).scalar_one_or_none()
    if o is None:
        o = SeriesModeOverride(user_id=user.id, series_id=series_id)
        session.add(o)
    o.reading_mode = body.reading_mode
    o.rtl = body.rtl
    await session.commit()
    return {"reading_mode": o.reading_mode.value, "rtl": o.rtl}
