import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.db.models import Base
import backend.natbirzha.models
from backend.natbirzha.models.next_game import (
    NatNextGameCompany, NatNextGameFacility, NatNextGameInventory, NatNextGameDeposit, NatNextGameLoan,
)
from backend.natbirzha.models.next_game_equity import NatNextGameShareIssue, NatNextGameShareHolding, NatNextGameShareOrder
from backend.natbirzha.models.next_game_finance import NatNextGameFinanceContract
from backend.natbirzha.models.next_game_community import NatNextGameProfile
from backend.natbirzha.models.next_game_progression import NatNextGameMerger
from backend.natbirzha.models.next_game_partnerships import NatNextGameJointProject
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.services.next_game_progression_service import NextGameProgressionService as Progression
from backend.natbirzha.services.next_game_fusion_service import NextGameFusionService as Fusion
from backend.natbirzha.services.next_game_community_service import profile
from backend.natbirzha.services.next_game_equity_service import NextGameEquityService as Equity
from backend.natbirzha.services.next_game_rebirth_assets import reserve_company, sweep_reserve_income


@asynccontextmanager
async def database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        await Game.create_company(session, 910001, "Первый холдинг")
        await Game.create_company(session, 910002, "Инвестор")
        yield session
    await engine.dispose()


async def terminal(session):
    company = await Game._owned_company(session, 910001)
    company.sector_id, company.branch_path, company.level, company.xp = "energy", ["power_exchange"], 60, 60000
    facility = NatNextGameFacility(company_id=company.id, branch_id="power_exchange", level=1,
        next_cycle_at=datetime.utcnow() + timedelta(days=1))
    session.add(facility)
    await session.flush()
    return company


async def cash_total(session):
    await session.flush()
    treasury = await Game._treasury(session)
    cash = await session.scalar(select(func.sum(NatNextGameCompany.cash)))
    return float(cash) + treasury.cash


def test_pvc_charges_real_balance_and_mastery_uses_post60_xp():
    async def check():
        async with database() as session:
            company = await Game._owned_company(session, 910001)
            row = await profile(session, company.id)
            with pytest.raises(ValueError, match="25 PVC"):
                await Progression.upgrade_pvc(session, 910001)
            assert row.pvc_balance == 0 and row.pvc_level == 0
            row.pvc_balance = 200
            await Progression.upgrade_pvc(session, 910001)
            assert row.pvc_balance == 175 and row.pvc_level == 1
            await Progression.upgrade_pvc(session, 910001)
            assert row.pvc_balance == 75 and row.pvc_level == 2
            with pytest.raises(ValueError, match="225 PVC"):
                await Progression.upgrade_pvc(session, 910001)
            company.level, company.xp, row.rebirths = 60, 60000, 1
            assert await Progression.production_bonus(session, company) == pytest.approx(1.25 * 1.10 * 1.01)
            company.xp = 59000
            assert await Progression.production_bonus(session, company) == pytest.approx(1.25 * 1.10)
    asyncio.run(check())


def test_fusion_consumes_sources_once_and_restores_original_levels():
    async def check():
        async with database() as session:
            company = await Game._owned_company(session, 910001)
            company.branch_path = ["thermal", "renewables"]
            sources = [NatNextGameFacility(company_id=company.id, branch_id=branch, level=5,
                next_cycle_at=datetime.utcnow() + timedelta(days=1)) for branch in company.branch_path]
            session.add_all(sources)
            await session.flush()
            before = await cash_total(session)
            result = await Fusion.fuse(session, 910001, [row.id for row in sources])
            facilities = (await session.scalars(select(NatNextGameFacility).where(
                NatNextGameFacility.company_id == company.id))).all()
            assert len(facilities) == 1
            assert await Fusion.consumed_branch(session, company.id, "renewables")
            recipe = await Fusion.facility_recipe(session, facilities[0], {})
            assert recipe["output_quantity"] == pytest.approx((16 * 2 + 9 * 2) * 1.25)
            assert recipe["inputs"] == {"coal": 2, "water": 1}
            assert recipe["operating_cost"] == 55
            assert await cash_total(session) == pytest.approx(before)
            await Fusion.dissolve(session, 910001, result["merger_id"])
            restored = (await session.scalars(select(NatNextGameFacility).where(
                NatNextGameFacility.company_id == company.id))).all()
            assert {(row.branch_id, row.level) for row in restored} == {("thermal", 5), ("renewables", 5)}
            assert not await Fusion.consumed_branch(session, company.id, "renewables")
            assert all(row.next_cycle_at > datetime.utcnow() for row in restored)
            with pytest.raises(ValueError, match="не найдено"):
                await Fusion.dissolve(session, 910001, result["merger_id"])
    asyncio.run(check())


def test_rebirth_redeems_deposit_repays_loan_preserves_issuer_and_conserves_cash():
    async def check():
        async with database() as session:
            company = await terminal(session)
            investor = await Game._owned_company(session, 910002)
            await Game.open_bank_deposit(session, 910001, 2000, 1)
            await Game.request_bank_loan(session, 910001, 1000)
            ipo = await Equity.open_ipo(session, 910001)
            issue = await session.get(NatNextGameShareIssue, ipo["issue"]["id"])
            original_price = issue.last_price
            self_holding = await session.scalar(select(NatNextGameShareHolding).where(
                NatNextGameShareHolding.company_id == company.id))
            self_holding.shares -= 100
            session.add(NatNextGameShareHolding(issue_id=issue.id, company_id=investor.id,
                shares=100, average_price=original_price))
            await Game._change_inventory(session, company.id, "coal", 15)
            settings = await profile(session, company.id)
            settings.pvc_balance, settings.pvc_level = 123, 2
            await session.commit()
            before = await cash_total(session)
            stock_before = (await Game._treasury(session)).inventory_json.get("coal", 0)
            result = await Progression.rebirth(session, 910001, confirm=True)
            assert result["rebirths"] == 1
            assert company.cash == 10000 and company.xp == 0 and company.level == 1
            assert company.branch_path == [] and company.sector_id is None
            assert settings.pvc_balance == 123 and settings.pvc_level == 2
            assert await cash_total(session) == pytest.approx(before)
            assert (await Game._treasury(session)).inventory_json["coal"] == stock_before + 15
            assert await session.scalar(select(func.count(NatNextGameFacility.id)).where(
                NatNextGameFacility.company_id == company.id)) == 0
            assert (await session.scalar(select(NatNextGameDeposit))).status == "WITHDRAWN"
            assert (await session.scalar(select(NatNextGameLoan))).status == "PAID"
            assert issue.last_price == pytest.approx(original_price * .01)
            holding = await session.scalar(select(NatNextGameShareHolding).where(
                NatNextGameShareHolding.company_id == investor.id))
            assert holding.shares == 100 and holding.issue_id == issue.id
            assert not (await session.scalars(select(NatNextGameShareOrder).where(
                NatNextGameShareOrder.status == "OPEN"))).all()
    asyncio.run(check())


def test_rebirth_transfers_creditor_claim_without_destroying_debt_or_creating_money():
    async def check():
        async with database() as session:
            company = await terminal(session)
            borrower = await Game._owned_company(session, 910002)
            current = datetime.utcnow()
            contract = NatNextGameFinanceContract(lender_company_id=company.id,
                borrower_company_id=borrower.id, principal=1000, daily_rate_bps=100,
                term_days=1, maturity_amount=1010, status="ACTIVE", offer_key="testclaim",
                accepted_at=current, due_at=current + timedelta(days=1))
            session.add(contract)
            company.cash -= 1000
            borrower.cash += 1000
            await session.commit()
            before = await cash_total(session)
            await Progression.rebirth(session, 910001, confirm=True)
            reserve = await reserve_company(session)
            assert contract.lender_company_id == reserve.id
            assert contract.borrower_company_id == borrower.id and contract.status == "ACTIVE"
            assert reserve.owner_tg_id == -1 and reserve.cash == 0
            assert await cash_total(session) == pytest.approx(before)
            from backend.natbirzha.services.next_game_finance_service import NextGameFinanceContractService
            await NextGameFinanceContractService.repay_loan(session, 910002, contract.id, idempotency_key="repay")
            assert reserve.cash == 1010 and company.cash == 10000
            await sweep_reserve_income(session)
            assert reserve.cash == 0 and await cash_total(session) == pytest.approx(before)
    asyncio.run(check())


def test_failed_rebirth_rolls_back_redemption_and_keeps_all_old_assets():
    async def check():
        async with database() as session:
            company = await terminal(session)
            await Game.open_bank_deposit(session, 910001, 2000, 1)
            await Game.request_bank_loan(session, 910001, 10000)
            # Model a real expense paid into the treasury, leaving debt insolvent.
            treasury = await Game._treasury(session)
            treasury.cash += company.cash
            company.cash = 0
            await session.commit()
            before = await cash_total(session)
            with pytest.raises(ValueError, match="погашения"):
                await Progression.rebirth(session, 910001, confirm=True)
            await session.refresh(company)
            deposit = await session.scalar(select(NatNextGameDeposit))
            loan = await session.scalar(select(NatNextGameLoan))
            assert deposit.status == "ACTIVE" and loan.status == "ACTIVE"
            assert company.branch_path == ["power_exchange"] and company.cash == 0
            assert await cash_total(session) == pytest.approx(before)
            assert await session.scalar(select(func.count(NatNextGameFacility.id))) == 1
    asyncio.run(check())


def test_unread_matured_bonds_and_listings_never_pay_after_rebirth():
    async def check():
        from backend.natbirzha.services.next_game_bond_service import NextGameBondService as Bonds
        from backend.natbirzha.models.next_game_bonds import NatNextGameBondHolding, NatNextGameBondListing
        async with database() as session:
            company = await terminal(session)
            old = datetime.utcnow() - timedelta(days=10)
            result = await Bonds.buy(session, 910001, 1, 10, now=old)
            holding = await session.get(NatNextGameBondHolding, result["holding_id"])
            # A listing saved before maturity; no screen has settled this lot yet.
            listing = NatNextGameBondListing(holding_id=holding.id, seller_company_id=company.id,
                units=5, unit_price=100, status="OPEN", created_at=old)
            session.add(listing)
            await session.commit()
            before = await cash_total(session)
            await Progression.rebirth(session, 910001, confirm=True)
            assert holding.status == "FORFEITED" and listing.status == "FORFEITED"
            assert holding.coupon_paid == 0
            await Bonds.settle_all(session, now=datetime.utcnow() + timedelta(days=40))
            assert company.cash == 10000 and holding.coupon_paid == 0
            assert await cash_total(session) == pytest.approx(before)
    asyncio.run(check())


def test_joint_ownership_blocks_reset_and_preserves_partner_interest():
    async def check():
        async with database() as session:
            company = await terminal(session)
            partner = await Game._owned_company(session, 910002)
            project = NatNextGameJointProject(proposer_company_id=company.id, partner_company_id=partner.id,
                branch_id="thermal", recipe_json={}, build_cost=1000, escrow_cash=0, status="ACTIVE",
                next_cycle_at=datetime.utcnow() + timedelta(days=1))
            session.add(project)
            await session.commit()
            before = await cash_total(session)
            with pytest.raises(ValueError, match="совместного"):
                await Progression.rebirth(session, 910001, confirm=True)
            await session.refresh(company)
            assert project.status == "ACTIVE" and company.branch_path == ["power_exchange"]
            assert await cash_total(session) == pytest.approx(before)
    asyncio.run(check())


def test_foreign_share_ownership_goes_to_reserve_and_old_issuer_buy_reserves_refund():
    async def check():
        async with database() as session:
            company = await terminal(session)
            investor = await Game._owned_company(session, 910002)
            own_ipo = await Equity.open_ipo(session, 910001)
            own = await session.get(NatNextGameShareIssue, own_ipo["issue"]["id"])
            other = NatNextGameShareIssue(company_id=investor.id, total_shares=100000, float_shares=10000,
                initial_price=1, last_price=1, status="ACTIVE")
            session.add(other)
            await session.flush()
            session.add(NatNextGameShareHolding(issue_id=other.id, company_id=company.id,
                shares=100, average_price=1))
            # Existing investor cash is placed in an unmatched bid for the old IPO.
            investor.cash -= 250
            session.add(NatNextGameShareOrder(issue_id=own.id, company_id=investor.id, side="BUY",
                limit_price=.25, quantity=1000, remaining_shares=1000, reserved_cash=250, status="OPEN"))
            await session.commit()
            before = await cash_total(session) + 250
            result = await Progression.rebirth(session, 910001, confirm=True)
            reserve = await reserve_company(session)
            holding = await session.scalar(select(NatNextGameShareHolding).where(
                NatNextGameShareHolding.issue_id == other.id))
            assert holding.company_id == reserve.id and holding.shares == 100
            assert result["transferred_assets"]["share_holdings"] == 1
            assert investor.cash == 10000
            assert await cash_total(session) == pytest.approx(before)
    asyncio.run(check())
