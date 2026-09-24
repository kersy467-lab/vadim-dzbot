from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.db.session import get_db_session
from backend.db.models import User
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user, get_current_company
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.company_rename_service import CompanyRenameService
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.progression_service import progress_snapshot

router = APIRouter(prefix="/company", tags=["Natbirzha Company"])


@router.get("/industries")
async def industry_overview(session: AsyncSession = Depends(get_db_session)):
    """Population pressure shown before a player chooses a specialization."""
    from backend.natbirzha.services.industry_service import IndustryService
    return await IndustryService.overview(session)

class CreateCompanyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    specialization: str
    ticker: Optional[str] = None
    territory_hex: Optional[str] = None

class RespecRequest(BaseModel):
    new_specialization: str

class MasteryUnlockRequest(BaseModel):
    branch: str

class RenameCompanyRequest(BaseModel):
    name: str

@router.post("/create")
async def create_company(
    req: CreateCompanyRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: User = Depends(get_strict_natbirzha_user),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, user.id, "/api/natbirzha/company/create", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    # Pre-flight check: ensure company name is unique before attempting INSERT
    name_taken = await session.execute(
        select(NatCompany.id).where(NatCompany.name == req.name.strip()).limit(1)
    )
    if name_taken.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=400,
            detail=f"Название компании «{req.name.strip()}» уже занято. Выберите другое название."
        )

    try:
        company = await CompanyService.create_company(
            session, user.id, req.name, req.specialization, ticker=req.ticker, commit=False
        )
        resp = {
            "success": True,
            "company_id": company.id,
            "name": company.name,
            "ticker": company.ticker,
            "specialization": company.specialization,
            "cash": company.cash,
            "territory_tiles": company.territory_tiles
        }
        return await IdempotencyService.commit_response(
            session, user.id, "/api/natbirzha/company/create", idempotency_key, req.model_dump(), resp
        )
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Название компании «{req.name.strip()}» уже занято. Выберите другое название."
        )



@router.get("/me")
@router.get("/status")
async def get_company_status(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    nav = await CompanyService.calculate_audited_nav(session, company)
    from backend.natbirzha.models.inventory import NatInventory
    inv_res = await session.execute(select(NatInventory).where(NatInventory.company_id == company.id))
    inventory_rows = inv_res.scalars().all()
    inv = {row.item_id: row.quantity for row in inventory_rows}
    available_inventory = {
        row.item_id: round(float(row.available_quantity), 6) for row in inventory_rows
    }
    reserved_inventory = {
        row.item_id: round(min(max(0.0, float(row.quantity)), max(0.0, float(row.reserved_quantity))), 6)
        for row in inventory_rows
    }
    from backend.natbirzha.models.company import NatFactory
    fac_res = await session.execute(select(NatFactory).where(NatFactory.company_id == company.id))
    factory_rows = fac_res.scalars().all()
    from backend.natbirzha.services.building_catalog import get_building_spec
    from backend.natbirzha.services.building_service import BuildingService
    from backend.natbirzha.config import get_game_tz
    def _format_dt_iso(dt):
        if not dt:
            return None
        if getattr(dt, 'tzinfo', None) is None:
            dt = dt.replace(tzinfo=get_game_tz())
        return dt.isoformat()

    from backend.natbirzha.config import normalize_dt, get_game_now
    now = normalize_dt(get_game_now())
    factories = []
    for f in factory_rows:
        ready_at_norm = normalize_dt(f.cycle_ready_at)
        is_running = bool(f.cycle_ready_at)
        is_ready = bool(is_running and now >= ready_at_norm)
        rem_sec = 0
        if is_running and not is_ready:
            rem_sec = max(1, int((ready_at_norm - now).total_seconds()))
        b_spec = get_building_spec(f.building_type) or {}
        factories.append({
            "id": f.id,
            "name": b_spec.get("name") or f.building_type,
            "building_type": f.building_type,
            "specialization": f.specialization,
            "level": f.level,
            "tier": f.level,
            "factory_type": f.building_type,
            "is_active": f.is_active,
            "workers": f.workers,
            "automation_level": f.automation_level,
            "automation_enabled": f.automation_enabled,
            "automation_status": f.automation_status,
            "automation_pause_reason": f.automation_pause_reason,
            "automation_unlocked": bool(f.automation_level >= 1 and company.level >= 6),
            "technology_level": f.technology_level,
            "current_recipe": f.current_recipe,
            "default_recipe": b_spec.get("recipe_id"),
            "upgrade_options": BuildingService.describe_upgrades(f, company),
            "cycle_started_at": _format_dt_iso(f.cycle_started_at),
            "cycle_ready_at": _format_dt_iso(f.cycle_ready_at),
            "last_produced_at": _format_dt_iso(f.last_produced_at),
            "is_running": is_running,
            "is_ready": is_ready,
            "remaining_seconds": rem_sec
        })
    from backend.natbirzha.models.stocks import NatStock
    stock_res = await session.execute(
        select(NatStock).where(NatStock.company_id == company.id, NatStock.is_listed == True)
    )
    is_public = stock_res.scalar_one_or_none() is not None
    progression = progress_snapshot(company)
    from backend.natbirzha.services.mastery_service import MasteryService
    mastery = MasteryService.snapshot(company)
    from backend.natbirzha.services.capital_plan_service import capital_plan_for_company
    capital_plan = capital_plan_for_company(company, is_public=is_public)

    return {
        "id": company.id,
        "name": company.name,
        "ticker": getattr(company, "ticker", company.name[:5].upper()),
        "specialization": company.specialization,
        "level": progression["level"],
        "xp": progression["xp"],
        "current_level_xp": progression["current_level_xp"],
        "next_level_xp": progression["next_level_xp"],
        "xp_to_next": progression["xp_to_next"],
        "level_progress_pct": progression["level_progress_pct"],
        "is_max_level": progression["is_max_level"],
        "max_level": progression["max_level"],
        "era": progression["era"],
        "mastery": mastery,
        "cash": company.cash,
        "nat_balance": company.nat_balance,
        "territory_tiles": company.territory_tiles,
        "max_territory": company.max_territory,
        "factory_slots": BuildingService.slot_limits(company, len(factory_rows)),
        "factory_count": len(factory_rows),
        "audited_nav": nav,
        "nav": nav,
        "is_bankrupt": company.is_bankrupt,
        "is_public": is_public,
        "capital_plan": capital_plan,
        "inventory": inv,
        "inventory_total": inv,
        "inventory_available": available_inventory,
        "inventory_reserved": reserved_inventory,
        "factories": factories
    }


@router.post("/rename")
async def rename_company(
    req: RenameCompanyRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = "/api/natbirzha/company/rename"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]

    try:
        response = await CompanyRenameService.rename(session, company.id, req.name)
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload, response
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=400,
            detail="Это название уже занято другой компанией.",
        ) from exc


@router.post("/mastery/unlock")
async def unlock_mastery(
    req: MasteryUnlockRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = "/api/natbirzha/company/mastery/unlock"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    from backend.natbirzha.services.mastery_service import MasteryService
    try:
        response = await MasteryService.unlock(session, company, req.branch.strip().lower())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, response
    )


@router.post("/territory/expand")
async def expand_territory(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, "/api/natbirzha/company/territory/expand", idempotency_key, {}
    )
    if cached:
        return cached[1]

    locked = (await session.execute(
        select(NatCompany).where(NatCompany.id == company.id).with_for_update()
    )).scalar_one_or_none()
    company = locked or company
    if company.territory_tiles >= company.max_territory:
        raise HTTPException(status_code=400, detail="Достигнут максимальный размер территории.")

    # Cost scales with territory, while post-60 logistics gives capped diminishing relief.
    from backend.natbirzha.services.mastery_service import MasteryService
    base_cost = company.territory_tiles * 10000.0
    logistics_discount = MasteryService.effect(company, "logistics")
    cost = round(base_cost * (1.0 - logistics_discount), 2)
    if company.cash < cost:
        raise HTTPException(status_code=400, detail=f"Недостаточно cash: нужно {cost}, доступно {company.cash}")

    company.cash = round(company.cash - cost, 2)
    company.territory_tiles += 1
    from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService
    await EconomyMetricsService.record(
        session, company_id=company.id, flow="SINK", category="territory_expand", cash_amount=cost
    )
    resp = {"success": True, "new_tiles": company.territory_tiles, "cost_paid": cost, "remaining_cash": company.cash}
    return await IdempotencyService.commit_response(
        session, company.user_id, "/api/natbirzha/company/territory/expand", idempotency_key, {}, resp
    )


@router.post("/respec")
async def respec_specialization(
    req: RespecRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, "/api/natbirzha/company/respec", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    try:
        res = await CompanyService.change_specialization(session, company, req.new_specialization, commit=False)
        return await IdempotencyService.commit_response(
            session, company.user_id, "/api/natbirzha/company/respec", idempotency_key, req.model_dump(), res
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class BuyLicenseRequest(BaseModel):
    target_specialization: str

@router.post("/license/buy")
async def buy_foreign_license_route(
    req: BuyLicenseRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, "/api/natbirzha/company/license/buy", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    try:
        res = await CompanyService.buy_foreign_license(session, company, req.target_specialization, commit=False)
        return await IdempotencyService.commit_response(
            session, company.user_id, "/api/natbirzha/company/license/buy", idempotency_key, req.model_dump(), res
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reset")
async def reset_company_route(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: User = Depends(get_strict_natbirzha_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Completely reset the authenticated player's company and assets."""
    endpoint = "/api/natbirzha/company/reset"
    cached = await IdempotencyService.check_or_conflict(session, user.id, endpoint, idempotency_key, {})
    if cached:
        return cached[1]
    ok = await CompanyService.reset_company_for_user(session, user.id, commit=False)
    resp = {
        "success": True,
        "reset": ok,
        "message": "Компания полностью сброшена. Теперь можно выбрать новую отрасль."
    }
    return await IdempotencyService.commit_response(session, user.id, endpoint, idempotency_key, {}, resp)
