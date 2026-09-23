"""Feature-flagged HTTP API for the NATBIRZHA 2.0 idle business loop."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.catalogs.businesses import visible_business_specs
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.empire_summary_service import EmpireSummaryService
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.supply_policy_service import SupplyPolicyService
from backend.natbirzha.services.territory_service import TerritoryService


router = APIRouter(prefix="/businesses", tags=["Natbirzha Tycoon V2"])
company_router = APIRouter(prefix="/company", tags=["Natbirzha Tycoon V2"])


class OpenBusinessRequest(BaseModel):
    business_type: str = Field(min_length=2, max_length=64)
    custom_name: Optional[str] = Field(default=None, max_length=120)


class SupplyPolicyRequest(BaseModel):
    mode: str = Field(pattern="^(MANUAL|AUTO_NPC|AUTO_MARKET|AUTO_MARKET_NPC)$")
    min_hours_stock: float = Field(default=0, ge=0, le=168)
    target_hours_stock: float = Field(default=0, ge=0, le=168)
    max_unit_price: Optional[float] = Field(default=None, gt=0)
    allow_state_reserve: bool = False


class SaleModeRequest(BaseModel):
    mode: str = Field(pattern="^(NPC|HOLD)$")


def _require_tycoon_v2() -> None:
    if not nat_settings.TYCOON_V2_ENABLED:
        raise HTTPException(
            status_code=409,
            detail="НАТБИРЖА 2.0 пока отключена: сейчас используется старая экономика.",
        )


def _catalog_item(spec: dict) -> dict:
    return {
        "id": spec["id"],
        "name": spec["name"],
        "description": spec.get("description", ""),
        "icon": spec.get("icon", "🏢"),
        "tier": spec["tier"],
        "mechanic": spec["mechanic"],
        "specialization": spec["specialization"],
        "max_stage": spec["max_stage"],
        "slot_weight": spec["slot_weight"],
        "open_cost": spec["open_cost"],
        "base_income_per_hour": spec["base_income_per_hour"],
        "base_maintenance_per_hour": spec["base_maintenance_per_hour"],
        "inputs_per_hour": spec["inputs_per_hour"],
        "outputs_per_hour": spec["outputs_per_hour"],
        "milestones": spec["milestones"],
        "company_level_required": spec.get("company_level_required", 1),
        "prerequisites": spec.get("prerequisites", {}),
        "territory_required": spec.get("territory_required", 0),
        "open_resources": spec.get("open_resources", {}),
        "industry_order": spec.get("industry_order", 0),
        "starter": bool(spec.get("starter")),
        "unique": bool(spec.get("unique", True)),
        "tags": list(spec.get("tags", ())),
    }


async def _settle_before_mutation(session: AsyncSession, company: NatCompany) -> None:
    """Freeze all idle income/consumption before changing business state."""
    await IdleEconomyService.settle_company(session, company.id)


@router.get("/catalog")
async def business_catalog() -> dict:
    _require_tycoon_v2()
    return {"items": [_catalog_item(spec) for spec in visible_business_specs()]}


@router.get("")
async def business_list(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_tycoon_v2()
    settlement = await IdleEconomyService.settle_company(session, company.id)
    summary = await EmpireSummaryService.build(session, company.id)
    await session.commit()
    return {"settlement": settlement, "businesses": summary["businesses"], "slots": summary["slots"]}


@company_router.get("/empire-summary")
async def empire_summary(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_tycoon_v2()
    settlement = await IdleEconomyService.settle_company(session, company.id)
    summary = await EmpireSummaryService.build(session, company.id)
    await session.commit()
    return {"settlement": settlement, **summary}


@company_router.get("/territory/quote")
async def territory_quote(company: NatCompany = Depends(get_current_company)) -> dict:
    _require_tycoon_v2()
    return TerritoryService.quote(company)


@company_router.post("/territory/expand")
async def expand_tycoon_territory(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_tycoon_v2()
    endpoint = "/api/natbirzha/company/territory/expand-v2"
    cached = await IdempotencyService.check_or_conflict(session, company.user_id, endpoint, idempotency_key, {})
    if cached:
        return cached[1]
    try:
        await _settle_before_mutation(session, company)
        response = await TerritoryService.expand(session, company.id)
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, {}, response
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/open")
async def open_business(
    request: OpenBusinessRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_tycoon_v2()
    endpoint = "/api/natbirzha/businesses/open"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        response = await BusinessService.open_business(
            session, company.id, request.business_type, custom_name=request.custom_name
        )
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload, response
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{business_id}/upgrade")
async def upgrade_business(
    business_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_tycoon_v2()
    endpoint = f"/api/natbirzha/businesses/{business_id}/upgrade"
    payload = {"business_id": business_id}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        response = await BusinessService.start_upgrade(session, company.id, business_id)
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload, response
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{business_id}/supply/{item_id}")
async def configure_supply_policy(
    business_id: int,
    item_id: str,
    request: SupplyPolicyRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_tycoon_v2()
    endpoint = f"/api/natbirzha/businesses/{business_id}/supply/{item_id}"
    payload = {"business_id": business_id, "item_id": item_id, **request.model_dump()}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    from sqlalchemy import select
    from backend.natbirzha.models.business import NatBusiness
    try:
        await _settle_before_mutation(session, company)
        business = await session.scalar(
            select(NatBusiness).where(NatBusiness.id == business_id, NatBusiness.company_id == company.id)
        )
        if business is None:
            raise ValueError("Предприятие не найдено")
        policy = await SupplyPolicyService.configure(session, business_id, item_id, **request.model_dump())
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload,
            {"success": True, "business_id": business_id, "policy": policy},
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{business_id}/sale-mode")
async def configure_sale_mode(
    business_id: int,
    request: SaleModeRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_tycoon_v2()
    endpoint = f"/api/natbirzha/businesses/{business_id}/sale-mode"
    payload = {"business_id": business_id, **request.model_dump()}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        await _settle_before_mutation(session, company)
        response = await BusinessService.configure_sale_mode(
            session, company.id, business_id, request.mode
        )
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload, response
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def _business_lifecycle_mutation(
    action: str,
    business_id: int,
    idempotency_key: Optional[str],
    company: NatCompany,
    session: AsyncSession,
) -> dict:
    endpoint = f"/api/natbirzha/businesses/{business_id}/{action}"
    payload = {"business_id": business_id, "action": action}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        operation = getattr(BusinessService, action)
        response = await operation(session, company.id, business_id)
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload, response
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{business_id}/pause")
async def pause_business(
    business_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_tycoon_v2()
    return await _business_lifecycle_mutation("pause", business_id, idempotency_key, company, session)


@router.post("/{business_id}/resume")
async def resume_business(
    business_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_tycoon_v2()
    return await _business_lifecycle_mutation("resume", business_id, idempotency_key, company, session)


@router.post("/{business_id}/sell")
async def sell_business(
    business_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_tycoon_v2()
    return await _business_lifecycle_mutation("sell", business_id, idempotency_key, company, session)


__all__ = ["router", "company_router"]
