from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.building_service import BuildingService
from backend.natbirzha.services.idempotency_service import IdempotencyService

router = APIRouter(tags=["Natbirzha Buildings"])

class BuildRequest(BaseModel):
    building_type: Optional[str] = None
    factory_type: Optional[str] = None

class UpgradeRequest(BaseModel):
    upgrade_type: str

@router.get("/buildings/catalog")
async def get_buildings_catalog(
    company: Optional[NatCompany] = Depends(get_current_company)
):
    """Returns the full 48-enterprise catalog annotated with player availability and efficiency."""
    catalog = BuildingService.get_catalog_for_company(company)
    return {"catalog": catalog, "total": len(catalog)}

@router.get("/buildings/{factory_id}")
async def get_building_details(
    factory_id: int,
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    details = await BuildingService.get_building_details(session, company, factory_id)
    if not details:
        raise HTTPException(status_code=404, detail="Предприятие не найдено")
    return details

@router.post("/buildings/build")
async def build_enterprise(
    req: BuildRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    b_type = req.building_type or req.factory_type or ""
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, "/api/natbirzha/buildings/build", idempotency_key, {"building_type": b_type}
    )
    if cached:
        return cached[1]

    try:
        res = await BuildingService.build_factory(session, company, b_type, idempotency_key, commit=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return await IdempotencyService.commit_response(
        session, company.user_id, "/api/natbirzha/buildings/build", idempotency_key, {"building_type": b_type}, res
    )

@router.get("/factories/{factory_id}/upgrades")
async def get_factory_upgrades(
    factory_id: int,
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    details = await BuildingService.get_building_details(session, company, factory_id)
    if not details:
        raise HTTPException(status_code=404, detail="Предприятие не найдено")
    fac = await session.get(NatFactory, factory_id)
    return {
        "factory_id": factory_id,
        "level": fac.level,
        "workers": fac.workers,
        "automation_level": fac.automation_level,
        "technology_level": fac.technology_level,
        "upgrades": BuildingService.describe_upgrades(fac, company),
    }

@router.post("/factories/{factory_id}/upgrade")
async def upgrade_enterprise(
    factory_id: int,
    req: UpgradeRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    payload = {"factory_id": factory_id, "upgrade_type": req.upgrade_type}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, f"/api/natbirzha/factories/{factory_id}/upgrade", idempotency_key, payload
    )
    if cached:
        return cached[1]

    try:
        res = await BuildingService.upgrade_factory(session, company, factory_id, req.upgrade_type, commit=False)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return await IdempotencyService.commit_response(
        session, company.user_id, f"/api/natbirzha/factories/{factory_id}/upgrade", idempotency_key, payload, res
    )

__all__ = ["router"]
