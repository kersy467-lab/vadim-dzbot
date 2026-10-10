"""Corporate aid at every level; transfers conserve cash and resources."""
from math import isfinite
from sqlalchemy import select
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_community import NatNextGameHelpRequest, NatNextGameProfile, NatNextGameTransfer
from backend.natbirzha.next_game_catalog import get_next_game_items
from backend.natbirzha.services.next_game_market_service import NextGameMarketService
from backend.natbirzha.services.next_game_service import MAX_INVENTORY_PER_ITEM, NextGameService


def amount(value, maximum=1_000_000_000):
    value = float(value)
    if not isfinite(value) or value <= 0 or value > maximum or abs(value - round(value, 4)) > 1e-9:
        raise ValueError("Укажи положительное количество с точностью до 4 знаков")
    return round(value, 4)


async def profile(session, company_id):
    row = await session.get(NatNextGameProfile, company_id)
    if row is None:
        row = NatNextGameProfile(company_id=company_id, auto_upgrade=False, rebirths=0, pvc_balance=0, pvc_level=0)
        session.add(row)
        await session.flush()
    return row


class NextGameCommunityService:
    @staticmethod
    async def snapshot(session, owner_tg_id):
        company = await NextGameService._owned_company(session, owner_tg_id)
        rows = (await session.execute(select(NatNextGameHelpRequest, NatNextGameCompany.name)
            .join(NatNextGameCompany, NatNextGameCompany.id == NatNextGameHelpRequest.company_id)
            .where(NatNextGameHelpRequest.status == "OPEN")
            .order_by(NatNextGameHelpRequest.created_at.desc()).limit(100))).all()
        items = get_next_game_items()
        return {"company_id": company.id, "items": [{"id": key, **row} for key, row in items.items()],
            "requests": [{"id": row.id, "company_id": row.company_id, "company_name": name,
                "item_id": row.item_id, "name": items[row.item_id]["name"] if row.item_id else "Cash",
                "unit": items[row.item_id]["unit"] if row.item_id else "cash", "goal": row.goal,
                "received": row.received, "description": row.description, "status": row.status} for row, name in rows]}

    @staticmethod
    async def create_request(session, owner_tg_id, item_id, goal, description):
        goal = amount(goal, 1_000_000_000)
        if not item_id and abs(goal - round(goal, 2)) > 1e-9:
            raise ValueError("Сумма cash может содержать максимум 2 знака после запятой")
        if item_id and item_id not in get_next_game_items():
            raise ValueError("Неизвестный ресурс")
        await NextGameMarketService.lock_orderbook(session)
        company = await NextGameService._owned_company(session, owner_tg_id)
        from backend.natbirzha.services.next_game_operations_effects import warehouse_capacity
        if item_id and goal > await warehouse_capacity(session, company.id):
            raise ValueError("Запрос превышает вместимость склада компании")
        active = (await session.scalars(select(NatNextGameHelpRequest).where(
            NatNextGameHelpRequest.company_id == company.id, NatNextGameHelpRequest.status == "OPEN"))).all()
        if len(active) >= 5:
            raise ValueError("Можно держать открытыми до 5 запросов помощи")
        request = NatNextGameHelpRequest(company_id=company.id, item_id=item_id, goal=goal,
            received=0, description=str(description or "").strip()[:240], status="OPEN")
        session.add(request)
        await session.flush()
        return {"success": True, "request_id": request.id}

    @staticmethod
    async def donate(session, owner_tg_id, request_id, quantity):
        quantity = amount(quantity)
        await NextGameMarketService.lock_orderbook(session)
        donor = await NextGameService._owned_company(session, owner_tg_id)
        request = await session.get(NatNextGameHelpRequest, request_id, with_for_update=True)
        if request is None or request.status != "OPEN":
            raise ValueError("Запрос уже закрыт или не найден")
        if donor.id == request.company_id:
            raise ValueError("Нельзя передавать помощь самому себе")
        if not request.item_id and abs(quantity - round(quantity, 2)) > 1e-9:
            raise ValueError("Сумма cash может содержать максимум 2 знака после запятой")
        recipient = await session.get(NatNextGameCompany, request.company_id, with_for_update=True)
        transfer = min(quantity, round(request.goal - request.received, 4))
        if request.item_id:
            source = await NextGameService._inventory_row(session, donor.id, request.item_id)
            dest = await NextGameService._inventory_row(session, recipient.id, request.item_id)
            if source is None or source.quantity + 1e-9 < transfer:
                raise ValueError("Недостаточно свободного товара на складе")
            reserved = await NextGameMarketService.reserved_sell_quantity(session, recipient.id, request.item_id)
            from backend.natbirzha.services.next_game_operations_effects import warehouse_capacity
            if float(dest.quantity if dest else 0) + reserved + transfer > await warehouse_capacity(session, recipient.id):
                raise ValueError("Склад получателя заполнен")
            await NextGameService._change_inventory(session, donor.id, request.item_id, -transfer, row=source)
            await NextGameService._change_inventory(session, recipient.id, request.item_id, transfer, row=dest)
        else:
            transfer = round(transfer, 2)
            if transfer <= 0 or donor.cash + 1e-9 < transfer:
                raise ValueError("Недостаточно cash для помощи")
            donor.cash = round(donor.cash - transfer, 8)
            recipient.cash = round(recipient.cash + transfer, 8)
        request.received = round(request.received + transfer, 4)
        if request.received >= request.goal - 1e-9:
            request.status = "COMPLETE"
        session.add(NatNextGameTransfer(sender_company_id=donor.id, recipient_company_id=recipient.id,
            cash=0 if request.item_id else transfer, item_id=request.item_id,
            quantity=transfer if request.item_id else 0, reason="AID", metadata_json={"request_id": request.id}))
        await session.flush()
        return {"success": True, "transferred": transfer, "status": request.status}

    @staticmethod
    async def close_request(session, owner_tg_id, request_id):
        await NextGameMarketService.lock_orderbook(session)
        company = await NextGameService._owned_company(session, owner_tg_id)
        request = await session.get(NatNextGameHelpRequest, request_id, with_for_update=True)
        if request is None or request.company_id != company.id:
            raise ValueError("Свой запрос не найден")
        request.status = "CLOSED"
        await session.flush()
        return {"success": True}
