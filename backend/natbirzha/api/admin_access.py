"""Server-side administrator gate for the temporary closed launch."""

from fastapi import Depends, HTTPException

from backend.db.models import User
from backend.natbirzha.services.access_control import is_game_admin
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user


async def require_game_admin(user: User = Depends(get_strict_natbirzha_user)) -> User:
    if not is_game_admin(user):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "GAME_ACCESS_CLOSED",
                "message": "Игра временно доступна только администраторам.",
            },
        )
    return user


__all__ = ["require_game_admin"]
