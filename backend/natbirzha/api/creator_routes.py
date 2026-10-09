from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.db.models import User
from backend.natbirzha.services.creator_service import CreatorService
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.leaderboard_service import LeaderboardService
from backend.natbirzha.config import nat_settings
from backend.natbirzha.api.creator_auth import is_creator_or_admin, get_current_creator
from backend.natbirzha.api.creator_reset_routes import (
    router as creator_reset_router,
    SeasonResetRequest,
    WorldResetRequest,
    reset_self,
    season_reset_preview,
    season_reset,
    world_reset_preview,
    world_reset,
)
from backend.natbirzha.api.creator_economy_routes import router as creator_economy_router

router = APIRouter(prefix="/creator", tags=["Natbirzha Creator & State"])
router.include_router(creator_reset_router)
router.include_router(creator_economy_router)


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


class PlayerGrantRequest(BaseModel):
    cash: float = Field(default=0.0, ge=0, le=10_000_000)
    pvc: int = Field(default=0, ge=0, le=10_000)
    reason: str = Field(default="", max_length=255)


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


@router.post("/players/{company_id}/grant")
async def grant_to_player(
    company_id: int,
    req: PlayerGrantRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    """Выдать cash/PVC компании любого игрока от имени государства."""
    endpoint = f"/api/natbirzha/creator/players/{company_id}/grant"
    payload = {**req.model_dump(), "company_id": company_id}
    cached = await IdempotencyService.check_or_conflict(session, admin.id, endpoint, idempotency_key, payload)
    if cached:
        return cached[1]
    from backend.natbirzha.services.creator_grant_service import CreatorGrantService
    try:
        response = await CreatorGrantService.grant_to_player(
            session, admin,
            target_company_id=company_id,
            cash=req.cash,
            pvc=req.pvc,
            reason=req.reason,
        )
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, admin.id, endpoint, idempotency_key, payload, response
    )


@router.get("/overview")
async def get_overview(
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    return await CreatorService.get_overview(session)


@router.get("/economy/metrics")
async def get_economy_metrics(
    days: int = Query(7, ge=1, le=30),
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
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
    endpoint = "/api/natbirzha/creator/market/warnings"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, admin.id, endpoint, idempotency_key, payload)
    if cached:
        return cached[1]
    try:
        res = await CreatorService.add_warning(
            session, admin.tg_id, req.company_id, req.reason, commit=False
        )
        return await IdempotencyService.commit_response(session, admin.id, endpoint, idempotency_key, payload, res)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/market/restrictions")
async def add_restriction(
    req: RestrictionRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    endpoint = "/api/natbirzha/creator/market/restrictions"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, admin.id, endpoint, idempotency_key, payload)
    if cached:
        return cached[1]
    try:
        res = await CreatorService.set_restriction(
            session, admin.tg_id, req.company_id, req.item_id,
            req.min_price, req.max_price, req.reason, req.duration_minutes,
            commit=False,
        )
        return await IdempotencyService.commit_response(session, admin.id, endpoint, idempotency_key, payload, res)
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
    payload = {"restriction_id": restriction_id}
    cached = await IdempotencyService.check_or_conflict(session, admin.id, endpoint, idempotency_key, payload)
    if cached:
        return cached[1]
    try:
        res = await CreatorService.remove_restriction(
            session, admin.tg_id, restriction_id, commit=False
        )
        return await IdempotencyService.commit_response(session, admin.id, endpoint, idempotency_key, payload, res)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/bonds/issue")
async def issue_bond(
    req: IssueBondRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    endpoint = "/api/natbirzha/creator/bonds/issue"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, admin.id, endpoint, idempotency_key, payload)
    if cached:
        return cached[1]
    try:
        res = await CreatorService.issue_bonds(
            session, admin.tg_id, req.title, req.volume, req.face_value,
            req.coupon_rate, req.maturity_days, req.purpose,
            coupon_interval_days=req.coupon_interval_days,
            commit=False,
        )
        return await IdempotencyService.commit_response(session, admin.id, endpoint, idempotency_key, payload, res)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/bonds")
async def list_bonds(
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    return {"bonds": await CreatorService.get_bonds(session)}


@router.post("/bonds/{bond_id}/bankrupt")
async def declare_bond_bankrupt(
    bond_id: int,
    payload: dict = Body(default={}),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = f"/api/natbirzha/creator/bonds/{bond_id}/bankrupt"
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    from backend.natbirzha.services.creator_bond_bankruptcy_service import (
        CreatorBondBankruptcyService,
    )
    try:
        res = await CreatorBondBankruptcyService.declare_bankrupt(
            session, bond_id=bond_id, actor_tg_id=admin.tg_id
        )
        return await IdempotencyService.commit_response(
            session, admin.id, endpoint, idempotency_key, payload, res
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/tournaments/launch")
async def launch_tournament(
    req: LaunchTournamentRequest = Body(default_factory=LaunchTournamentRequest),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    """Launch a 7-day server tournament with configurable prize distribution."""
    endpoint = "/api/natbirzha/creator/tournaments/launch"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]

    from backend.natbirzha.services.tournament_service import TournamentService
    try:
        t = await TournamentService.launch_creator_tournament(
            session,
            creator_user_id=admin.id,
            reward_first=req.reward_first_pvc,
            reward_second=req.reward_second_pvc,
            reward_third=req.reward_third_pvc,
        )
        resp = {
            "success": True,
            "tournament_id": t.id,
            "status": t.status,
            "starts_at": t.starts_at.isoformat(),
            "ends_at": t.ends_at.isoformat(),
            "rewards": [req.reward_first_pvc, req.reward_second_pvc, req.reward_third_pvc],
        }
        return await IdempotencyService.commit_response(
            session, admin.id, endpoint, idempotency_key, payload, resp
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/audit-log")
async def get_audit_log(
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session)
):
    return {"logs": await CreatorService.get_audit_log(session, limit=limit)}


@router.get("/premium/ledger")
async def get_premium_ledger(
    limit: int = Query(50, ge=1, le=200),
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    return {"entries": await CreatorService.get_premium_ledger(session, limit=limit)}


@router.get("/players")
async def list_players(
    search: Optional[str] = Query(None),
    sort: str = Query("created_at"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await LeaderboardService.get_players(
            session, query=search, sort=sort, page=page, page_size=page_size
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


__all__ = [
    "router",
    "is_creator_or_admin",
    "get_current_creator",
    "WarningRequest",
    "RestrictionRequest",
    "IssueBondRequest",
    "LaunchTournamentRequest",
    "SeasonResetRequest",
    "WorldResetRequest",
    "PlayerGrantRequest",
    "SelfGrantRequest",
    "reset_self",
    "season_reset_preview",
    "season_reset",
    "world_reset_preview",
    "world_reset",
]
