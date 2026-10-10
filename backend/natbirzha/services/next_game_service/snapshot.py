"""Read-only snapshots for the isolated NATBIRZHA 2.0 game."""
from datetime import datetime
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.natbirzha.models.next_game import (
    NatNextGameCompany, NatNextGameFacility, NatNextGameInventory,
    NatNextGameLedger, NatNextGameLoan, NatNextGameDeposit,
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
        cls, session: AsyncSession, owner_tg_id: int, *, now: datetime | None = None
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
        market_ids: set[str] = set()
        for facility in facilities:
            branch = find_next_game_branch(facility.branch_id)
            if not branch:
                continue
            recipe = facility_recipe_at_level(branch["factory"], facility.level)
            blocked_reason = await cls._cycle_block_reason(session, company, recipe)
            market_ids.add(recipe["output_item"])
            market_ids.update(recipe["inputs"])
            facility_rows.append({
                "id": facility.id, "branch_id": facility.branch_id,
                "name": recipe["facility_name"], "level": facility.level,
                "next_cycle_at": facility.next_cycle_at.isoformat(), "recipe": recipe,
                "output_multiplier": facility_output_multiplier(facility.level),
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
        own = {row.item_id: float(row.quantity) for row in inventory_rows}
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
        )
        loan_payload = cls._loan_snapshot(active_loan, current) if active_loan else None
        active_deposits = list((await session.scalars(
            select(NatNextGameDeposit).where(NatNextGameDeposit.company_id == company.id)
            .where(NatNextGameDeposit.status == "ACTIVE")
            .order_by(NatNextGameDeposit.matures_at, NatNextGameDeposit.id)
        )).all())
        closed_deposits = list((await session.scalars(
            select(NatNextGameDeposit).where(
                NatNextGameDeposit.company_id == company.id,
                NatNextGameDeposit.status != "ACTIVE",
            ).order_by(NatNextGameDeposit.id.desc()).limit(12)
        )).all())
        deposit_rows = [
            cls._deposit_snapshot(row, current)
            for row in [*active_deposits, *closed_deposits]
        ]
        reserved_deposits = await cls._deposit_liability(session)
        available_treasury_cash = max(0.0, round(float(treasury.cash) - reserved_deposits, 2))
        from backend.natbirzha.services.next_game_market_service import NextGameMarketService

        order_book = await NextGameMarketService.market_snapshot(
            session, company_id=company.id, item_ids=market_ids,
        )
        from backend.natbirzha.services.next_game_equity_service import NextGameEquityService
        from backend.natbirzha.services.next_game_banking_service import NextGameBankingService

        equity = await NextGameEquityService.snapshot(session, company)
        banking = await NextGameBankingService.snapshot(session, company)
        from backend.natbirzha.services.next_game_finance_service import NextGameFinanceContractService

        banking["direct_finance"] = await NextGameFinanceContractService.snapshot(session, company)
        return {
            "company": cls.snapshot_company(company),
            "corporations": get_next_game_catalog(),
            "facilities": facility_rows,
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
