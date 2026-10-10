"""Primary issuance and escrowed secondary trading in reserve-bank bonds."""
from datetime import timedelta
from math import isfinite
from sqlalchemy import func, select
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_bonds import (
    NatNextGameBondSeries, NatNextGameBondHolding, NatNextGameBondListing,
)
from backend.natbirzha.services.next_game_market_service import NextGameMarketService
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_bond_accounting import (
    utcnow, required_liability, settle_holding, forfeit_company_holdings,
    money,
)


def units_value(value):
    try:
        amount = int(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Число облигаций должно быть целым") from exc
    if amount != value or not 1 <= amount <= 10000:
        raise ValueError("Укажите от 1 до 10 000 облигаций")
    return amount


class NextGameBondService:
    @staticmethod
    async def initialize(session):
        for series_id, days, rate in ((1, 7, .001), (2, 14, .002), (3, 30, .003)):
            if await session.get(NatNextGameBondSeries, series_id) is None:
                session.add(NatNextGameBondSeries(id=series_id,
                    name=f"Резервный банк · {days} дней", face_price=100, daily_rate=rate, term_days=days))
        await session.flush()

    @classmethod
    async def settle_all(cls, session, *, now=None):
        await NextGameMarketService.lock_orderbook(session)
        await cls.initialize(session)
        treasury = await NextGameService._treasury(session)
        rows = (await session.execute(select(NatNextGameBondHolding, NatNextGameBondSeries,
            NatNextGameCompany).join(NatNextGameBondSeries,
            NatNextGameBondSeries.id == NatNextGameBondHolding.series_id).join(NatNextGameCompany,
            NatNextGameCompany.id == NatNextGameBondHolding.company_id)
            .where(NatNextGameBondHolding.status == "ACTIVE"))).all()
        for holding, series, company in rows:
            await settle_holding(session, holding, series, company, treasury, now=now)

    @classmethod
    async def buy(cls, session, owner, series_id, units, *, now=None):
        amount = units_value(units)
        await cls.settle_all(session, now=now)
        company = await NextGameService._owned_company(session, owner)
        series = await session.get(NatNextGameBondSeries, series_id)
        if series is None:
            raise ValueError("Серия облигаций не найдена")
        treasury = await NextGameService._treasury(session)
        total = round(amount * series.face_price, 8)
        coupon_liability = round(total * series.daily_rate * series.term_days, 8)
        if company.cash + 1e-8 < total:
            raise ValueError("Недостаточно cash для покупки облигаций")
        # Primary payment covers principal; existing reserve funds future coupon.
        if await NextGameService._available_treasury_cash(session, treasury) + 1e-8 < coupon_liability:
            raise ValueError("В резервном банке недостаточно средств для обеспечения купонов")
        current = now or utcnow()
        company.cash = round(company.cash - total, 8)
        treasury.cash = round(treasury.cash + total, 8)
        holding = NatNextGameBondHolding(company_id=company.id, series_id=series.id,
            units=amount, acquired_at=current, last_coupon_at=current,
            accrual_started_at=current, accrual_paid=0, coupon_paid=0,
            coupon_remaining=money(coupon_liability),
            matures_at=current + timedelta(days=series.term_days), status="ACTIVE")
        session.add(holding)
        session.add(NextGameService._ledger(company.id, "BOND_BUY", -total, total,
            metadata={"series_id": series_id, "units": amount}))
        await session.flush()
        return {"success": True, "holding_id": holding.id, "cash_paid": total}

    @classmethod
    async def list(cls, session, owner, holding_id, units, unit_price, *, now=None):
        amount = units_value(units)
        try:
            price = float(unit_price)
        except (ValueError, TypeError) as exc:
            raise ValueError("Цена должна быть числом") from exc
        if not isfinite(price) or price <= 0 or round(price, 4) != price:
            raise ValueError("Цена должна быть положительной, максимум 4 знака после запятой")
        if not isfinite(price * amount):
            raise ValueError("Сумма заявки слишком велика")
        await cls.settle_all(session, now=now)
        company = await NextGameService._owned_company(session, owner)
        holding = await session.get(NatNextGameBondHolding, holding_id)
        if holding is None or holding.company_id != company.id or holding.status != "ACTIVE":
            raise ValueError("Активный пакет облигаций не найден")
        reserved = await session.scalar(select(func.coalesce(func.sum(NatNextGameBondListing.units), 0)).where(
            NatNextGameBondListing.holding_id == holding.id, NatNextGameBondListing.status == "OPEN"))
        if amount > holding.units - reserved:
            raise ValueError("Недостаточно свободных облигаций")
        listing = NatNextGameBondListing(holding_id=holding.id, seller_company_id=company.id,
            units=amount, unit_price=price, status="OPEN", created_at=now or utcnow())
        session.add(listing)
        await session.flush()
        return {"success": True, "listing_id": listing.id}

    @classmethod
    async def buy_listing(cls, session, owner, listing_id, units, *, now=None):
        amount = units_value(units)
        await cls.settle_all(session, now=now)
        company = await NextGameService._owned_company(session, owner)
        listing = await session.get(NatNextGameBondListing, listing_id)
        if listing is None or listing.status != "OPEN" or amount > listing.units:
            raise ValueError("Открытое предложение не найдено или количество недоступно")
        seller = await session.get(NatNextGameCompany, listing.seller_company_id)
        if seller.owner_tg_id == company.owner_tg_id:
            raise ValueError("Нельзя купить собственные облигации")
        holding = await session.get(NatNextGameBondHolding, listing.holding_id)
        if holding.status != "ACTIVE" or holding.units < amount:
            raise ValueError("Пакет облигаций недоступен")
        total = round(amount * listing.unit_price, 8)
        if company.cash + 1e-8 < total:
            raise ValueError("Недостаточно cash для покупки")
        current = now or utcnow()
        series = await session.get(NatNextGameBondSeries, holding.series_id)
        treasury = await NextGameService._treasury(session)
        # Pay every accrued second to previous owner before title transfer.
        await settle_holding(session, holding, series, seller, treasury, now=current, force=True)
        buyer_coupon_budget = money(holding.coupon_remaining * amount / holding.units)
        holding.coupon_remaining = money(holding.coupon_remaining - buyer_coupon_budget)
        company.cash = round(company.cash - total, 8)
        seller.cash = round(seller.cash + total, 8)
        holding.units -= amount
        holding.accrual_started_at = current
        holding.accrual_paid = 0
        holding.last_coupon_at = current
        if holding.units == 0:
            holding.status = "TRANSFERRED"
        listing.units -= amount
        if listing.units == 0:
            listing.status = "FILLED"
        buyer_holding = NatNextGameBondHolding(company_id=company.id, series_id=series.id,
            units=amount, acquired_at=current, last_coupon_at=current,
            accrual_started_at=current, accrual_paid=0, coupon_paid=0,
            coupon_remaining=buyer_coupon_budget,
            matures_at=holding.matures_at, status="ACTIVE")
        session.add(buyer_holding)
        # Secondary cash stays between companies; reserve has no sale proceeds.
        await session.flush()
        # All principal and remaining coupon stay reserved after ownership transfer.
        liability = await required_liability(session) + await NextGameService._deposit_liability(session)
        if treasury.cash + 1e-8 < liability:
            raise ValueError("Резервному банку не хватает обеспечения купонов после разделения пакета")
        return {"success": True, "holding_id": buyer_holding.id, "cash_paid": total}

    @classmethod
    async def cancel_listing(cls, session, owner, listing_id, *, now=None):
        await cls.settle_all(session, now=now)
        company = await NextGameService._owned_company(session, owner)
        listing = await session.get(NatNextGameBondListing, listing_id)
        if listing is None or listing.seller_company_id != company.id or listing.status != "OPEN":
            raise ValueError("Открытое предложение не найдено")
        listing.status = "CANCELLED"
        await session.flush()
        return {"success": True, "released_units": listing.units}

    required_liability = staticmethod(required_liability)
    forfeit_company_holdings = staticmethod(forfeit_company_holdings)


__all__ = ["NextGameBondService"]
