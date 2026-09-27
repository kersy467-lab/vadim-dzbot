"""Authentication dependency and helper for Creator / State Administrator routes."""

from fastapi import Depends, HTTPException
from backend.db.models import User
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user
from backend.natbirzha.services.access_control import is_creator_user, get_creator_tg_ids


def is_creator_or_admin(user: User) -> bool:
    return bool(is_creator_user(user) or user.tg_id in get_creator_tg_ids() or user.role == "admin")


async def get_current_creator(
    user: User = Depends(get_strict_natbirzha_user)
) -> User:
    if not is_creator_or_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Доступ запрещён: требуются полномочия Создателя или Администратора государства."
        )
    return user


__all__ = ["is_creator_or_admin", "get_current_creator"]
