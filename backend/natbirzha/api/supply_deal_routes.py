"""Authenticated API for company-to-company time-limited supply deals."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.db.models import User
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.player_deals import NatSupplyDeal
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.supply_deal_service import SupplyDealService


router = APIRouter(prefix="/market/deals", tags=["Natbirzha Supply Deals"])


class CreateSupplyDealRequest(BaseModel):
    supplier_company_id: int = Field(gt=0)
    item_id: str = Field(min_length=1, max_length=50)
    quantity_per_hour: float = Field(gt=0, le=SupplyDealService.MAX_QUANTITY_PER_HOUR)
    discount_pct: float = Field(ge=0, le=SupplyDealService.MAX_DISCOUNT_PCT)
    term_seconds: int
    reward_type: str = Field(pattern="^(PROFIT_SHARE|FIXED_CASH)$")
    profit_share_pct: Optional[float] = Field(default=None, gt=0, le=SupplyDealService.MAX_PROFIT_SHARE_PCT)
    fixed_cash: Optional[float] = Field(default=None, gt=0, le=1_000_000_000_000)


def _http_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status = 409 if any(token in message.lower() for token in ("уже обработано", "уже обработ", "превышать 50%")) else 400
    return HTTPException(status_code=status, detail=message)


async def _mutate(
    session: AsyncSession,
    company: NatCompany,
    endpoint: str,
    key: str | None,
    payload: dict,
    operation,
) -> dict:
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, key, payload
    )
    if cached:
        return cached[1]
    try:
        deal = await operation()
    except ValueError as exc:
        raise _http_error(exc) from exc
    await session.flush()
    response = await SupplyDealService.serialize(session, deal, company.id)
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, key, payload, response
    )


@router.get("/companies")
async def list_companies(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return {"companies": await SupplyDealService.available_companies(
        session, company.id, current_user_id=company.user_id,
    )}


@router.get("/companies/{target_company_id}/resources")
async def company_resources(
    target_company_id: int,
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    target_row = (await session.execute(select(NatCompany, User).join(
        User, User.id == NatCompany.user_id
    ).where(
        NatCompany.id == target_company_id,
        NatCompany.is_bankrupt.is_(False),
        NatCompany.id != company.id,
        NatCompany.user_id != company.user_id,
    ))).first()
    if target_row is None:
        raise HTTPException(status_code=404, detail="Компания не найдена")
    target, user = target_row
    resources = await SupplyDealService.produced_resources(session, target.id)
    for resource in resources:
        resource["reference_price"] = await SupplyDealService.current_reference_price(
            session, resource["item_id"], exclude_company_id=company.id
        )
    return {
        "company_id": target.id,
        "company_name": target.name,
        "player_name": user.display_name,
        "specialization": target.specialization,
        "level": target.level,
        "resources": resources,
    }


@router.post("")
async def create_offer(
    req: CreateSupplyDealRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = req.model_dump()
    return await _mutate(
        session, company, "/api/natbirzha/market/deals", idempotency_key, payload,
        lambda: SupplyDealService.create_offer(session, company, **payload),
    )


async def _list_deals(
    view: str,
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        if view == "active":
            buyer_ids = await SupplyDealService.buyers_to_settle(session, company.id)
            for buyer_id in buyer_ids:
                await IdleEconomyService.settle_company(session, buyer_id)
            await IdleEconomyService.settle_company(session, company.id)
        items = await SupplyDealService.list_deals(session, company.id, view)
    except ValueError as exc:
        raise _http_error(exc) from exc
    await session.commit()
    return {"items": items}


@router.get("/incoming")
async def incoming_deals(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _list_deals("incoming", company, session)


@router.get("/outgoing")
async def outgoing_deals(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _list_deals("outgoing", company, session)


@router.get("/active")
async def active_deals(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _list_deals("active", company, session)


@router.get("/history")
async def historic_deals(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return await _list_deals("history", company, session)


@router.get("/{deal_id}")
async def get_deal(
    deal_id: int,
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    row = await session.scalar(select(NatSupplyDeal).where(
        NatSupplyDeal.id == deal_id,
        (NatSupplyDeal.buyer_company_id == company.id) | (NatSupplyDeal.supplier_company_id == company.id),
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    if row.status == "ACTIVE":
        buyer_ids = [row.buyer_company_id] if row.buyer_company_id != company.id else [company.id]
        for buyer_id in buyer_ids:
            await IdleEconomyService.settle_company(session, buyer_id)
    try:
        details = await SupplyDealService.get_deal(session, company.id, deal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return details


@router.post("/{deal_id}/accept")
async def accept_offer(
    deal_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = {"deal_id": deal_id}
    return await _mutate(
        session, company, f"/api/natbirzha/market/deals/{deal_id}/accept", idempotency_key, payload,
        lambda: SupplyDealService.accept(session, company, deal_id),
    )


@router.post("/{deal_id}/reject")
async def reject_offer(
    deal_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = {"deal_id": deal_id}
    return await _mutate(
        session, company, f"/api/natbirzha/market/deals/{deal_id}/reject", idempotency_key, payload,
        lambda: SupplyDealService.reject(session, company, deal_id),
    )


@router.post("/{deal_id}/cancel")
async def cancel_offer(
    deal_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = {"deal_id": deal_id}
    return await _mutate(
        session, company, f"/api/natbirzha/market/deals/{deal_id}/cancel", idempotency_key, payload,
        lambda: SupplyDealService.cancel(session, company, deal_id),
    )
