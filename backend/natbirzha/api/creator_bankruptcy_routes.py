"""Creator-only controls for one-time asset liquidation of a company."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_routes import get_current_creator
from backend.natbirzha.services.forced_bankruptcy_service import ForcedBankruptcyService
from backend.natbirzha.services.idempotency_service import IdempotencyService


router = APIRouter(prefix="/creator/players", tags=["Natbirzha Creator Players"])


def _require_key(value: Optional[str]) -> str:
    if not value or not value.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required.")
    if len(value.strip()) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key is too long.")
    return value.strip()


@router.post("/{company_id}/bankruptcy")
async def liquidate_company_assets(
    company_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    creator: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    key = _require_key(idempotency_key)
    endpoint = f"/api/natbirzha/creator/players/{company_id}/bankruptcy"
    payload = {"company_id": company_id}
    cached = await IdempotencyService.check_or_conflict(
        session, creator.id, endpoint, key, payload
    )
    if cached:
        return cached[1]
    try:
        result = await ForcedBankruptcyService.execute(
            session,
            company_id=company_id,
            actor_id=creator.tg_id,
            operation_key=key,
            commit=False,
        )
        return await IdempotencyService.commit_response(
            session, creator.id, endpoint, key, payload, result
        )
    except ValueError as exc:
        status = 404 if "not found" in str(exc).lower() else 409
        raise HTTPException(status_code=status, detail=str(exc)) from exc


__all__ = ["router"]
