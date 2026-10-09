"""Authenticated player controls for automatic early business upgrades."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.business_auto_upgrade_service import BusinessAutoUpgradeService
from backend.natbirzha.services.idempotency_service import IdempotencyService

router = APIRouter(prefix="/company", tags=["Natbirzha Automatic Upgrades"])


class AutoUpgradeRequest(BaseModel):
    enabled: bool


@router.put("/auto-upgrade")
async def set_auto_upgrade(
    request: AutoUpgradeRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    endpoint = "/api/natbirzha/company/auto-upgrade"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        result = await BusinessAutoUpgradeService.set_enabled(
            session, company.id, request.enabled
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, result
    )


__all__ = ["router"]
