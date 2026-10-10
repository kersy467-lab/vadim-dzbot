"""Read-only snapshots for the isolated NATBIRZHA 2.0 game."""
from datetime import datetime
from typing import Any
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.natbirzha.models.next_game import (
    NatNextGameCompany, NatNextGameFacility, NatNextGameInventory,
    NatNextGameLedger, NatNextGameLoan, NatNextGameDeposit,
    NatNextGameMarketOrder,
)
from backend.natbirzha.next_game_catalog import (
    find_next_game_branch, get_next_game_catalog, get_next_game_items,
)
from .common import (
    BUY_MARKUP, SELL_MARKDOWN, MAX_BANK_LOAN, MAX_FACILITY_LEVEL,
    XP_PER_LEVEL, _utcnow, facility_output_multiplier,
    facility_recipe_at_level, facility_upgrade_cost,
)

class NextGameSnapshotMixin:
    @staticmethod
    def snapshot_company(company: NatNextGameCompany | None) -> dict[str, Any] | None:
        if company is None:
            return None
        return {
            "id": company.id,
            "name": company.name,
            "cash": round(float(company.cash), 2),
            "level": int(company.level),
            "xp": int(company.xp),
            "xp_to_next_level": max(0, int(company.level) * XP_PER_LEVEL - int(company.xp)),
            "sector_id": company.sector_id,
            "branch_path": list(company.branch_path or []),
        }

    @classmethod
    async def snapshot(
        cls, session: AsyncSession, owner_tg_id: int, *, now: datetime | None = None,
        section: str = "full",
    ) -> dict[str, Any]:
        await cls._lock_treasury_for_sqlite(session)
        company = await session.scalar(
            select(NatNextGameCompany).where(NatNextGameCompany.owner_tg_id == owner_tg_id)
        )
        if company is None:
            return {"company": None, "corporations": get_next_game_catalog()}
        await cls.settle_company(session, owner_tg_id, now=now)
        company = await cls._owned_company(session, owner_tg_id)
        treasury = await cls._treasury(session)
        items = get_next_game_items()
        inventory_rows = (await session.scalars(
            select(NatNextGameInventory).where(
                NatNextGameInventory.company_id == company.id,
                NatNextGameInventory.quantity > 0,
            ).order_by(NatNextGameInventory.item_id)
        )).all()
        inventory = [
            {"item_id": row.item_id, "name": items[row.item_id]["name"],
             "unit": items[row.item_id]["unit"], "quantity": round(float(row.quantity), 4)}
            for row in inventory_rows if row.item_id in items
        ]
        facilities = list((await session.scalars(
            select(NatNextGameFacility).where(NatNextGameFacility.company_id == company.id)
            .order_by(NatNextGameFacility.id)
        )).all())
        facility_rows = []
        current = now or _utcnow()
        from backend.natbirzha.services.next_game_progression_service import NextGameProgressionService
        from backend.natbirzha.services.next_game_operations_effects import (
            factory_recipe, warehouse_capacity, production_slots, used_production_slots,
        )
        from backend.natbirzha.services.next_game_civic_accounting import event_multiplier
        bonus = await NextGameProgressionService.production_bonus(session, company)
        bonus *= await event_multiplier(session, company, now=current)
        warehouse_limit = await warehouse_capacity(session, company.id)
        own = {row.item_id: float(row.quantity) for row in inventory_rows}
        reserved = dict((await session.execute(select(NatNextGameMarketOrder.item_id,
            func.sum(NatNextGameMarketOrder.remaining_quantity)).where(
                NatNextGameMarketOrder.company_id == company.id,
                NatNextGameMarketOrder.side == "SELL", NatNextGameMarketOrder.status == "OPEN")
            .group_by(NatNextGameMarketOrder.item_id))).all())
        from backend.natbirzha.models.next_game_progression import NatNextGameMerger
        mergers = (await session.scalars(select(NatNextGameMerger).where(
            NatNextGameMerger.company_id == company.id, NatNextGameMerger.status == "ACTIVE"))).all()
        consumed_branch_ids = sorted({source["branch_id"] for merger in mergers for source in merger.sources_json})
        merger_recipes = {merger.branch_id: merger.recipe_json for merger in mergers}
        market_ids: set[str] = set()
        for facility in facilities:
            branch = find_next_game_branch(facility.branch_id)
            if not branch:
                continue
            base_recipe = {**branch["factory"], **merger_recipes.get(facility.branch_id, {})}
            recipe = facility_recipe_at_level(base_recipe, facility.level)
            recipe["output_quantity"] = round(recipe["output_quantity"] * bonus, 4)
            recipe = await factory_recipe(session, company, facility, recipe, now=current)
            blocked_reason = None
            if company.cash < recipe["operating_cost"]:
                blocked_reason = "Недостаточно cash на расходы цикла"
            for item_id, needed in recipe["inputs"].items():
                if own.get(item_id, 0) + 1e-9 < needed:
                    blocked_reason = f"{items[item_id]['name']}: не хватает {needed - own.get(item_id, 0):g} {items[item_id]['unit']}"
                    break
            output_id = recipe["output_item"]
            if own.get(output_id, 0) + reserved.get(output_id, 0) + recipe["output_quantity"] > warehouse_limit:
                blocked_reason = "Склад заполнен; продайте готовый товар"
            market_ids.add(recipe["output_item"])
            market_ids.update(recipe["inputs"])
            facility_rows.append({
                "id": facility.id, "branch_id": facility.branch_id,
                "name": recipe["facility_name"], "level": facility.level,
                "next_cycle_at": facility.next_cycle_at.isoformat(), "recipe": recipe,
                "output_multiplier": facility_output_multiplier(facility.level) * bonus,
                "upgrade_cost": (
                    facility_upgrade_cost(facility.level)
                    if int(facility.level) < MAX_FACILITY_LEVEL else None
                ),
                "upgrade_level": int(facility.level) + 1,
                "required_company_level": int(facility.level) + 1,
                "status": "blocked" if blocked_reason else "active",
                "blocked_reason": blocked_reason,
                "seconds_to_cycle": max(0, int((facility.next_cycle_at - current).total_seconds())),
            })
        built_branch_ids = {facility.branch_id for facility in facilities}
        for branch_id in company.branch_path or []:
            if branch_id in built_branch_ids:
                continue
            branch = find_next_game_branch(branch_id)
            if branch:
                market_ids.add(branch["factory"]["output_item"])
                market_ids.update(branch["factory"]["inputs"])
        reserve = dict(treasury.inventory_json or {})
        market = []
        for item_id in sorted(market_ids):
            item = items[item_id]
            base = float(item["base_price"])
            market.append({
                "item_id": item_id, "name": item["name"], "unit": item["unit"],
                "quantity": round(own.get(item_id, 0.0), 4),
                "npc_quantity": round(float(reserve.get(item_id, 0.0)), 4),
                "buy_price": round(base * BUY_MARKUP, 2),
                "sell_price": round(base * SELL_MARKDOWN, 2),
            })
        ledger_rows = list((await session.scalars(
            select(NatNextGameLedger).where(NatNextGameLedger.company_id == company.id)
            .order_by(NatNextGameLedger.created_at.desc(), NatNextGameLedger.id.desc())
            .limit(12)
        )).all())
        recent_activity = []
        for row in ledger_rows:
            item = items.get(row.item_id) if row.item_id else None
            recent_activity.append({
                "action": row.action,
                "cash_change": round(float(row.cash_company_delta), 2),
                "item_name": item["name"] if item else None,
                "unit": item["unit"] if item else None,
                "quantity_change": round(float(row.quantity_company_delta), 4),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })
        active_loan = await session.scalar(
            select(NatNextGameLoan).where(
                NatNextGameLoan.company_id == company.id,
                NatNextGameLoan.status == "ACTIVE",
            ).order_by(NatNextGameLoan.id.desc()).with_for_update()
        ) if section in {"full", "bank"} else None
        loan_payload = cls._loan_snapshot(active_loan, current) if active_loan else None
        active_deposits = list((await session.scalars(
            select(NatNextGameDeposit).where(NatNextGameDeposit.company_id == company.id)
            .where(NatNextGameDeposit.status == "ACTIVE")
            .order_by(NatNextGameDeposit.matures_at, NatNextGameDeposit.id)
        )).all()) if section in {"full", "bank"} else []
        closed_deposits = list((await session.scalars(
            select(NatNextGameDeposit).where(
                NatNextGameDeposit.company_id == company.id,
                NatNextGameDeposit.status != "ACTIVE",
            ).order_by(NatNextGameDeposit.id.desc()).limit(12)
        )).all()) if section in {"full", "bank"} else []
        deposit_rows = [
            cls._deposit_snapshot(row, current)
            for row in [*active_deposits, *closed_deposits]
        ]
        reserved_deposits = await cls._deposit_liability(session)
        available_treasury_cash = await cls._available_treasury_cash(session, treasury)
        from backend.natbirzha.services.next_game_market_service import NextGameMarketService

        order_book = await NextGameMarketService.market_snapshot(
            session, company_id=company.id, item_ids=market_ids,
        ) if section in {"full", "market"} else {}
        from backend.natbirzha.services.next_game_equity_service import NextGameEquityService
        from backend.natbirzha.services.next_game_banking_service import NextGameBankingService

        equity = await NextGameEquityService.snapshot(session, company) if section in {"full", "capital"} else {}
        banking = await NextGameBankingService.snapshot(session, company) if section in {"full", "bank"} else {}
        from backend.natbirzha.services.next_game_finance_service import NextGameFinanceContractService

        if section in {"full", "bank"}:
            banking["direct_finance"] = await NextGameFinanceContractService.snapshot(session, company)
        from backend.natbirzha.services.next_game_community_service import profile
        settings = await profile(session, company.id)
        from backend.natbirzha.services.next_game_production_summary import production_summary
        return {
            "company": cls.snapshot_company(company),
            "settings": {"auto_upgrade": settings.auto_upgrade, "rebirths": settings.rebirths,
                         "pvc_balance": settings.pvc_balance, "pvc_level": settings.pvc_level},
            "corporations": get_next_game_catalog(),
            "facilities": facility_rows,
            "consumed_branch_ids": consumed_branch_ids,
            "capacity": {"warehouse_capacity": warehouse_limit,
                         "production_slots": await production_slots(session, company.id),
                         "used_slots": await used_production_slots(session, company.id)},
            "production": production_summary(company, facility_rows, own),
            "inventory": inventory,
            "market": market,
            "market_orders": order_book,
            "equity": equity,
            "banking": banking,
            "treasury": {
                "cash": available_treasury_cash,
                "total_cash": round(float(treasury.cash), 2),
                "reserved_for_deposits": reserved_deposits,
            },
            "recent_activity": recent_activity,
            "deposits": deposit_rows,
            "bank_loan": loan_payload,
            "bank_credit_limit": 0.0 if active_loan else round(min(MAX_BANK_LOAN, available_treasury_cash), 2),
        }
