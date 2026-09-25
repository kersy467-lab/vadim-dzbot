"""FastAPI routes for economic sabotages and state crisis controls."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.db.models import User
from backend.natbirzha.catalogs.sabotages import SABOTAGES_CATALOG
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user
from backend.natbirzha.api.creator_routes import get_current_creator
from backend.natbirzha.services.sabotage_service import SabotageService

router = APIRouter(tags=["Natbirzha Sabotages & Crises"])


class LaunchSabotageRequest(BaseModel):
    sabotage_id: str = Field(min_length=2, max_length=50)


class StopSabotageRequest(BaseModel):
    sabotage_id: Optional[str] = Field(default=None, max_length=50)
    reason: Optional[str] = Field(default="CREATOR_ABORT", max_length=100)


@router.get("/sabotages/catalog")
async def get_sabotages_catalog(
    _user: User = Depends(get_strict_natbirzha_user),
) -> List[Dict[str, Any]]:
    """Return the full crises catalog with metadata and multipliers."""
    return list(SABOTAGES_CATALOG.values())


@router.get("/sabotages/active")
async def get_active_sabotage_status(
    _user: User = Depends(get_strict_natbirzha_user),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Return currently active crises (up to 2), if any, with remaining time."""
    actives = await SabotageService.get_active_sabotages(session)
    if not actives:
        return {"active": False, "count": 0, "sabotage": None, "sabotages": []}
    summary = SabotageService.get_active_summary()
    return {
        "active": True,
        "count": len(actives),
        "sabotage": summary,
        "sabotages": summary.get("sabotages", []) if summary else [],
    }


@router.post("/creator/sabotages/launch")
async def launch_sabotage(
    req: LaunchSabotageRequest,
    creator: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Launch a selected crisis event. Requires creator privileges."""
    try:
        from backend.main import bot
    except Exception:
        bot = None

    try:
        result = await SabotageService.start_sabotage(
            session,
            sabotage_id=req.sabotage_id,
            actor_id=creator.tg_id,
            bot=bot,
        )
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка запуска саботажа: {exc}") from exc


@router.post("/creator/sabotages/stop")
async def stop_sabotage(
    req: StopSabotageRequest,
    creator: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> Dict[str, Any]:
    """Abort an active crisis early. Requires creator privileges."""
    try:
        from backend.main import bot
    except Exception:
        bot = None

    try:
        result = await SabotageService.stop_sabotage(
            session,
            actor_id=creator.tg_id,
            sabotage_id=req.sabotage_id,
            reason=req.reason or "CREATOR_ABORT",
            bot=bot,
        )
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка завершения саботажа: {exc}") from exc


__all__ = ["router"]
