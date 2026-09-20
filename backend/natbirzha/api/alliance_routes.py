from typing import Optional, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.alliances import NatAlliance
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.military_service import MilitaryService
from backend.natbirzha.services.idempotency_service import IdempotencyService

router = APIRouter(prefix="/alliance", tags=["Natbirzha Alliances"])

class CreateAllianceRequest(BaseModel):
    name: str = Field(min_length=3, max_length=64)

class JoinAllianceRequest(BaseModel):
    alliance_id: int

@router.get("/my")
async def get_my_alliance(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    alliance_data = await MilitaryService.get_company_alliance(session, company.id)
    return {"in_alliance": alliance_data is not None, "alliance": alliance_data}

@router.get("/list")
async def list_alliances(
    session: AsyncSession = Depends(get_db_session)
):
    res = await session.execute(
        select(NatAlliance).order_by(NatAlliance.total_army_strength.desc(), NatAlliance.member_count.desc()).limit(50)
    )
    alliances = [
        {
            "id": a.id,
            "name": a.name,
            "leader_company_id": a.leader_company_id,
            "member_count": a.member_count,
            "max_members": a.max_members,
            "total_army_strength": a.total_army_strength
        }
        for a in res.scalars().all()
    ]
    return {"alliances": alliances}

@router.post("/create")
async def create_alliance_route(
    req: CreateAllianceRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, "/api/natbirzha/alliance/create", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    try:
        res = await MilitaryService.create_alliance(session, company, req.name)
        await IdempotencyService.save_record(
            session, company.user_id, "/api/natbirzha/alliance/create", idempotency_key, req.model_dump(), 200, res
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/join")
async def join_alliance_route(
    req: JoinAllianceRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, "/api/natbirzha/alliance/join", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    try:
        res = await MilitaryService.join_alliance(session, req.alliance_id, company)
        await IdempotencyService.save_record(
            session, company.user_id, "/api/natbirzha/alliance/join", idempotency_key, req.model_dump(), 200, res
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.post("/leave")
async def leave_alliance_route(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, "/api/natbirzha/alliance/leave", idempotency_key, {}
    )
    if cached:
        return cached[1]

    try:
        res = await MilitaryService.leave_alliance(session, company)
        await IdempotencyService.save_record(
            session, company.user_id, "/api/natbirzha/alliance/leave", idempotency_key, {}, 200, res
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
