"""Fleet, workforce and internal project endpoints for V2 enterprises."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.business_asset_catalog import EMPLOYEE_CATALOG, PROJECT_CATALOG, VEHICLE_CATALOG
from backend.natbirzha.services.business_asset_service import BusinessAssetService
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


router = APIRouter(prefix="/business-assets", tags=["Natbirzha Tycoon Assets"])


class VehicleRequest(BaseModel):
    business_id: int = Field(gt=0)
    vehicle_type: str = Field(min_length=2, max_length=64)


class EmployeeRequest(BaseModel):
    business_id: int = Field(gt=0)
    role: str = Field(min_length=2, max_length=64)


class ProjectRequest(BaseModel):
    business_id: int = Field(gt=0)
    project_type: str = Field(min_length=2, max_length=64)


@router.get("/catalog")
async def assets_catalog() -> dict:
    return {
        "vehicles": [{"id": key, **value} for key, value in VEHICLE_CATALOG.items()],
        "employees": [{"id": key, **value} for key, value in EMPLOYEE_CATALOG.items()],
        "projects": [{"id": key, **value} for key, value in PROJECT_CATALOG.items()],
    }


async def _mutate(
    *, endpoint: str, payload: dict, idempotency_key: Optional[str], company: NatCompany,
    session: AsyncSession, callback,
) -> dict:
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        await IdleEconomyService.settle_company(session, company.id)
        response = await callback()
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload, response
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/vehicles")
async def purchase_vehicle(
    request: VehicleRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = request.model_dump()
    return await _mutate(
        endpoint="/api/natbirzha/business-assets/vehicles", payload=payload,
        idempotency_key=idempotency_key, company=company, session=session,
        callback=lambda: BusinessAssetService.purchase_vehicle(
            session, company.id, request.business_id, request.vehicle_type
        ),
    )


@router.post("/vehicles/{vehicle_id}/repair")
async def repair_vehicle(
    vehicle_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = {"vehicle_id": vehicle_id}
    return await _mutate(
        endpoint=f"/api/natbirzha/business-assets/vehicles/{vehicle_id}/repair", payload=payload,
        idempotency_key=idempotency_key, company=company, session=session,
        callback=lambda: BusinessAssetService.repair_vehicle(session, company.id, vehicle_id),
    )


@router.post("/employees")
async def hire_employee(
    request: EmployeeRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = request.model_dump()
    return await _mutate(
        endpoint="/api/natbirzha/business-assets/employees", payload=payload,
        idempotency_key=idempotency_key, company=company, session=session,
        callback=lambda: BusinessAssetService.hire_employee(
            session, company.id, request.business_id, request.role
        ),
    )


@router.delete("/employees/{employee_id}")
async def fire_employee(
    employee_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = {"employee_id": employee_id}
    return await _mutate(
        endpoint=f"/api/natbirzha/business-assets/employees/{employee_id}", payload=payload,
        idempotency_key=idempotency_key, company=company, session=session,
        callback=lambda: BusinessAssetService.fire_employee(session, company.id, employee_id),
    )


@router.post("/projects")
async def start_project(
    request: ProjectRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = request.model_dump()
    return await _mutate(
        endpoint="/api/natbirzha/business-assets/projects", payload=payload,
        idempotency_key=idempotency_key, company=company, session=session,
        callback=lambda: BusinessAssetService.start_project(
            session, company.id, request.business_id, request.project_type
        ),
    )


__all__ = ["router"]
