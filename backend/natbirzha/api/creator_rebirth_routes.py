"""Creator-only delayed rebirth controls for game administrators."""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.services.admin_rebirth_schedule_service import AdminRebirthScheduleService

router = APIRouter(tags=["Natbirzha Creator Rebirth"])


class ScheduleAdminRebirthRequest(BaseModel):
    telegram_ids: list[int] = Field(min_length=2, max_length=2)

    @field_validator("telegram_ids")
    @classmethod
    def require_distinct_ids(cls, value: list[int]) -> list[int]:
        if len(set(value)) != 2 or any(item <= 0 for item in value):
            raise ValueError("Укажите два разных положительных Telegram ID")
        return value


@router.post("/rebirth/schedule")
async def schedule_admin_rebirth(
    req: ScheduleAdminRebirthRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Нужен ключ идемпотентности")
    operation_key = f"{admin.tg_id}:{idempotency_key.strip()[:80]}"
    try:
        return await AdminRebirthScheduleService.schedule(
            session,
            req.telegram_ids,
            actor_tg_id=int(admin.tg_id),
            operation_key=operation_key,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        await session.rollback()
        raise HTTPException(status_code=502, detail=str(exc)) from exc


__all__ = ["router", "ScheduleAdminRebirthRequest", "schedule_admin_rebirth"]
