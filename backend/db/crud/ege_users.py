"""CRUD helpers for EGE Arena public profiles and classmate privilege."""
from __future__ import annotations

from typing import Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.ege.ranking import normalize_nickname, validate_nickname


async def get_user_by_ege_nickname(session: AsyncSession, nickname: str) -> Optional[User]:
    normalized = normalize_nickname(nickname)
    if not normalized:
        return None
    result = await session.execute(select(User).where(User.ege_nickname_normalized == normalized, User.role != "rejected"))
    return result.scalar_one_or_none()


async def set_ege_nickname(session: AsyncSession, user: User, nickname: str) -> tuple[bool, str]:
    valid, value = validate_nickname(nickname)
    if not valid:
        return False, value
    normalized = normalize_nickname(value)
    result = await session.execute(
        select(User).where(User.ege_nickname_normalized == normalized, User.id != user.id)
    )
    if result.scalar_one_or_none():
        return False, "Этот ник уже занят. Выберите другой."
    user.ege_nickname = value
    user.ege_nickname_normalized = normalized
    try:
        await session.commit()
    except IntegrityError:
        # The DB unique index is the final guard against two users choosing
        # the same nickname at the same moment.
        await session.rollback()
        return False, "Этот ник уже занят. Выберите другой."
    await session.refresh(user)
    return True, value


async def set_user_classmate(session: AsyncSession, tg_id: int, enabled: bool) -> Optional[User]:
    result = await session.execute(select(User).where(User.tg_id == int(tg_id)))
    user = result.scalar_one_or_none()
    if user:
        user.is_classmate = bool(enabled)
        await session.commit()
        await session.refresh(user)
    return user


async def get_ege_players(session: AsyncSession) -> list[User]:
    result = await session.execute(
        select(User).where(
            User.tg_id > 0,
            User.ege_nickname.is_not(None),
            User.ege_nickname_normalized.is_not(None),
            User.role != "rejected",
        ).order_by(User.ege_nickname_normalized.asc())
    )
    return list(result.scalars().all())


def has_full_access(user: User | None) -> bool:
    if not user:
        return False
    return bool(user.role == "admin" or user.role == "student" or getattr(user, "is_classmate", False))
