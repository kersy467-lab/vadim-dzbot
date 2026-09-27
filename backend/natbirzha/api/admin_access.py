"""Server-side dynamic access gate for the game API."""

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.db.models import User
from backend.natbirzha.services.access_control import is_game_admin
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user
from backend.natbirzha.services.maintenance_service import MaintenanceService


async def require_game_access(
    user: User = Depends(get_strict_natbirzha_user),
    session: AsyncSession = Depends(get_db_session),
    *,
    default_closed: bool | None = None,
) -> User:
    if (
        await MaintenanceService.is_maintenance_active(session, default=default_closed)
        and not is_game_admin(user)
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "GAME_ACCESS_CLOSED",
                "message": "Игра временно закрыта на технический перерыв.",
            },
        )
    return user


# Backwards compatibility for modules that imported the old static guard.
require_game_admin = require_game_access

__all__ = ["require_game_access", "require_game_admin"]
