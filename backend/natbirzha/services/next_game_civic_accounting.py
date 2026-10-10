"""Cash operating profits and daily assessment; no financing flows are taxable."""
from datetime import timedelta
from sqlalchemy import func, select
from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameLedger, NatNextGameMarketTrade
from backend.natbirzha.models.next_game_civic import (
    NatNextGameTaxAccount, NatNextGameTaxAssessment, NatNextGameCityOrder, NatNextGameEconomicEvent,
)
from backend.natbirzha.services.next_game_service.common import _utcnow


def cutoff(now):
    value = now.replace(hour=6, minute=0, second=0, microsecond=0)
    return value if value <= now else value - timedelta(days=1)


async def required_liability(session):
    return float(await session.scalar(select(func.coalesce(func.sum(
        NatNextGameCityOrder.remaining_quantity * NatNextGameCityOrder.unit_price), 0)).where(
        NatNextGameCityOrder.status == "OPEN")) or 0)


async def event_multiplier(session, company, now=None):
    now = now or _utcnow()
    active = await session.scalar(select(NatNextGameEconomicEvent.id).where(
        NatNextGameEconomicEvent.sector_id == company.sector_id,
        NatNextGameEconomicEvent.starts_at <= now, NatNextGameEconomicEvent.ends_at > now).limit(1))
    return 1.25 if active else 1.0


async def operating_profit(session, company_id, start, end):
    value = float(await session.scalar(select(func.coalesce(func.sum(NatNextGameLedger.cash_company_delta), 0)).where(
        NatNextGameLedger.company_id == company_id,
        NatNextGameLedger.action.in_(("BUY", "SELL", "OPERATING_COST", "JOINT_OPERATING", "CITY_SALE")),
        NatNextGameLedger.created_at >= start, NatNextGameLedger.created_at < end)) or 0)
    for field, sign in ((NatNextGameMarketTrade.seller_company_id, 1), (NatNextGameMarketTrade.buyer_company_id, -1)):
        value += sign * float(await session.scalar(select(func.coalesce(func.sum(
            NatNextGameMarketTrade.price * NatNextGameMarketTrade.quantity), 0)).where(
            field == company_id, NatNextGameMarketTrade.executed_at >= start,
            NatNextGameMarketTrade.executed_at < end)) or 0)
    # Supply prepayments are escrow. Only executed delivery cash is an operating flow.
    from backend.natbirzha.models.next_game_community import NatNextGameTransfer
    for field, sign in ((NatNextGameTransfer.recipient_company_id, 1), (NatNextGameTransfer.sender_company_id, -1)):
        value += sign * float(await session.scalar(select(func.coalesce(func.sum(NatNextGameTransfer.cash), 0)).where(
            field == company_id, NatNextGameTransfer.reason == "SUPPLY_PAYMENT",
            NatNextGameTransfer.created_at >= start, NatNextGameTransfer.created_at < end)) or 0)
    return round(value, 2)


async def assess_company(session, company, now=None, *, include_open=False):
    now = now or _utcnow()
    account = await session.get(NatNextGameTaxAccount, company.id, with_for_update=True)
    if account is None:
        account = NatNextGameTaxAccount(company_id=company.id, epoch_at=company.created_at,
            assessed_until=company.created_at, loss_carry=0)
        session.add(account)
        await session.flush()
    finish = now if include_open else cutoff(now)
    while account.assessed_until < finish:
        start = account.assessed_until
        end = min(cutoff(start) + timedelta(days=1), finish)
        profit = await operating_profit(session, company.id, start, end)
        taxable = max(0, profit - account.loss_carry)
        account.loss_carry = round(max(0, account.loss_carry - profit), 2)
        amount = round(taxable * .13, 2)
        session.add(NatNextGameTaxAssessment(company_id=company.id, period_start=start, period_end=end,
            operating_profit=profit, taxable_profit=taxable, amount=amount,
            status="DUE" if amount else "PAID"))
        account.assessed_until = end
        await session.flush()
    return account


async def retire_company(session, company_id):
    """Settle final partial day before rebirth and move the accounting epoch."""
    from backend.natbirzha.services.next_game_civic_service import NextGameCivicService
    await NextGameCivicService.lock(session)
    company = await session.get(NatNextGameCompany, company_id, with_for_update=True)
    now = _utcnow()
    account = await assess_company(session, company, now, include_open=True)
    due = list((await session.scalars(select(NatNextGameTaxAssessment).where(
        NatNextGameTaxAssessment.company_id == company_id, NatNextGameTaxAssessment.status == "DUE"
    ).order_by(NatNextGameTaxAssessment.id).with_for_update())).all())
    if sum(row.amount for row in due) > company.cash + 1e-9:
        raise ValueError("Перед перерождением погасите налоговую задолженность")
    for row in due:
        await NextGameCivicService.pay_tax(session, company.owner_tg_id, row.id, now=now)
    account.epoch_at = account.assessed_until = now
    account.loss_carry = 0
    await session.flush()
