"""Explicit, atomic beta liquidation and one recovery choice per episode."""
from datetime import timedelta
from sqlalchemy import func, select
from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameFacility
from backend.natbirzha.models.next_game_bankruptcy import NatNextGameBankruptcy, NatNextGameDebtWriteoff, NatNextGameLiquidationLot
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.services.next_game_market_service import NextGameMarketService as Market
from backend.natbirzha.services.next_game_service.common import _utcnow
from backend.natbirzha.next_game_catalog import find_next_game_branch
from backend.natbirzha.services.next_game_bankruptcy_debts import close_debts, confiscate_orders, forgive_taxes
from backend.natbirzha.services.next_game_bankruptcy_assets import close_partnerships, list_factories, seize_inventory_and_cash, offer_reserve_shares

RESTART_GRANT = 100_000.0


class NextGameBankruptcyService:
    @staticmethod
    async def status(session, company_id):
        row = await session.get(NatNextGameBankruptcy, company_id)
        if not row:
            return {"requires_ack": False, "was_triggered": False}
        return {"company_id": company_id, "requires_ack": row.requires_ack, "was_triggered": row.was_triggered,
            "sequence": row.sequence, "note": row.note, "triggered_at": row.triggered_at.isoformat() + "Z",
            "recovery_choice": row.recovery_choice, "restart_grant": RESTART_GRANT}

    @staticmethod
    async def recovery_snapshot(session, owner_tg_id):
        await Market.lock_orderbook(session)
        company = await Game._owned_company(session, owner_tg_id, allow_recovery=True)
        result = await NextGameBankruptcyService.status(session, company.id)
        treasury = await Game._treasury(session)
        result.update(cash=company.cash, can_restart=await Game._available_treasury_cash(session, treasury) >= RESTART_GRANT)
        losses = (await session.scalars(select(NatNextGameDebtWriteoff).where(
            NatNextGameDebtWriteoff.company_id == company.id).order_by(NatNextGameDebtWriteoff.id.desc()).limit(60))).all()
        result["writeoffs"] = [{"kind": row.kind, "id": row.obligation_id, "amount": row.amount,
            "status": "WRITTEN_OFF"} for row in losses]
        return result

    @staticmethod
    async def force(session, company_id, note, creator_tg_id, now=None):
        note = str(note or "").strip()
        if not 5 <= len(note) <= 500:
            raise ValueError("Укажите причину банкротства: от 5 до 500 символов")
        await Market.lock_orderbook(session)
        company = await session.get(NatNextGameCompany, int(company_id), with_for_update=True)
        if not company or company.owner_tg_id <= 0:
            raise ValueError("Выберите действующую компанию игрока")
        row = await session.get(NatNextGameBankruptcy, company.id, with_for_update=True)
        if row and row.requires_ack:
            raise ValueError("Компания уже ожидает решения после банкротства")
        current = now or _utcnow()
        episode = row.sequence + 1 if row else 1
        # A failed guard leaves the entire prior company intact even for service callers.
        async with session.begin_nested():
            from backend.natbirzha.services.next_game_rebirth_settlement import close_orders_and_offers
            from backend.natbirzha.services.next_game_rebirth_assets import transfer_financial_assets
            from backend.natbirzha.services.next_game_bond_accounting import forfeit_company_holdings
            await close_partnerships(session, company, current)
            await confiscate_orders(session, company, current)
            await close_orders_and_offers(session, company, current)
            await close_debts(session, company, current)
            await forgive_taxes(session, company, current)
            await forfeit_company_holdings(session, company.id)
            transferred = await transfer_financial_assets(session, company, current)
            lots = await list_factories(session, company, episode, current)
            cash = await seize_inventory_and_cash(session, company)
            if row is None:
                row = NatNextGameBankruptcy(company_id=company.id)
                session.add(row)
            row.requires_ack, row.was_triggered, row.sequence = True, True, episode
            row.note, row.creator_tg_id, row.triggered_at = note, creator_tg_id, current
            row.acknowledged_at, row.recovery_choice = None, None
            session.add(Game._ledger(company.id, "BANKRUPTCY_FORCE", 0, 0,
                metadata={"episode": episode, "creator_tg_id": creator_tg_id, "note": note, "lots": lots,
                          "cash_seized": cash, "transferred": transferred}))
            from backend.natbirzha.models.next_game_community import NatNextGameAdminAudit
            session.add(NatNextGameAdminAudit(actor_tg_id=creator_tg_id, action="BANKRUPTCY_FORCE",
                metadata_json={"company_id": company.id, "company_name": company.name, "note": note,
                               "episode": episode, "value": cash, "factory_lots": lots}, created_at=current))
            await session.flush()
            await offer_reserve_shares(session)
        return {"success": True, "bankruptcy": await NextGameBankruptcyService.status(session, company.id),
            "factory_lots": lots, "cash_seized": cash}

    @staticmethod
    async def recover(session, owner_tg_id, restart):
        if not isinstance(restart, bool):
            raise ValueError("Выберите перезапуск или продолжение")
        await Market.lock_orderbook(session)
        company = await Game._owned_company(session, owner_tg_id, allow_recovery=True)
        row = await session.get(NatNextGameBankruptcy, company.id, with_for_update=True)
        choice = "RESTART" if restart else "CONTINUE"
        if not row:
            raise ValueError("Компания не проходила банкротство")
        if not row.requires_ack:
            if row.recovery_choice != choice:
                raise ValueError("Решение для этого банкротства уже принято")
            return {"success": True, "bankruptcy": await NextGameBankruptcyService.status(session, company.id)}
        async with session.begin_nested():
            if restart:
                treasury = await Game._treasury(session)
                # An explicit admin grant while pending is also an ordinary asset of the old run.
                await list_factories(session, company, row.sequence, _utcnow())
                await seize_inventory_and_cash(session, company)
                if await Game._available_treasury_cash(session, treasury) < RESTART_GRANT:
                    raise ValueError("В резерве недостаточно свободных средств на перезапуск; можно продолжить")
                # Ordinary assets were already removed atomically by force(); keep IPO and PVC identities.
                company.sector_id, company.branch_path, company.level, company.xp = None, [], 1, 0
                treasury.cash = round(treasury.cash - RESTART_GRANT, 8)
                company.cash = round(company.cash + RESTART_GRANT, 8)
                session.add(Game._ledger(company.id, "BANKRUPTCY_RESTART", RESTART_GRANT, -RESTART_GRANT,
                    metadata={"episode": row.sequence}))
            row.requires_ack, row.recovery_choice, row.acknowledged_at = False, choice, _utcnow()
            await session.flush()
        return {"success": True, "bankruptcy": await NextGameBankruptcyService.status(session, company.id)}

    @staticmethod
    async def liquidation_snapshot(session, owner_tg_id):
        await Market.lock_orderbook(session)
        company = await Game._owned_company(session, owner_tg_id)
        lots = (await session.scalars(select(NatNextGameLiquidationLot).where(
            NatNextGameLiquidationLot.status == "OPEN").order_by(NatNextGameLiquidationLot.id).limit(200))).all()
        owned = set((await session.scalars(select(NatNextGameFacility.branch_id).where(
            NatNextGameFacility.company_id == company.id))).all())
        result = []
        for lot in lots:
            branch = find_next_game_branch(lot.branch_id)
            if branch:
                result.append({"id": lot.id, "branch_id": lot.branch_id, "name": branch["factory"]["facility_name"],
                    "level": lot.level, "price": lot.price, "source_company_id": lot.source_company_id,
                    "unlocked": lot.branch_id in (company.branch_path or []), "already_owned": lot.branch_id in owned})
        return {"cash": company.cash, "lots": result}

    @staticmethod
    async def buy_lot(session, owner_tg_id, lot_id):
        await Market.lock_orderbook(session)
        company = await Game._owned_company(session, owner_tg_id)
        status = await NextGameBankruptcyService.status(session, company.id)
        if status["requires_ack"]:
            raise ValueError("Сначала примите решение после банкротства")
        lot = await session.get(NatNextGameLiquidationLot, lot_id, with_for_update=True)
        if not lot or lot.status != "OPEN":
            raise ValueError("Этот лот уже продан")
        if lot.branch_id not in (company.branch_path or []):
            raise ValueError("Сначала откройте ветку этого предприятия")
        from backend.natbirzha.services.next_game_fusion_service import NextGameFusionService
        from backend.natbirzha.services.next_game_operations_effects import production_slots
        if await NextGameFusionService.consumed_branch(session, company.id, lot.branch_id):
            raise ValueError("Предприятие этой ветки входит в объединённый комплекс")
        if await session.scalar(select(NatNextGameFacility.id).where(
            NatNextGameFacility.company_id == company.id, NatNextGameFacility.branch_id == lot.branch_id)):
            raise ValueError("Предприятие этой ветки уже построено")
        from backend.natbirzha.services.next_game_operations_effects import used_production_slots
        count = await used_production_slots(session, company.id)
        if count >= await production_slots(session, company.id):
            raise ValueError("Недостаточно производственных мест; расширьте территорию")
        if company.cash + 1e-8 < lot.price:
            raise ValueError("Недостаточно cash для покупки")
        branch = find_next_game_branch(lot.branch_id)
        if not branch:
            raise ValueError("Ветка предприятия отсутствует")
        current = _utcnow()
        treasury = await Game._treasury(session)
        company.cash = round(company.cash - lot.price, 8)
        treasury.cash = round(treasury.cash + lot.price, 8)
        facility = NatNextGameFacility(company_id=company.id, branch_id=lot.branch_id, level=lot.level,
            next_cycle_at=current + timedelta(seconds=branch["factory"]["cycle_seconds"]))
        session.add(facility)
        lot.status, lot.buyer_company_id, lot.sold_at = "SOLD", company.id, current
        session.add(Game._ledger(company.id, "LIQUIDATION_FACTORY_BUY", -lot.price, lot.price,
            metadata={"lot_id": lot.id, "branch_id": lot.branch_id, "level": lot.level}))
        await session.flush()
        return {"success": True, "lot_id": lot.id, "facility_id": facility.id}
