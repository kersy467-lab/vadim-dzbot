"""Explicit sandbox administration; every issuance and grant is audited."""
from sqlalchemy import select
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_community import NatNextGameAdminAudit
from backend.natbirzha.next_game_catalog import get_next_game_items
from backend.natbirzha.services.next_game_community_service import amount
from backend.natbirzha.services.next_game_market_service import NextGameMarketService
from backend.natbirzha.services.next_game_service import MAX_INVENTORY_PER_ITEM, NextGameService


class NextGameAdminService:
    @staticmethod
    async def snapshot(session):
        treasury = await NextGameService._treasury(session)
        companies = (await session.scalars(select(NatNextGameCompany).where(NatNextGameCompany.owner_tg_id > 0).order_by(NatNextGameCompany.id))).all()
        audit = (await session.scalars(select(NatNextGameAdminAudit).order_by(NatNextGameAdminAudit.id.desc()).limit(25))).all()
        return {"treasury": {"cash": treasury.cash, "inventory": treasury.inventory_json},
            "companies": [{"id": c.id, "name": c.name, "owner_tg_id": c.owner_tg_id,
                "cash": c.cash, "level": c.level} for c in companies],
            "audit": [{"actor_tg_id": r.actor_tg_id, "action": r.action, "details": r.metadata_json,
                "created_at": r.created_at.isoformat()} for r in audit]}

    @staticmethod
    async def operate(session, actor_tg_id, action, company_id, value, item_id, note):
        value = amount(value, 100_000_000_000_000)
        if action not in {"TREASURY_TOPUP", "CASH_GRANT", "ITEM_GRANT", "PVC_GRANT"}:
            raise ValueError("Неизвестная админская операция")
        if action != "ITEM_GRANT" and abs(value - round(value, 2)) > 1e-9:
            raise ValueError("Денежная сумма может содержать максимум 2 знака после запятой")
        note = str(note or "").strip()[:240]
        if not note:
            raise ValueError("Укажи причину операции")
        await NextGameMarketService.lock_orderbook(session)
        company = None
        if action != "TREASURY_TOPUP":
            company = await session.get(NatNextGameCompany, company_id, with_for_update=True)
            if company is None or company.owner_tg_id <= 0:
                raise ValueError("Компания 2.0 не найдена")
        treasury = await NextGameService._treasury(session)
        if action == "TREASURY_TOPUP":
            treasury.cash = round(treasury.cash + value, 8)
        elif action == "CASH_GRANT":
            if await NextGameService._available_treasury_cash(session, treasury) < value:
                raise ValueError("Недостаточно свободных средств расчётного резерва")
            company.cash = round(company.cash + value, 8)
            treasury.cash = round(treasury.cash - value, 8)
            session.add(NextGameService._ledger(company.id, "ADMIN_GRANT", value, -value,
                metadata={"actor_tg_id": actor_tg_id, "note": note}))
        elif action == "PVC_GRANT":
            from backend.natbirzha.services.next_game_community_service import profile
            row = await profile(session, company.id)
            row.pvc_balance = round(row.pvc_balance + value, 2)
        else:
            from backend.natbirzha.services.next_game_operations_effects import warehouse_capacity
            capacity = await warehouse_capacity(session, company.id)
            if item_id not in get_next_game_items() or value > capacity:
                raise ValueError("Неизвестный товар или превышен объём склада")
            row = await NextGameService._inventory_row(session, company.id, item_id)
            reserved = await NextGameMarketService.reserved_sell_quantity(session, company.id, item_id)
            if float(row.quantity if row else 0) + reserved + value > capacity:
                raise ValueError("Склад компании заполнен")
            await NextGameService._change_inventory(session, company.id, item_id, value, row=row)
        session.add(NatNextGameAdminAudit(actor_tg_id=actor_tg_id, action=action,
            metadata_json={"company_id": company_id, "value": value, "item_id": item_id, "note": note}))
        await session.flush()
        return {"success": True, "action": action}
