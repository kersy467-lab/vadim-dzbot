"""Reserve funded city orders, paid taxes and bounded sector events."""
from datetime import timedelta
from math import isfinite
from sqlalchemy import select
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_civic import NatNextGameCityOrder, NatNextGameEconomicEvent, NatNextGameTaxAssessment
from backend.natbirzha.next_game_catalog import get_next_game_items, find_next_game_sector
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_service.common import _utcnow
from backend.natbirzha.services.next_game_civic_accounting import assess_company, cutoff, required_liability


class NextGameCivicService:
    @staticmethod
    async def lock(session):
        from backend.natbirzha.services.next_game_market_service import NextGameMarketService
        await NextGameMarketService.lock_orderbook(session)

    @staticmethod
    async def tick(session, now=None):
        now = now or _utcnow()
        await NextGameCivicService.lock(session)
        for company in (await session.scalars(select(NatNextGameCompany).order_by(NatNextGameCompany.id))).all():
            await assess_company(session, company, now)
        await NextGameCivicService.rotate_orders(session, now)
        await session.flush()

    @staticmethod
    async def rotate_orders(session, now=None):
        now = now or _utcnow()
        await NextGameCivicService.lock(session)
        for row in (await session.scalars(select(NatNextGameCityOrder).where(
            NatNextGameCityOrder.status == "OPEN", NatNextGameCityOrder.expires_at <= now).with_for_update())).all():
            row.status = "EXPIRED"
        await session.flush()
        rotation = cutoff(now)
        if await session.scalar(select(NatNextGameCityOrder.id).where(NatNextGameCityOrder.rotation_at == rotation).limit(1)):
            return
        treasury = await NextGameService._treasury(session)
        budget = min(100_000.0, max(0, await NextGameService._available_treasury_cash(session, treasury)) * .01)
        items = sorted(get_next_game_items().items())
        offset = rotation.toordinal() % len(items)
        chosen = (items + items)[offset:offset + min(8, len(items))]
        for item_id, item in chosen:
            price = round(float(item["base_price"]) * 1.08, 2)
            quantity = min(1000, int(budget / max(1, len(chosen)) / price)) if price > 0 else 0
            if quantity <= 0:
                continue
            session.add(NatNextGameCityOrder(item_id=item_id, unit_price=price, quantity=quantity,
                remaining_quantity=quantity, rotation_at=rotation, expires_at=rotation + timedelta(days=1), status="OPEN"))
        await session.flush()

    @staticmethod
    async def pay_tax(session, owner_tg_id, tax_id, now=None):
        await NextGameCivicService.lock(session)
        company = await NextGameService._owned_company(session, owner_tg_id)
        row = await session.get(NatNextGameTaxAssessment, tax_id, with_for_update=True)
        if not row or row.company_id != company.id:
            raise ValueError("Начисление не принадлежит вашей компании")
        if row.status == "PAID":
            return {"success": True, "tax_id": row.id, "status": "PAID"}
        if row.status != "DUE":
            raise ValueError("Начисление закрыто и не подлежит оплате")
        if company.cash + 1e-9 < row.amount:
            raise ValueError("Недостаточно cash для уплаты налога")
        treasury = await NextGameService._treasury(session)
        company.cash = round(company.cash - row.amount, 8)
        treasury.cash = round(treasury.cash + row.amount, 8)
        row.status, row.paid_at = "PAID", now or _utcnow()
        session.add(NextGameService._ledger(company.id, "TAX_PAYMENT", -row.amount, row.amount,
            metadata={"assessment_id": row.id, "rate": .13}))
        await session.flush()
        return {"success": True, "tax_id": row.id, "status": "PAID"}

    @staticmethod
    async def fulfill(session, owner_tg_id, order_id, quantity, now=None):
        now = now or _utcnow()
        quantity = float(quantity)
        if not isfinite(quantity) or quantity <= 0 or abs(quantity - round(quantity, 4)) > 1e-9:
            raise ValueError("Количество должно быть положительным, до 4 знаков после запятой")
        await NextGameCivicService.lock(session)
        company = await NextGameService._owned_company(session, owner_tg_id)
        order = await session.get(NatNextGameCityOrder, order_id, with_for_update=True)
        if not order or order.status != "OPEN" or order.expires_at <= now:
            raise ValueError("Заказ больше не доступен")
        if quantity > order.remaining_quantity + 1e-9:
            raise ValueError("Количество превышает остаток заказа")
        raw_total = quantity * order.unit_price
        if raw_total < .01:
            raise ValueError("Сумма поставки меньше 0,01 cash")
        total = round(raw_total, 8)
        treasury = await NextGameService._treasury(session)
        # The order's own reserve is spendable; other promises remain protected.
        from backend.natbirzha.services.next_game_bond_accounting import required_liability as bond_liability
        other = (await NextGameService._deposit_liability(session) + await bond_liability(session)
                 + await required_liability(session) - order.remaining_quantity * order.unit_price)
        if treasury.cash - other + 1e-9 < total:
            raise ValueError("Недостаточно средств в резерве")
        await NextGameService._change_inventory(session, company.id, order.item_id, -quantity)
        stock = dict(treasury.inventory_json or {})
        stock[order.item_id] = round(float(stock.get(order.item_id, 0)) + quantity, 4)
        treasury.inventory_json = stock
        treasury.cash = round(treasury.cash - total, 8)
        company.cash = round(company.cash + total, 8)
        order.remaining_quantity = round(max(0, order.remaining_quantity - quantity), 4)
        if order.remaining_quantity == 0:
            order.status = "FILLED"
        ledger = NextGameService._ledger(company.id, "CITY_SALE", total, -total, item_id=order.item_id,
            company_quantity=-quantity, treasury_quantity=quantity, metadata={"order_id": order.id})
        ledger.created_at = now
        session.add(ledger)
        await session.flush()
        return {"success": True, "order_id": order.id, "quantity": quantity, "cash_received": total}

    @staticmethod
    async def create_event(session, creator_tg_id, sector_id, duration_hours, now=None):
        if not find_next_game_sector(sector_id) or not isfinite(duration_hours) or not 0 < duration_hours <= 24:
            raise ValueError("Выберите отрасль и длительность до 24 часов")
        now = now or _utcnow()
        await NextGameCivicService.lock(session)
        if await session.scalar(select(NatNextGameEconomicEvent.id).where(
            NatNextGameEconomicEvent.sector_id == sector_id, NatNextGameEconomicEvent.ends_at > now)):
            raise ValueError("В этой отрасли событие уже действует")
        row = NatNextGameEconomicEvent(sector_id=sector_id, starts_at=now,
            ends_at=now + timedelta(hours=duration_hours), creator_tg_id=creator_tg_id)
        session.add(row)
        await session.flush()
        return {"success": True, "event_id": row.id, "ends_at": row.ends_at.isoformat() + "Z"}

    @staticmethod
    async def snapshot(session, owner_tg_id, now=None):
        now = now or _utcnow()
        await NextGameCivicService.lock(session)
        company = await NextGameService._owned_company(session, owner_tg_id)
        account = await assess_company(session, company, now)
        await NextGameCivicService.rotate_orders(session, now)
        taxes = (await session.scalars(select(NatNextGameTaxAssessment).where(
            NatNextGameTaxAssessment.company_id == company.id).order_by(NatNextGameTaxAssessment.id.desc()).limit(60))).all()
        orders = (await session.scalars(select(NatNextGameCityOrder).where(
            NatNextGameCityOrder.status == "OPEN", NatNextGameCityOrder.expires_at > now).order_by(NatNextGameCityOrder.id))).all()
        events = (await session.scalars(select(NatNextGameEconomicEvent).where(NatNextGameEconomicEvent.ends_at > now))).all()
        items = get_next_game_items()
        from backend.natbirzha.models.next_game import NatNextGameInventory
        inventory = {row.item_id: row.quantity for row in (await session.scalars(select(NatNextGameInventory).where(
            NatNextGameInventory.company_id == company.id))).all()}
        return {"cash": company.cash, "tax_rate": .13, "loss_carry": account.loss_carry,
            "next_assessment_at": (cutoff(now) + timedelta(days=1)).isoformat() + "Z",
            "taxes": [{"id": r.id, "period_end": r.period_end.isoformat() + "Z", "operating_profit": r.operating_profit,
                "taxable_profit": r.taxable_profit, "amount": r.amount, "status": r.status} for r in taxes],
            "orders": [{"id": r.id, "item_id": r.item_id, "name": items[r.item_id]["name"], "unit": items[r.item_id]["unit"],
                "unit_price": r.unit_price, "remaining_quantity": r.remaining_quantity, "available_quantity": inventory.get(r.item_id, 0),
                "expires_at": r.expires_at.isoformat() + "Z"} for r in orders],
            "events": [{"id": r.id, "sector_id": r.sector_id, "ends_at": r.ends_at.isoformat() + "Z", "output_multiplier": 1.25} for r in events]}
