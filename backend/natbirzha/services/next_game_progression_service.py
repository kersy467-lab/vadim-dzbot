"""Paid PVC progression, mastery and financially complete civilian rebirth."""
from sqlalchemy import delete, select
from backend.natbirzha.models.next_game import NatNextGameFacility, NatNextGameInventory
from backend.natbirzha.models.next_game_community import NatNextGameProfile, NatNextGameHelpRequest
from backend.natbirzha.models.next_game_progression import NatNextGameMerger
from backend.natbirzha.next_game_catalog import find_next_game_branch
from backend.natbirzha.services.next_game_rebirth_assets import sweep_reserve_income, transfer_financial_assets
from backend.natbirzha.services.next_game_rebirth_settlement import (
    blockers, close_orders_and_offers, close_partnership_offers, redeem_deposits, repay_obligations, repayment_quote,
)

MAX_REBIRTHS = 10
MAX_PVC_LEVEL = 50


def mastery_rank(company):
    # Production caps company.level at 60. XP continues to accrue beyond it.
    return max(0, (int(company.xp or 0) - 59000) // 1000)


def pvc_upgrade_price(level):
    return 25 * (int(level) + 1) ** 2


class NextGameProgressionService:
    @staticmethod
    async def production_bonus(session, company):
        profile = await session.get(NatNextGameProfile, company.id)
        rebirths = int(profile.rebirths or 0) if profile else 0
        pvc_level = int(profile.pvc_level or 0) if profile else 0
        return (1.25 ** rebirths) * (1 + .05 * pvc_level) * (1 + .01 * mastery_rank(company))

    @staticmethod
    async def terminal_ready(session, company):
        path = list(company.branch_path or [])
        branch = find_next_game_branch(path[-1]) if path else None
        if not branch or not branch["terminal"]:
            return False
        facility = await session.scalar(select(NatNextGameFacility.id).where(
            NatNextGameFacility.company_id == company.id, NatNextGameFacility.branch_id == path[-1],
        ))
        if facility:
            return True
        mergers = (await session.scalars(select(NatNextGameMerger).where(
            NatNextGameMerger.company_id == company.id, NatNextGameMerger.status == "ACTIVE",
        ))).all()
        return any(source["branch_id"] == path[-1] for merger in mergers for source in merger.sources_json)

    @classmethod
    async def snapshot(cls, session, owner_tg_id):
        from backend.natbirzha.services.next_game_service import NextGameService
        from backend.natbirzha.services.next_game_fusion_service import NextGameFusionService
        company = await NextGameService._owned_company(session, owner_tg_id)
        profile = await session.get(NatNextGameProfile, company.id)
        rebirths, pvc_level, pvc = ((profile.rebirths, profile.pvc_level, profile.pvc_balance)
                                  if profile else (0, 0, 0))
        from backend.natbirzha.services.next_game_service.common import _utcnow
        financial = await repayment_quote(session, company, _utcnow())
        reasons = await blockers(session, company.id)
        if financial["shortfall"] > 0:
            reasons.append(f"Для погашения долгов не хватает {financial['shortfall']:,.2f} cash")
        terminal = await cls.terminal_ready(session, company)
        if not terminal:
            reasons.insert(0, "Пройдите маршрут до последней эпохи и постройте её предприятие")
        if rebirths >= MAX_REBIRTHS:
            reasons.append("Достигнут предел: 10 перерождений")
        rank = mastery_rank(company)
        return {
            "company_id": company.id, "rebirths": rebirths, "max_rebirths": MAX_REBIRTHS,
            "pvc_balance": pvc, "pvc_level": pvc_level, "max_pvc_level": MAX_PVC_LEVEL,
            "pvc_upgrade_price": pvc_upgrade_price(pvc_level) if pvc_level < MAX_PVC_LEVEL else None,
            "pvc_bonus_pct": pvc_level * 5, "mastery_rank": rank, "mastery_bonus_pct": rank,
            "mastery_unlock_level": 60, "mastery_next_rank_xp": 60000 + rank * 1000,
            "production_multiplier": round(await cls.production_bonus(session, company), 6),
            "rebirth_ready": not reasons, "rebirth_blockers": reasons, "rebirth_financials": financial,
            "rebirth_policy": "Деньги и товары передаются резерву; вклады закрываются, долги погашаются. Чужие акции и кредитные требования переходят резервному банку. Своё IPO и акции инвесторов сохраняются. PVC сохраняется. Новый старт 10000 из конечной казны.",
            "fusion": await NextGameFusionService.snapshot(session, company.id),
        }

    @classmethod
    async def upgrade_pvc(cls, session, owner_tg_id):
        from backend.natbirzha.services.next_game_service import NextGameService
        from backend.natbirzha.services.next_game_community_service import profile
        await NextGameService._lock_treasury_for_sqlite(session)
        company = await NextGameService._owned_company(session, owner_tg_id)
        row = await profile(session, company.id)
        if row.pvc_level >= MAX_PVC_LEVEL:
            raise ValueError("Достигнут предел PVC-улучшений")
        price = pvc_upgrade_price(row.pvc_level)
        if row.pvc_balance + 1e-8 < price:
            raise ValueError(f"Для улучшения требуется {price} PVC")
        row.pvc_balance = round(row.pvc_balance - price, 4)
        row.pvc_level += 1
        session.add(NextGameService._ledger(company.id, "PVC_UPGRADE", 0, 0,
            metadata={"pvc_delta": -price, "pvc_level": row.pvc_level}))
        await session.flush()
        return {"success": True, "paid_pvc": price, "pvc_balance": row.pvc_balance,
                "pvc_level": row.pvc_level, "production_multiplier": await cls.production_bonus(session, company)}

    @classmethod
    async def rebirth(cls, session, owner_tg_id, *, confirm=False):
        if confirm is not True:
            raise ValueError("Подтвердите передачу активов и перезапуск компании")
        # A failed repayment or reserve check rolls the complete reset back,
        # including coupon forfeiture and cancelled financial reservations.
        async with session.begin_nested():
            return await cls._rebirth(session, owner_tg_id)

    @classmethod
    async def _rebirth(cls, session, owner_tg_id):
        from backend.natbirzha.services.next_game_service import NextGameService
        from backend.natbirzha.services.next_game_service.common import _utcnow, STARTING_COMPANY_CASH
        from backend.natbirzha.services.next_game_market_service import NextGameMarketService
        from backend.natbirzha.services.next_game_community_service import profile
        from backend.natbirzha.services.next_game_bond_accounting import forfeit_company_holdings
        await NextGameMarketService.lock_orderbook(session)
        company = await NextGameService._owned_company(session, owner_tg_id)
        row = await profile(session, company.id)
        if row.rebirths >= MAX_REBIRTHS:
            raise ValueError("Достигнут предел: 10 перерождений")
        if not await cls.terminal_ready(session, company):
            raise ValueError("Для перерождения постройте предприятие последней эпохи выбранного маршрута")
        reasons = await blockers(session, company.id)
        if reasons:
            raise ValueError(reasons[0])
        current = _utcnow()
        # Even matured-but-unread holdings cannot pay after the old run ends.
        forfeited_bonds = await forfeit_company_holdings(session, company.id)
        await close_partnership_offers(session, company, current)
        sells = await close_orders_and_offers(session, company, current)
        await redeem_deposits(session, company, current)
        await repay_obligations(session, company, sells, current)
        from backend.natbirzha.services.next_game_civic_accounting import retire_company as retire_civic
        from backend.natbirzha.services.next_game_operations_effects import retire_company as retire_operations
        await retire_civic(session, company.id)
        await retire_operations(session, company.id)
        transferred = await transfer_financial_assets(session, company, current)
        treasury = await NextGameService._treasury(session)
        inventories = (await session.scalars(select(NatNextGameInventory).where(
            NatNextGameInventory.company_id == company.id,
        ).with_for_update())).all()
        stock = dict(treasury.inventory_json or {})
        for inventory in inventories:
            quantity = float(inventory.quantity)
            if quantity:
                stock[inventory.item_id] = round(stock.get(inventory.item_id, 0) + quantity, 4)
                session.add(NextGameService._ledger(company.id, "REBIRTH_GOODS_DONATE", 0, 0,
                    item_id=inventory.item_id, company_quantity=-quantity, treasury_quantity=quantity))
        treasury.inventory_json = stock
        donation = float(company.cash)
        company.cash = 0
        treasury.cash = round(treasury.cash + donation, 8)
        session.add(NextGameService._ledger(company.id, "REBIRTH_CASH_DONATE", -donation, donation))
        await sweep_reserve_income(session)
        if await NextGameService._available_treasury_cash(session, treasury) + 1e-8 < STARTING_COMPANY_CASH:
            raise ValueError("Казне не хватает свободных средств на новый старт; активы сохраняются")
        treasury.cash = round(treasury.cash - STARTING_COMPANY_CASH, 8)
        company.cash = STARTING_COMPANY_CASH
        company.sector_id, company.branch_path, company.level, company.xp = None, [], 1, 0
        company.updated_at = current
        row.rebirths += 1
        await session.execute(delete(NatNextGameInventory).where(NatNextGameInventory.company_id == company.id))
        await session.execute(delete(NatNextGameFacility).where(NatNextGameFacility.company_id == company.id))
        mergers = (await session.scalars(select(NatNextGameMerger).where(
            NatNextGameMerger.company_id == company.id, NatNextGameMerger.status == "ACTIVE",
        ))).all()
        for merger in mergers:
            merger.status, merger.dissolved_at = "RESET", current
        requests = (await session.scalars(select(NatNextGameHelpRequest).where(
            NatNextGameHelpRequest.company_id == company.id, NatNextGameHelpRequest.status == "OPEN",
        ))).all()
        for request in requests:
            request.status = "CLOSED"
        session.add(NextGameService._ledger(company.id, "REBIRTH_STARTUP", STARTING_COMPANY_CASH,
            -STARTING_COMPANY_CASH, metadata={"rebirths": row.rebirths, "transferred": transferred, "bonds": forfeited_bonds}))
        await session.flush()
        return {"success": True, "company": NextGameService.snapshot_company(company),
                "rebirths": row.rebirths, "pvc_balance": row.pvc_balance, "transferred_assets": transferred}

    sweep_reserve_income = staticmethod(sweep_reserve_income)
