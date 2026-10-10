"""Server-gated administrator routes for the next-game sandbox."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.api.creator_auth import get_current_creator
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_service import (
    MAX_TRADE_QUANTITY, MAX_BANK_LOAN, MAX_BANK_DEPOSIT, MAX_BANK_DEPOSIT_DAYS,
)
from backend.natbirzha.services.next_game_market_service import NextGameMarketService

router = APIRouter(prefix="/next-game", tags=["Natbirzha Next Game Preview"])


from backend.natbirzha.api.next_game_schemas import (
    CreateSandboxCompany, SelectSector, SelectBranch, BuildFacility, TradeItem,
    LimitOrderRequest, BankLoanRequest, BankDepositRequest,
)


def _require_idempotency_key(value: Optional[str]) -> str:
    if not value or not value.strip():
        raise HTTPException(status_code=400, detail="Нужен ключ идемпотентности")
    return value.strip()[:128]


@router.get("/map")
async def get_map(
    section: Literal["full", "overview", "map", "factories", "market", "bank", "capital", "contracts"] = Query(default="full"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        from sqlalchemy import select
        from backend.natbirzha.models.next_game import NatNextGameCompany
        from backend.natbirzha.services.next_game_bankruptcy_service import NextGameBankruptcyService
        from backend.natbirzha.next_game_catalog import get_next_game_catalog
        await NextGameMarketService.lock_orderbook(session)
        company = await session.scalar(select(NatNextGameCompany).where(
            NatNextGameCompany.owner_tg_id == int(admin.tg_id)))
        recovery = await NextGameBankruptcyService.status(session, company.id) if company else {
            "requires_ack": False, "was_triggered": False}
        if recovery["requires_ack"]:
            result = {"company": NextGameService.snapshot_company(company),
                "corporations": get_next_game_catalog(), "recovery": recovery}
        else:
            result = await NextGameService.snapshot(session, int(admin.tg_id), section=section)
            result["recovery"] = recovery
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise


@router.post("/company")
async def create_company(
    request: CreateSandboxCompany,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        result = await NextGameService.create_company(session, int(admin.tg_id), request.name)
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/sector")
async def select_sector(
    request: SelectSector,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        result = await NextGameService.select_sector(
            session, int(admin.tg_id), request.sector_id
        )
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/branch")
async def select_branch(
    request: SelectBranch,
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        result = await NextGameService.select_branch(
            session, int(admin.tg_id), request.branch_id
        )
        await session.commit()
        return result
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/facility/build")
async def build_facility(
    request: BuildFacility,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_idempotency_key(idempotency_key)
    endpoint = "/api/natbirzha/next-game/facility/build"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, endpoint, key, payload,
    )
    if cached:
        return cached[1]
    try:
        result = await NextGameService.build_facility(
            session, int(admin.tg_id), branch_id=request.branch_id,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, admin.id, endpoint, key, payload, result,
    )


@router.put("/branch/advance")
async def advance_branch(
    request: SelectBranch,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_idempotency_key(idempotency_key)
    endpoint = "/api/natbirzha/next-game/branch/advance"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, endpoint, key, payload,
    )
    if cached:
        return cached[1]
    try:
        result = await NextGameService.advance_branch(
            session, int(admin.tg_id), request.branch_id,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, admin.id, endpoint, key, payload, result,
    )


@router.post("/market/trade")
async def trade_market(
    request: TradeItem,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_idempotency_key(idempotency_key)
    endpoint = "/api/natbirzha/next-game/market/trade"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, endpoint, key, payload,
    )
    if cached:
        return cached[1]
    try:
        result = await NextGameService.trade(
            session, int(admin.tg_id), request.item_id, request.side, request.quantity,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, admin.id, endpoint, key, payload, result,
    )


@router.get("/market/orders")
async def get_market_orders(
    item_id: Optional[str] = Query(default=None, min_length=1, max_length=64),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        return await NextGameMarketService.list_market(session, item_id=item_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/market/orders/mine")
async def get_my_market_orders(
    item_id: Optional[str] = Query(default=None, min_length=1, max_length=64),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        orders = await NextGameMarketService.list_my_orders(
            session, int(admin.tg_id), item_id=item_id,
        )
        return {"orders": orders}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/market/orders")
async def create_market_order(
    request: LimitOrderRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_idempotency_key(idempotency_key)
    endpoint = "/api/natbirzha/next-game/market/orders"
    payload = request.model_dump()
    await NextGameMarketService.lock_orderbook(session)
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, endpoint, key, payload,
    )
    if cached:
        return cached[1]
    try:
        result = await NextGameMarketService.create_limit_order(
            session, int(admin.tg_id), request.item_id, request.side,
            request.quantity, request.limit_price,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, admin.id, endpoint, key, payload, result,
    )


@router.delete("/market/orders/{order_id}")
async def cancel_market_order(
    order_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_idempotency_key(idempotency_key)
    endpoint = "/api/natbirzha/next-game/market/orders/cancel"
    payload = {"order_id": int(order_id)}
    await NextGameMarketService.lock_orderbook(session)
    cached = await IdempotencyService.check_or_conflict(
        session, admin.id, endpoint, key, payload,
    )
    if cached:
        return cached[1]
    try:
        result = await NextGameMarketService.cancel_order(
            session, int(admin.tg_id), int(order_id),
        )
    except ValueError as exc:
        await session.rollback()
        status_code = 404 if "не найдена" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, admin.id, endpoint, key, payload, result,
    )


@router.post("/bank/loan")
async def request_bank_loan(
    request: BankLoanRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_idempotency_key(idempotency_key)
    endpoint = "/api/natbirzha/next-game/bank/loan"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, admin.id, endpoint, key, payload)
    if cached:
        return cached[1]
    try:
        result = await NextGameService.request_bank_loan(
            session, int(admin.tg_id), request.amount,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, admin.id, endpoint, key, payload, result,
    )


@router.post("/bank/loan/repay")
async def repay_bank_loan(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_idempotency_key(idempotency_key)
    endpoint = "/api/natbirzha/next-game/bank/loan/repay"
    payload: dict = {}
    cached = await IdempotencyService.check_or_conflict(session, admin.id, endpoint, key, payload)
    if cached:
        return cached[1]
    try:
        result = await NextGameService.repay_bank_loan(session, int(admin.tg_id))
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, admin.id, endpoint, key, payload, result,
    )


@router.post("/bank/deposits")
async def open_bank_deposit(
    request: BankDepositRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_idempotency_key(idempotency_key)
    endpoint = "/api/natbirzha/next-game/bank/deposits"
    payload = request.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, admin.id, endpoint, key, payload)
    if cached:
        return cached[1]
    try:
        result = await NextGameService.open_bank_deposit(
            session, int(admin.tg_id), request.amount, request.term_days,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, admin.id, endpoint, key, payload, result,
    )


@router.post("/bank/deposits/{deposit_id}/withdraw")
async def withdraw_bank_deposit(
    deposit_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    admin: User = Depends(get_current_creator),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_idempotency_key(idempotency_key)
    endpoint = "/api/natbirzha/next-game/bank/deposits/withdraw"
    payload = {"deposit_id": int(deposit_id)}
    cached = await IdempotencyService.check_or_conflict(session, admin.id, endpoint, key, payload)
    if cached:
        return cached[1]
    try:
        result = await NextGameService.withdraw_bank_deposit(
            session, int(admin.tg_id), int(deposit_id),
        )
    except ValueError as exc:
        await session.rollback()
        status_code = 404 if "не найден" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, admin.id, endpoint, key, payload, result,
    )


__all__ = ["router"]

from backend.natbirzha.api.next_game_facility_routes import router as facility_router

router.include_router(facility_router)
