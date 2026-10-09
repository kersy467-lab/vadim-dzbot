from typing import Literal, Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.rebirth_service import RebirthService

router = APIRouter(prefix='/company/rebirth', tags=['Natbirzha Rebirth'])


class RebirthRequest(BaseModel):
    expected_count: int = Field(ge=0, le=10)
    confirmed: Literal[True]


class RebirthAnnouncementRequest(BaseModel):
    expected_count: int = Field(ge=0, le=10)


@router.get('')
async def rebirth_status(company: NatCompany = Depends(get_current_company), session: AsyncSession = Depends(get_db_session)):
    return await RebirthService.snapshot(session, company)


@router.post('/announce')
async def rebirth_announce(
    req: RebirthAnnouncementRequest,
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await RebirthService.announce(session, company.id, expected_count=req.expected_count)
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post('')
async def rebirth(req: RebirthRequest, idempotency_key: Optional[str] = Header(None, alias='Idempotency-Key'), company: NatCompany = Depends(get_current_company), session: AsyncSession = Depends(get_db_session)):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail='Нужен ключ идемпотентности')
    endpoint = '/api/natbirzha/company/rebirth'
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, company.user_id, endpoint, idempotency_key, payload)
    if cached:
        return cached[1]
    try:
        response = await RebirthService.perform(session, company.id, expected_count=req.expected_count)
        return await IdempotencyService.commit_response(session, company.user_id, endpoint, idempotency_key, payload, response)
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
