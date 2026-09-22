"""War 2.0 infrastructure routes kept separate from battle/tournament routes."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.military_infrastructure_service import MilitaryInfrastructureService


router = APIRouter(prefix="/military/infrastructure", tags=["Natbirzha War 2.0"])


@router.get("")
async def infrastructure_status(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    result = await MilitaryInfrastructureService.status(session, company.id)
    await session.commit()
    return result


@router.post("/{facility}/upgrade")
async def upgrade_infrastructure(
    facility: str,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    endpoint = f"/api/natbirzha/military/infrastructure/{facility}/upgrade"
    payload = {"facility": facility}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        response = await MilitaryInfrastructureService.upgrade(session, company.id, facility)
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload, response
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = ["router"]
