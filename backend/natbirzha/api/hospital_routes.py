"""Authenticated hospital and repair-depot endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.hospital_service import HospitalService
from backend.natbirzha.services.idempotency_service import IdempotencyService


router = APIRouter(prefix="/military/hospital", tags=["Natbirzha Military Hospital"])


class TreatmentRequest(BaseModel):
    unit_type: str
    count: int = Field(gt=0, le=100_000)
    instant: bool = False


class CollectRequest(BaseModel):
    unit_type: Optional[str] = None


@router.get("/status")
async def hospital_status(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    response = await HospitalService.get_status(session, company.id)
    await session.commit()
    return response


@router.post("/treat")
async def start_treatment(
    request: TreatmentRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    endpoint = "/api/natbirzha/military/hospital/treat"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        response = await HospitalService.start_treatment(
            session, company.id, request.unit_type, request.count, instant=request.instant
        )
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload, response
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/treat-all")
async def start_all_treatments(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    endpoint = "/api/natbirzha/military/hospital/treat-all"
    payload = {}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    response = await HospitalService.start_all_treatments(session, company.id)
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, response
    )


@router.post("/collect")
async def collect_treated(
    request: CollectRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    endpoint = "/api/natbirzha/military/hospital/collect"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        collected = await HospitalService.collect_treated(
            session, company.id, unit_type=request.unit_type
        )
        response = {"success": True, "collected": collected}
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload, response
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


__all__ = ["router"]