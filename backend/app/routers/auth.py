"""Authentication and account endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.deps import get_current_admin, get_current_user
from ..core.security import create_access_token, hash_password, verify_password
from ..db import get_session
from ..models import User
from ..schemas import Token, UserCreate, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    user = (
        await session.execute(select(User).where(User.username == form.username))
    ).scalar_one_or_none()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad credentials"
        )
    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, username=user.username, is_admin=user.is_admin)


@router.get("/users", response_model=list[UserOut])
async def list_users(
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    users = (await session.execute(select(User))).scalars().all()
    return [UserOut(id=u.id, username=u.username, is_admin=u.is_admin) for u in users]


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    _: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    exists = (
        await session.execute(select(User).where(User.username == body.username))
    ).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="Username taken")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        is_admin=body.is_admin,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return UserOut(id=user.id, username=user.username, is_admin=user.is_admin)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    user = await session.get(User, user_id)
    if user:
        await session.delete(user)
        await session.commit()


async def ensure_bootstrap_admin(session: AsyncSession, username: str, password: str) -> None:
    count = (await session.execute(select(func.count(User.id)))).scalar_one()
    if count == 0:
        session.add(
            User(username=username, password_hash=hash_password(password), is_admin=True)
        )
        await session.commit()
