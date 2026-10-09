from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.restructuring import NatRestructuring
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.bankruptcy_service import BankruptcyService
from backend.natbirzha.services.bankruptcy_recovery_service import (
    BankruptcyRecoveryService,
    RESTART_CASH_GRANT,
)
from backend.natbirzha.services.idempotency_service import IdempotencyService

router = APIRouter(prefix="/bankruptcy", tags=["Natbirzha Bankruptcy"])

@router.get("/status")
async def get_bankruptcy_status(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    res = await session.execute(
        select(NatRestructuring).where(
            NatRestructuring.company_id == company.id,
            NatRestructuring.status == "ACTIVE"
        )
    )
    restruct = res.scalar_one_or_none()
    if not restruct:
        return {
            "is_bankrupt": bool(company.is_bankrupt),
            "status": "BANKRUPT" if company.is_bankrupt else "solvent",
            "bankruptcy_kind": "liquidation" if company.is_bankrupt else None,
            "assets_liquidated": bool(company.is_bankrupt),
        }

    return {
        "is_bankrupt": True,
        "status": "RESTRUCTURING",
        "bankruptcy_kind": "restructuring",
        "assets_liquidated": False,
        "snapshot_nav": restruct.snapshot_nav,
        "liquidation_pool": restruct.liquidation_pool,
        "fee_start_date": str(restruct.fee_start_date),
        "fee_end_date": str(restruct.fee_end_date),
        "fee_rate": restruct.fee_rate,
        "status": restruct.status
    }

@router.post("/file")
async def file_bankruptcy(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, "/api/natbirzha/bankruptcy/file", idempotency_key, {}
    )
    if cached:
        return cached[1]

    try:
        r = await BankruptcyService.file_restructuring(session, company)
        resp = {
            "success": True,
            "snapshot_nav": r.snapshot_nav,
            "liquidation_pool": r.liquidation_pool,
            "fee_start_date": str(r.fee_start_date),
            "fee_end_date": str(r.fee_end_date)
        }
        await IdempotencyService.save_record(
            session, company.user_id, "/api/natbirzha/bankruptcy/file", idempotency_key, {}, 200, resp
        )
        return resp
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/restart")
async def restart_after_bankruptcy(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = "/api/natbirzha/bankruptcy/restart"
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, {}
    )
    if cached:
        return cached[1]

    try:
        restarted = await BankruptcyRecoveryService.restart_company(
            session, company, commit=False,
        )
        result = {
            "success": True,
            "cash_grant": RESTART_CASH_GRANT,
            "company": {
                "id": restarted.id,
                "company_id": restarted.id,
                "name": restarted.name,
                "ticker": restarted.ticker,
                "specialization": restarted.specialization,
                "level": int(restarted.level or 1),
                "xp": int(restarted.xp or 0),
                "cash": float(restarted.cash or 0.0),
                "is_bankrupt": False,
            },
        }
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, {}, result
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
