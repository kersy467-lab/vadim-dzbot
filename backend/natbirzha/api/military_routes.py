from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select
from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.military import NatTournament
from backend.natbirzha.models.combat import NatBattle
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.military_service import MilitaryService
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.army_service import ArmyService
from backend.natbirzha.services.pve_service import PveService, PveWarError
from backend.natbirzha.services.tournament_service import TournamentError, TournamentService
from backend.natbirzha.config import game_dt_iso

router = APIRouter(prefix="/military", tags=["Natbirzha Military"])

class RecruitRequest(BaseModel):
    unit_type: str
    count: int = Field(gt=0)

class JoinAllianceRequest(BaseModel):
    alliance_id: int


@router.get("/pve-targets")
@router.get("/pve/targets")
async def get_pve_targets(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    return {"targets": await PveService.list_targets(session, company)}


@router.post("/pve-targets/{target_code}/scout")
@router.post("/pve/targets/{target_code}/scout")
async def scout_pve_target(
    target_code: str,
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        result = await PveService.scout_target(session, company, target_code)
        from backend.natbirzha.services.mastery_service import MasteryService
        intelligence = MasteryService.effect(company, "intelligence")
        strength_range = result.get("strength_range") or {}
        lower = strength_range.get("min")
        upper = strength_range.get("max")
        if intelligence > 0 and lower is not None and upper is not None and upper > lower:
            midpoint = (float(lower) + float(upper)) / 2.0
            half_span = (float(upper) - float(lower)) / 2.0
            narrowed = half_span * (1.0 - intelligence)
            result["strength_range"] = {
                "min": max(0, round(midpoint - narrowed)),
                "max": max(0, round(midpoint + narrowed)),
            }
        result["mastery_intelligence_pct"] = round(intelligence * 100, 2)
        return result
    except PveWarError as exc:
        raise HTTPException(
            status_code=404 if exc.reason == "target_not_found" else 400,
            detail={"reason": exc.reason, "message": str(exc)},
        ) from exc


@router.post("/pve-targets/{target_code}/attack")
@router.post("/pve/targets/{target_code}/attack")
async def attack_pve_target(
    target_code: str,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "idempotency_key_required"})
    endpoint = f"/api/natbirzha/military/pve/targets/{target_code}/attack"
    payload = {"target_code": target_code}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        response = await PveService.attack_target(
            session,
            company,
            target_code,
            f"pve:{company.id}:{idempotency_key}",
        )
        from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService
        rewards = response.get("rewards") or {}
        cash_reward = float(rewards.get("cash") or 0.0)
        if cash_reward > 0:
            await EconomyMetricsService.record(
                session, company_id=company.id, flow="SOURCE", category="pve_reward",
                cash_amount=cash_reward, context={"target_code": target_code},
            )
        casualties = sum(int(value or 0) for value in (response.get("attacker_losses") or {}).values())
        if casualties > 0:
            await EconomyMetricsService.record(
                session, company_id=company.id, flow="CONSUMPTION", category="pve_casualties",
                item_id="army_units", quantity=casualties, context={"target_code": target_code},
            )
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload, response
        )
    except PveWarError as exc:
        await session.rollback()
        status_code = 409 if exc.reason in {"already_conquered", "operation_conflict"} else 400
        raise HTTPException(
            status_code=status_code,
            detail={"reason": exc.reason, "message": str(exc)},
        ) from exc


@router.get("/battles")
async def get_battle_history(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    return {"battles": await PveService.battle_history(session, company.id)}


@router.get("/battles/{battle_id}")
async def get_battle_detail(
    battle_id: int,
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    battle = await session.scalar(
        select(NatBattle).where(
            NatBattle.id == battle_id,
            or_(
                NatBattle.attacker_company_id == company.id,
                NatBattle.defender_company_id == company.id,
            ),
        )
    )
    if battle is None:
        raise HTTPException(status_code=404, detail="Battle not found")
    return battle.summary_json

@router.get("/status")
async def get_military_status(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    status = await ArmyService.compatibility_status(session, company.id)
    status["pvc_balance"] = company.pvc_balance
    status["nat_balance"] = company.nat_balance  # temporary legacy response
    return status

@router.get("/tournaments/current")
@router.get("/tournament")
async def get_current_tournament(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    res = await session.execute(
        select(NatTournament).order_by(NatTournament.id.desc()).limit(1)
    )
    tourn = res.scalar_one_or_none()
    if not tourn:
        return {"tournament": None, "participants": []}
    participants = await TournamentService.leaderboard(session, tourn.id)
    return {
        "tournament": {
            "id": tourn.id,
            "cycle_number": tourn.cycle_number,
            "tournament_type": tourn.tournament_type,
            "status": tourn.status,
            "start_time": game_dt_iso(tourn.start_time),
            "snapshot_time": game_dt_iso(tourn.snapshot_time),
            "finish_time": game_dt_iso(tourn.finish_time),
            "rewards_pvc": [
                tourn.reward_first_pvc,
                tourn.reward_second_pvc,
                tourn.reward_third_pvc,
            ],
            "is_participant": any(row["company_id"] == company.id for row in participants),
        },
        "participants": participants[:50],
    }


@router.get("/tournaments/history")
async def get_tournament_history(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    return {"tournaments": await TournamentService.history(session, company.id)}


@router.get("/tournaments/{tournament_id}/targets")
async def get_tournament_targets(
    tournament_id: int,
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    from backend.natbirzha.config import get_game_now
    return {
        "targets": await TournamentService.pvp_targets(
            session, tournament_id, company.id, now=get_game_now()
        )
    }


@router.get("/tournaments/{tournament_id}/leaderboard")
async def get_tournament_leaderboard(
    tournament_id: int,
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    return {"leaderboard": await TournamentService.leaderboard(session, tournament_id)}


@router.post("/tournaments/{tournament_id}/targets/{target_company_id}/attack")
async def attack_tournament_player(
    tournament_id: int,
    target_company_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"reason": "idempotency_key_required"})
    endpoint = f"/api/natbirzha/military/tournaments/{tournament_id}/targets/{target_company_id}/attack"
    payload = {"tournament_id": tournament_id, "target_company_id": target_company_id}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    from backend.natbirzha.config import get_game_now
    try:
        response = await TournamentService.attack_player(
            session,
            tournament_id,
            company,
            target_company_id,
            f"pvp:{company.id}:{idempotency_key}",
            now=get_game_now(),
        )
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload, response
        )
    except TournamentError as exc:
        await session.rollback()
        status_code = 409 if exc.reason in {"cooldown", "operation_conflict"} else 400
        raise HTTPException(
            status_code=status_code,
            detail={"reason": exc.reason, "message": str(exc)},
        ) from exc

@router.post("/recruit")
async def recruit_units(
    req: RecruitRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, "/api/natbirzha/military/recruit", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    try:
        res = await MilitaryService.recruit_units(
            session, company, req.unit_type, req.count, commit=False
        )
        return await IdempotencyService.commit_response(
            session, company.user_id, "/api/natbirzha/military/recruit",
            idempotency_key, req.model_dump(), res
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/alliance/join")
async def join_alliance(
    req: JoinAllianceRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, "/api/natbirzha/military/alliance/join", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    try:
        res = await MilitaryService.join_alliance(session, req.alliance_id, company)
        await IdempotencyService.save_record(
            session, company.user_id, "/api/natbirzha/military/alliance/join", idempotency_key, req.model_dump(), 200, res
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.post("/tournament/{tournament_id}/resolve")
async def resolve_tournament(
    tournament_id: int,
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    try:
        return await MilitaryService.resolve_tournament(session, tournament_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
