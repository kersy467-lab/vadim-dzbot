import asyncio
from datetime import datetime, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.db.models import Base
import backend.natbirzha.models
import backend.natbirzha.models.next_game_operations
from backend.natbirzha.models.next_game import (
    NatNextGameCompany as Company, NatNextGameTreasury as Treasury, NatNextGameFacility as Facility,
    NatNextGameInventory as Inventory, NatNextGameLoan as Loan, NatNextGameDeposit as Deposit,
    NatNextGameLedger as Ledger, NatNextGameMarketOrder as Order,
)
from backend.natbirzha.models.next_game_equity import NatNextGameShareIssue as Issue, NatNextGameShareHolding as Holding
from backend.natbirzha.models.next_game_finance import NatNextGameFinanceContract as Finance
from backend.natbirzha.models.next_game_banking import NatNextGameCorporateLoan as Corporate
from backend.natbirzha.models.next_game_advance import NatNextGameMarketAdvance as Advance
from backend.natbirzha.models.next_game_civic import NatNextGameTaxAssessment as Tax
from backend.natbirzha.models.next_game_bankruptcy import NatNextGameLiquidationLot as Lot
from backend.natbirzha.services.next_game_bankruptcy_service import NextGameBankruptcyService as Bankruptcy
from backend.natbirzha.services.next_game_bankruptcy_debts import writeoff_status
from backend.natbirzha.services.next_game_civic_service import NextGameCivicService as Civic


async def database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def test_forced_bankruptcy_preserves_external_rights_moves_claims_and_does_not_pay_creditors():
    async def run():
        engine, sessions = await database()
        async with sessions() as session:
            now = datetime(2026, 10, 10, 12)
            target = Company(owner_tg_id=601, name="Fail", sector_id="bank", branch_path=["retail"],
                cash=50.00001234, level=9, xp=8000, created_at=now - timedelta(hours=1))
            peer = Company(owner_tg_id=602, name="Investor", cash=5000, created_at=now)
            treasury = Treasury(id=1, cash=1000000, inventory_json={})
            session.add_all([target, peer, treasury]); await session.flush()
            own = Issue(company_id=target.id, total_shares=100000, float_shares=10000, initial_price=100, last_price=100)
            foreign = Issue(company_id=peer.id, total_shares=100000, float_shares=10000, initial_price=10, last_price=10)
            session.add_all([own, foreign]); await session.flush()
            investor = Holding(company_id=peer.id, issue_id=own.id, shares=10000, average_price=100)
            session.add_all([investor, Holding(company_id=target.id, issue_id=own.id, shares=90000, average_price=0),
                Holding(company_id=target.id, issue_id=foreign.id, shares=10, average_price=10),
                Inventory(company_id=target.id, item_id="coal", quantity=3),
                Facility(company_id=target.id, branch_id="retail", level=3, next_cycle_at=now + timedelta(hours=1)),
                Ledger(company_id=target.id, action="SELL", cash_company_delta=100, cash_treasury_delta=-100,
                       created_at=now - timedelta(minutes=30))])
            bank_debt = Loan(company_id=target.id, principal=1000, due_at=now + timedelta(days=1))
            corporate_debt = Corporate(bank_company_id=peer.id, borrower_company_id=target.id, principal=1000,
                daily_rate=.01, term_days=2, maturity_amount=1020, idempotency_key="debt", issued_at=now, due_at=now + timedelta(days=2))
            direct_debt = Finance(lender_company_id=peer.id, borrower_company_id=target.id, principal=1000,
                daily_rate_bps=10, term_days=2, maturity_amount=1002, status="ACTIVE", offer_key="debt",
                accepted_at=now, due_at=now + timedelta(days=2))
            bank_claim = Corporate(bank_company_id=target.id, borrower_company_id=peer.id, principal=1000,
                daily_rate=.01, term_days=2, maturity_amount=1020, idempotency_key="claim", issued_at=now, due_at=now + timedelta(days=2))
            direct_claim = Finance(lender_company_id=target.id, borrower_company_id=peer.id, principal=1000,
                daily_rate_bps=10, term_days=2, maturity_amount=1002, status="ACTIVE", offer_key="claim",
                accepted_at=now, due_at=now + timedelta(days=2))
            deposit = Deposit(company_id=target.id, principal=1000, maturity_amount=1010, term_days=2,
                daily_rate=.005, opened_at=now, matures_at=now + timedelta(days=2))
            buy = Order(company_id=target.id, item_id="coal", side="BUY", limit_price=1, quantity=50,
                remaining_quantity=50, reserved_cash=50)
            sell = Order(company_id=target.id, item_id="coal", side="SELL", limit_price=2, quantity=5,
                remaining_quantity=5, reserved_cash=0)
            session.add_all([bank_debt, corporate_debt, direct_debt, bank_claim, direct_claim, deposit, buy, sell])
            await session.flush()
            advance = Advance(company_id=target.id, order_id=sell.id, advance_paid=10, outstanding_amount=10, reference_price=2)
            session.add(advance); await session.flush()
            result = await Bankruptcy.force(session, target.id, "Проверка ликвидации", 601, now)
            assert result["factory_lots"] == 1 and target.cash == 0
            assert treasury.cash == pytest.approx(1000100.00001234)
            assert peer.cash == 5000  # no fake repayment or principal restoration
            assert bank_debt.status == corporate_debt.status == direct_debt.status == "PAID"
            assert corporate_debt.repaid_amount == direct_debt.repaid_amount == 0
            assert await writeoff_status(session, "BANK_LOAN", bank_debt.id) == "WRITTEN_OFF"
            assert advance.outstanding_amount == 0 and buy.status == sell.status == "CANCELLED"
            assert treasury.inventory_json["coal"] == 8
            assert own.company_id == target.id and own.last_price == 1
            assert investor.company_id == peer.id and investor.shares == 10000
            reserve = await session.scalar(select(Company).where(Company.owner_tg_id == -1))
            assert bank_claim.bank_company_id == direct_claim.lender_company_id == reserve.id
            foreign_holding = await session.scalar(select(Holding).where(Holding.issue_id == foreign.id, Holding.company_id == reserve.id))
            assert foreign_holding.shares == 10 and deposit.status == "WITHDRAWN"
            assert not (await session.scalars(select(Facility).where(Facility.company_id == target.id))).all()
            tax = await session.scalar(select(Tax).where(Tax.company_id == target.id, Tax.amount > 0))
            assert tax.status == "FORGIVEN"
            with pytest.raises(ValueError):
                await Civic.pay_tax(session, 601, tax.id)
            from backend.natbirzha.services.next_game_banking_service import NextGameBankingService
            from backend.natbirzha.services.next_game_finance_service import NextGameFinanceContractService
            bank_view = await NextGameBankingService.snapshot(session, peer)
            direct_view = await NextGameFinanceContractService.snapshot(session, peer)
            closed = next(row for row in bank_view["loans"] if row["id"] == corporate_debt.id)
            direct_closed = next(row for row in direct_view["contracts"] if row["id"] == direct_debt.id)
            assert closed["status"] == direct_closed["status"] == "WRITTEN_OFF"
            assert closed["due_amount"] == direct_closed["due_amount"] == 0
            assert closed["paid_amount"] == direct_closed["paid_amount"] == 0
            assert bank_view["bank_summary"]["loan_interest_income"] == 0
            await Bankruptcy.recover(session, 601, False)
            with pytest.raises(ValueError, match="закрыто"):
                await Civic.pay_tax(session, 601, tax.id)
        await engine.dispose()
    asyncio.run(run())


def test_recovery_once_and_liquidation_sale_guards_conserve_money():
    async def run():
        engine, sessions = await database()
        async with sessions() as session:
            now = datetime(2026, 10, 10, 12)
            target = Company(owner_tg_id=603, name="Fail", sector_id="bank", branch_path=["retail"], cash=123,
                level=7, xp=6000, created_at=now)
            buyer = Company(owner_tg_id=604, name="Buyer", cash=200000, branch_path=[], created_at=now)
            treasury = Treasury(id=1, cash=1000000, inventory_json={})
            session.add_all([target, buyer, treasury]); await session.flush()
            session.add(Facility(company_id=target.id, branch_id="retail", level=3, next_cycle_at=now))
            await session.flush()
            await Bankruptcy.force(session, target.id, "Явная проверка", 603, now)
            with pytest.raises(ValueError):
                await Bankruptcy.force(session, target.id, "Повторная проверка", 603, now)
            await Bankruptcy.recover(session, 603, True)
            first_cash = target.cash
            await Bankruptcy.recover(session, 603, True)
            assert target.cash == first_cash == 100000
            assert target.sector_id is None and target.branch_path == [] and target.level == 1 and target.xp == 0
            assert treasury.cash == 900123
            with pytest.raises(ValueError):
                await Bankruptcy.recover(session, 603, False)
            lot = await session.scalar(select(Lot))
            with pytest.raises(ValueError):
                await Bankruptcy.buy_lot(session, 604, lot.id)
            buyer.branch_path = ["retail"]; await session.flush()
            cash_before = treasury.cash + buyer.cash
            await Bankruptcy.buy_lot(session, 604, lot.id)
            assert treasury.cash + buyer.cash == cash_before
            assert target.cash == 100000  # seller never receives liquidation proceeds
            acquired = await session.scalar(select(Facility).where(Facility.company_id == buyer.id))
            assert acquired.level == 3 and lot.status == "SOLD"
            with pytest.raises(ValueError):
                await Bankruptcy.buy_lot(session, 604, lot.id)
            duplicate = Lot(source_company_id=target.id, bankruptcy_sequence=1, branch_id="retail", level=2,
                price=1000, status="OPEN", listed_at=now)
            session.add(duplicate); await session.flush()
            with pytest.raises(ValueError, match="уже построено"):
                await Bankruptcy.buy_lot(session, 604, duplicate.id)
        await engine.dispose()
    asyncio.run(run())


def test_recovery_reserve_shortfall_and_continue_preserve_profile_and_partner_outputs():
    async def run():
        from backend.natbirzha.models.next_game_community import NatNextGameProfile
        from backend.natbirzha.models.next_game_partnerships import NatNextGameSupplyDeal, NatNextGameJointProject
        engine, sessions = await database()
        async with sessions() as session:
            now = datetime(2026, 10, 10, 12)
            target = Company(owner_tg_id=605, name="Fail", sector_id="bank", branch_path=["retail"], cash=0,
                level=7, xp=6000, created_at=now)
            peer = Company(owner_tg_id=606, name="Partner", cash=1000, created_at=now)
            treasury = Treasury(id=1, cash=99000, inventory_json={})
            session.add_all([target, peer, treasury]); await session.flush()
            profile = NatNextGameProfile(company_id=target.id, rebirths=5, pvc_balance=500, pvc_level=2)
            partner_inventory = Inventory(company_id=peer.id, item_id="coal", quantity=11)
            supply = NatNextGameSupplyDeal(buyer_company_id=peer.id, seller_company_id=target.id,
                item_id="coal", quantity=10, delivered=0, unit_price=40, rate_per_hour=1, duration_hours=10,
                escrow_cash=400, status="ACTIVE", offered_at=now, accepted_at=now, ends_at=now + timedelta(hours=10))
            joint = NatNextGameJointProject(proposer_company_id=target.id, partner_company_id=peer.id,
                branch_id="retail", recipe_json={}, build_cost=1000, escrow_cash=0, status="ACTIVE", offered_at=now,
                accepted_at=now, next_cycle_at=now + timedelta(days=1))
            session.add_all([profile, partner_inventory, supply, joint]); await session.flush()
            await Bankruptcy.force(session, target.id, "Проверка договора", 605, now)
            assert peer.cash == 1400 and partner_inventory.quantity == 11
            assert joint.status == supply.status == "CANCELLED" and supply.escrow_cash == 0
            with pytest.raises(ValueError):
                await Bankruptcy.recover(session, 605, True)
            await session.refresh(target)
            await session.refresh(treasury)
            assert (await Bankruptcy.status(session, target.id))["requires_ack"]
            assert profile.pvc_balance == 500 and profile.rebirths == 5
            await Bankruptcy.recover(session, 605, False)
            await Bankruptcy.recover(session, 605, False)
            assert treasury.cash == 99000 and target.cash == 0
            assert target.level == 7 and target.branch_path == ["retail"]
        await engine.dispose()
    asyncio.run(run())


def test_scheduler_skips_pending_company_and_backend_gate_blocks_mutations(monkeypatch):
    async def run():
        from backend.bot.services import next_game_scheduler
        from backend.natbirzha.models.next_game_bankruptcy import NatNextGameBankruptcy
        from backend.natbirzha.services.next_game_service import NextGameService
        from backend.natbirzha.api.next_game_routes import get_map
        from types import SimpleNamespace
        engine, sessions = await database()
        async with sessions() as session:
            now = datetime(2026, 10, 10, 12)
            pending = Company(owner_tg_id=607, name="Pending", cash=0, created_at=now)
            active = Company(owner_tg_id=608, name="Active", cash=1000, created_at=now)
            session.add_all([pending, active, Treasury(id=1, cash=1000000, inventory_json={})]); await session.flush()
            session.add(NatNextGameBankruptcy(company_id=pending.id, requires_ack=True, was_triggered=True,
                sequence=1, note="Проверка блокировки", creator_tg_id=607, triggered_at=now))
            await session.commit()
            with pytest.raises(ValueError, match="банкротства"):
                await NextGameService.select_sector(session, 607, "bank")
            state = await get_map(section="full", admin=SimpleNamespace(tg_id=607), session=session)
            assert state["recovery"]["requires_ack"] and state["company"]["cash"] == 0
        calls = []
        real_settle = NextGameService.settle_company
        async def tracked(session, owner, **kwargs):
            calls.append(owner)
            return await real_settle(session, owner, **kwargs)
        monkeypatch.setattr(NextGameService, "settle_company", tracked)
        await next_game_scheduler.settle_preview_world(session_factory=sessions)
        assert 607 not in calls and 608 in calls
        await engine.dispose()
    asyncio.run(run())


def test_bankruptcy_and_recovery_request_replays_cannot_repeat_the_grant():
    async def run():
        from types import SimpleNamespace
        from backend.natbirzha.api.next_game_mutation import mutate
        engine, sessions = await database()
        async with sessions() as session:
            now = datetime(2026, 10, 10, 12)
            target = Company(owner_tg_id=609, name="Replay", cash=123, created_at=now)
            treasury = Treasury(id=1, cash=1000000, inventory_json={})
            session.add_all([target, treasury]); await session.commit()
            admin = SimpleNamespace(id=609)
            target_id = target.id
            action = lambda: Bankruptcy.force(session, target_id, "Проверка повторов", 609, now)
            first = await mutate(session, admin, "force-1", "/admin/bankruptcy", {"id": target_id}, action)
            assert await mutate(session, admin, "force-1", "/admin/bankruptcy", {"id": target_id}, action) == first
            recovery = lambda: Bankruptcy.recover(session, 609, True)
            first = await mutate(session, admin, "recovery-1", "/recovery", {"restart": True}, recovery)
            assert await mutate(session, admin, "recovery-1", "/recovery", {"restart": True}, recovery) == first
            await mutate(session, admin, "recovery-2", "/recovery", {"restart": True}, recovery)
            await session.refresh(target); await session.refresh(treasury)
            assert target.cash == 100000 and treasury.cash == 900123
            assert len((await session.scalars(select(Ledger).where(Ledger.action == "BANKRUPTCY_RESTART"))).all()) == 1
        await engine.dispose()
    asyncio.run(run())
