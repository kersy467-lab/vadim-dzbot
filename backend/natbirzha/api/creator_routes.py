from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.db.models import User
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user
from backend.natbirzha.services.access_control import is_creator_user, get_creator_tg_ids
from backend.natbirzha.services.creator_service import CreatorService
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.leaderboard_service import LeaderboardService
from backend.natbirzha.services.season_reset_service import SeasonResetService
from backend.natbirzha.services.world_reset_service import WorldResetService
from backend.natbirzha.config import nat_settings

router = APIRouter(prefix="/creator", tags=["Natbirzha Creator & State"])

def is_creator_or_admin(user: User) -> bool:
    return bool(is_creator_user(user) or user.tg_id in get_creator_tg_ids() or user.role == "admin")


async def get_current_creator(
    user: User = Depends(get_strict_natbirzha_user)
) -> User:
    if not is_creator_or_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Доступ запрещён: требуются полномочия Создателя или Администратора государства."
        )
    return user

class WarningRequest(BaseModel):
    company_id: int
    reason: str = Field(min_length=3)

class RestrictionRequest(BaseModel):
    company_id: Optional[int] = None
    item_id: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    reason: str = Field(min_length=3)
    duration_minutes: Optional[int] = None

class IssueBondRequest(BaseModel):
    title: str = Field(min_length=3)
    volume: int = Field(gt=0)
    face_value: float = Field(gt=0)
    coupon_rate: float = Field(ge=0)
    maturity_days: int = Field(gt=0)
    coupon_interval_days: Optional[int] = Field(default=None, gt=0)
    purpose: str = Field(min_length=3)


class LaunchTournamentRequest(BaseModel):
    reward_first_pvc: int = Field(default=150, ge=0, le=10_000)
    reward_second_pvc: int = Field(default=100, ge=0, le=10_000)
    reward_third_pvc: int = Field(default=70, ge=0, le=10_000)


class SeasonResetRequest(BaseModel):
    operation_id: str = Field(min_length=1, max_length=120)
    backup_reference: str = Field(min_length=1, max_length=255)


class WorldResetRequest(BaseModel):
    confirmation: str = Field(min_length=1, max_length=64)

class SelfGrantRequest(BaseModel):
    cash: float = Field(default=0.0, ge=0, le=10_000_000)
    pvc: int = Field(default=0, ge=0, le=10_000)

@router.post("/me/grant")
async def grant_to_self(
    req: SelfGrantRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = "/api/natbirzha/creator/me/grant"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, admin.id, endpoint, idempotency_key, payload)
    if cached:
        return cached[1]
    from backend.natbirzha.services.creator_grant_service import CreatorGrantService
    try:
        response = await CreatorGrantService.grant_to_self(session, admin, cash=req.cash, pvc=req.pvc)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, admin.id, endpoint, idempotency_key, payload, response
    )


@router.post("/me/reset")
async def reset_self(
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete only the creator's own company. User record and admin role are preserved.
    Next company creation uses the normal cash balance plus the creator's PVC grant."""
    from backend.natbirzha.services.company_service import CompanyService

    comp_res = await session.execute(
        select(NatCompany).where(NatCompany.user_id == admin.id)
    )
    company = comp_res.scalar_one_or_none()
    if not company:
        return {"ok": True, "message": "Компании нет — уже чисто.", "deleted_company": None}

    company_name = company.name
    company_id = company.id
    try:
        await CompanyService.reset_company_for_user(session, admin.id, commit=True)
    except Exception as exc:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка сброса: {exc}") from exc

    starting_cash_text = f"{nat_settings.STARTING_CASH:,.0f}".replace(",", " ")
    return {
        "ok": True,
        "message": f"Компания «{company_name}» удалена. При новом создании стартовый баланс: {starting_cash_text} cash + 200 PVC.",
        "deleted_company": company_name,
        "deleted_company_id": company_id,
    }


@router.get("/overview")
async def get_overview(
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    return await CreatorService.get_overview(session)

@router.get("/economy/metrics")
async def get_economy_metrics(
    days: int = Query(default=7, ge=1, le=90),
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService
    return await EconomyMetricsService.summary(session, days=days)


@router.get("/market")
async def get_market(
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    return await CreatorService.get_market_snapshot(session)

@router.post("/market/warnings")
async def send_warning(
    req: WarningRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, "/api/natbirzha/creator/market/warnings", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    try:
        res = await CreatorService.add_warning(
            session, admin.tg_id, req.company_id, req.reason, commit=False
        )
        return await IdempotencyService.commit_response(
            session, admin.id, "/api/natbirzha/creator/market/warnings",
            idempotency_key, req.model_dump(), res
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/market/restrictions")
async def set_restriction(
    req: RestrictionRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, "/api/natbirzha/creator/market/restrictions", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    try:
        res = await CreatorService.set_restriction(
            session, admin.tg_id, req.company_id, req.item_id,
            req.min_price, req.max_price, req.reason, req.duration_minutes, commit=False
        )
        return await IdempotencyService.commit_response(
            session, admin.id, "/api/natbirzha/creator/market/restrictions",
            idempotency_key, req.model_dump(), res
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/market/restrictions/{restriction_id}")
async def remove_restriction(
    restriction_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    endpoint = f"/api/natbirzha/creator/market/restrictions/{restriction_id}"
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, endpoint, idempotency_key, {}
    )
    if cached:
        return cached[1]
    try:
        res = await CreatorService.remove_restriction(
            session, admin.tg_id, restriction_id, commit=False
        )
        return await IdempotencyService.commit_response(
            session, admin.id, endpoint, idempotency_key, {}, res
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/bonds/issue")
async def issue_bonds(
    req: IssueBondRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, "/api/natbirzha/creator/bonds/issue", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    try:
        res = await CreatorService.issue_bonds(
            session, admin.tg_id, req.title, req.volume,
            req.face_value, req.coupon_rate, req.maturity_days, req.purpose,
            coupon_interval_days=req.coupon_interval_days, commit=False
        )
        return await IdempotencyService.commit_response(
            session, admin.id, "/api/natbirzha/creator/bonds/issue",
            idempotency_key, req.model_dump(), res
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/bonds")
async def get_bonds(
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    return {"bonds": await CreatorService.get_bonds(session)}

@router.post("/bonds/{bond_id}/bankrupt")
async def declare_bond_bankruptcy(
    bond_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = f"/api/natbirzha/creator/bonds/{bond_id}/bankrupt"
    payload = {"bond_id": bond_id}
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, endpoint, idempotency_key, payload,
    )
    if cached:
        return cached[1]
    try:
        result = await CreatorService.declare_bond_bankruptcy(
            session, actor_id=admin.tg_id, bond_id=bond_id, commit=False,
        )
        return await IdempotencyService.commit_response(
            session, admin.id, endpoint, idempotency_key, payload, result,
        )
    except ValueError as error:
        status_code = 404 if "not found" in str(error).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(error)) from error

@router.post("/tournaments/launch")
async def launch_tournament(
    req: LaunchTournamentRequest = Body(default=LaunchTournamentRequest()),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, "/api/natbirzha/creator/tournaments/launch", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    res = await CreatorService.launch_early_tournament(
        session,
        admin.tg_id,
        (req.reward_first_pvc, req.reward_second_pvc, req.reward_third_pvc),
        commit=False,
    )
    return await IdempotencyService.commit_response(
        session, admin.id, "/api/natbirzha/creator/tournaments/launch",
        idempotency_key, req.model_dump(), res
    )

@router.get("/audit-log")
async def get_audit_log(
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    return {"logs": await CreatorService.get_audit_log(session, limit=limit)}


@router.get("/premium/ledger")
async def get_premium_ledger(
    limit: int = Query(100, ge=1, le=200),
    company_id: Optional[int] = Query(default=None, gt=0),
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    return {
        "currency": "PVC",
        "entries": await CreatorService.get_premium_ledger(
            session, limit=limit, company_id=company_id
        ),
    }


@router.get("/players")
async def get_players(
    search: str = Query(default="", max_length=80),
    sort: str = Query(default="last_activity_at"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=50),
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await LeaderboardService.get_players(
            session, query=search, sort=sort, page=page, page_size=page_size
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/season-reset/preview")
async def season_reset_preview(
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    return await SeasonResetService.preview(session)


@router.post("/season-reset")
async def season_reset(
    req: SeasonResetRequest,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    if not nat_settings.SEASON_RESET_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Season reset is disabled. Create a verified backup and set NATBIRZHA_SEASON_RESET_ENABLED=true for one operation.",
        )
    try:
        return await SeasonResetService.execute(
            session,
            operation_id=req.operation_id,
            actor_tg_id=admin.tg_id,
            backup_reference=req.backup_reference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/world-reset/preview")
async def world_reset_preview(
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    return await WorldResetService.preview(session)


@router.post("/world-reset")
async def world_reset(
    req: WorldResetRequest,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await WorldResetService.execute(
            session, actor_tg_id=admin.tg_id, confirmation=req.confirmation
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
