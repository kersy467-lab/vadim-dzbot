import asyncio
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
import backend.natbirzha.models.next_game_bonds  # noqa: F401
from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameInventory, NatNextGameLedger
from backend.natbirzha.models.next_game_community import NatNextGameTransfer
from backend.natbirzha.models.next_game_partnerships import NatNextGameSupplyDeal, NatNextGameJointProject
from backend.natbirzha.services.next_game_partnership_service import NextGamePartnershipService as Service
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.services.next_game_market_service import NextGameMarketService as Market
from backend.natbirzha.next_game_catalog import find_next_game_branch

NOW = datetime(2026, 10, 10, 12)


async def setup(url="sqlite+aiosqlite:///:memory:"):
    engine = create_async_engine(url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        for id in [920001, 920002, 920003]:
            await Game.create_company(session, id, f"Company {id}")
        await session.commit()
    return engine, sessions


async def companies(session):
    return list((await session.scalars(select(NatNextGameCompany).order_by(NatNextGameCompany.id))).all())


def test_supply_escrow_permissions_batch_tail_and_audit_conserve_balances():
    async def check():
        engine, sessions = await setup()
        async with sessions() as session:
            buyer, seller, stranger = await companies(session)
            treasury = await Game._treasury(session)
            treasury_before = treasury.cash
            session.add(NatNextGameInventory(company_id=seller.id, item_id="water", quantity=103))
            offer = await Service.create_supply(session, buyer.owner_tg_id, seller.id, "water", 103, 2, 103, 3, NOW)
            row = await session.get(NatNextGameSupplyDeal, offer["id"])
            assert buyer.cash == 9794 and row.escrow_cash == 206 and seller.cash == 10000
            with pytest.raises(ValueError, match="партнёр"):
                await Service.respond(session, buyer.owner_tg_id, "supply", row.id, True, NOW)
            with pytest.raises(ValueError, match="не найден"):
                await Service.cancel(session, stranger.owner_tg_id, "supply", row.id)
            await Service.respond(session, seller.owner_tg_id, "supply", row.id, True, NOW)
            await Service.settle_all(session, NOW + timedelta(minutes=30))
            assert row.delivered == 0  # Water requires 100-unit batches.
            await Service.settle_all(session, NOW + timedelta(hours=1))
            assert row.delivered == 103 and row.status == "COMPLETED" and row.escrow_cash == 0
            assert seller.cash == 10206 and buyer.cash + seller.cash == 20000
            assert treasury.cash == treasury_before
            assert (await Game._inventory_row(session, buyer.id, "water")).quantity == 103
            assert (await Game._inventory_row(session, seller.id, "water")).quantity == 0
            audits = (await session.scalars(select(NatNextGameTransfer))).all()
            assert len(audits) == 2 and sum(row.cash for row in audits) == 206
            await Service.settle_all(session, NOW + timedelta(hours=2))
            assert seller.cash == 10206
            await session.commit()
        await engine.dispose()
    asyncio.run(check())


def test_supply_partial_expiry_and_cancel_return_only_unused_escrow():
    async def check():
        engine, sessions = await setup()
        async with sessions() as session:
            buyer, seller, _ = await companies(session)
            offer = await Service.create_supply(session, buyer.owner_tg_id, seller.id, "steel", 13, 2.3333, 13, 1, NOW)
            row = await session.get(NatNextGameSupplyDeal, offer["id"])
            session.add(NatNextGameInventory(company_id=seller.id, item_id="steel", quantity=7))
            await Service.respond(session, seller.owner_tg_id, "supply", row.id, True, NOW)
            await Service.settle_all(session, NOW + timedelta(hours=1))
            assert row.delivered == 5 and row.status == "EXPIRED" and row.escrow_cash == 0
            assert buyer.cash == 9988.33 and seller.cash == 10011.67
            total = buyer.cash + seller.cash
            await Service.cancel(session, buyer.owner_tg_id, "supply", row.id)
            assert buyer.cash + seller.cash == total == 20000
            pending = await Service.create_supply(session, buyer.owner_tg_id, seller.id, "steel", 1, 501, 1, 1, NOW)
            await Service.respond(session, seller.owner_tg_id, "supply", pending["id"], False)
            assert buyer.cash == 9988.33
            await session.commit()
        await engine.dispose()
    asyncio.run(check())


def test_project_acceptance_split_production_limits_and_no_refund_after_build():
    async def check():
        engine, sessions = await setup()
        async with sessions() as session:
            proposer, partner, stranger = await companies(session)
            proposer.branch_path = ["agriculture"]
            recipe = find_next_game_branch("agriculture")["factory"]
            treasury = await Game._treasury(session)
            initial_total = treasury.cash + proposer.cash + partner.cash
            offer = await Service.create_project(session, proposer.owner_tg_id, partner.id, "agriculture", NOW)
            row = await session.get(NatNextGameJointProject, offer["id"])
            await Service.respond(session, partner.owner_tg_id, "projects", row.id, True, NOW)
            assert treasury.cash + proposer.cash + partner.cash == initial_total
            money_after_build = proposer.cash
            await Service.respond(session, partner.owner_tg_id, "projects", row.id, True, NOW)
            assert proposer.cash == money_after_build
            for company in [proposer, partner]:
                for item_id, qty in recipe["inputs"].items():
                    await Game._change_inventory(session, company.id, item_id, qty / 2)
            due = NOW + timedelta(seconds=recipe["cycle_seconds"])
            await Service.settle_all(session, due)
            assert row.cycles_completed == 1
            for company in [proposer, partner]:
                assert (await Game._inventory_row(session, company.id, recipe["output_item"])).quantity == recipe["output_quantity"] / 2
            assert treasury.cash + proposer.cash + partner.cash == initial_total
            await Service.settle_all(session, due + timedelta(seconds=recipe["cycle_seconds"]))
            assert row.cycles_completed == 1 and row.blocked_reason
            second = await Service.create_project(session, proposer.owner_tg_id, partner.id, "agriculture", NOW)
            third = await Service.create_project(session, proposer.owner_tg_id, stranger.id, "agriculture", NOW)
            await Service.respond(session, partner.owner_tg_id, "projects", second["id"], True, NOW)
            with pytest.raises(ValueError, match="два"):
                await Service.respond(session, stranger.owner_tg_id, "projects", third["id"], True, NOW)
            await Service.cancel(session, stranger.owner_tg_id, "projects", third["id"])
            before = proposer.cash + partner.cash
            await Service.cancel(session, proposer.owner_tg_id, "projects", row.id)
            assert proposer.cash + partner.cash == before
            ledgers = (await session.scalars(select(NatNextGameLedger))).all()
            assert all(abs(row.cash_company_delta + row.cash_treasury_delta) < .01 for row in ledgers)
            await session.commit()
        await engine.dispose()
    asyncio.run(check())


def test_snapshot_lists_only_own_partnerships_and_project_cannot_use_locked_blueprint():
    async def check():
        engine, sessions = await setup()
        async with sessions() as session:
            buyer, seller, stranger = await companies(session)
            with pytest.raises(ValueError, match="чертёж"):
                await Service.create_project(session, buyer.owner_tg_id, seller.id, "agriculture")
            await Service.create_supply(session, buyer.owner_tg_id, seller.id, "steel", 5, 10, 5, 2, NOW)
            own = await Service.snapshot(session, seller.owner_tg_id, NOW)
            unrelated = await Service.snapshot(session, stranger.owner_tg_id, NOW)
            assert len(own["supplies"]) == 1 and own["supplies"][0]["can_accept"]
            assert unrelated["supplies"] == [] and unrelated["projects"] == []
        await engine.dispose()
    asyncio.run(check())


def test_concurrent_project_acceptance_enforces_two_active_and_replay_is_safe():
    async def check():
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False, dir=Path(__file__).parent) as file:
            database = Path(file.name)
        engine, sessions = await setup(f"sqlite+aiosqlite:///{database.as_posix()}")
        async with sessions() as session:
            proposer, partner, stranger = await companies(session)
            proposer.branch_path = ["agriculture"]
            treasury = await Game._treasury(session)
            treasury_before = treasury.cash
            cost = find_next_game_branch("agriculture")["factory"]["build_cost"]
            offers = [await Service.create_project(session, proposer.owner_tg_id, partner.id, "agriculture", NOW)
                      for _ in range(3)]
            partner_tg = partner.owner_tg_id
            await session.commit()
        async def accept(id):
            async with sessions() as session:
                try:
                    result = await Service.respond(session, partner_tg, "projects", id, True, NOW)
                    await session.commit()
                    return result
                except ValueError as exc:
                    await session.rollback()
                    return str(exc)
        results = await asyncio.gather(*(accept(row["id"]) for row in offers))
        assert sum(isinstance(result, dict) for result in results) == 2
        assert any("два" in result for result in results if isinstance(result, str))
        async with sessions() as session:
            rows = (await session.scalars(select(NatNextGameJointProject))).all()
            active = [row for row in rows if row.status == "ACTIVE"]
            assert len(active) == 2
            treasury = await Game._treasury(session)
            assert treasury.cash == treasury_before + 2 * cost
            treasury_after = treasury.cash
            replay_id = active[0].id
        await asyncio.gather(accept(replay_id), accept(replay_id))
        async with sessions() as session:
            treasury = await Game._treasury(session)
            assert treasury.cash == treasury_after
        await engine.dispose()
        database.unlink()
    asyncio.run(check())


def test_supply_never_consumes_sell_escrow_and_respects_buyer_reserved_capacity():
    async def check():
        engine, sessions = await setup()
        async with sessions() as session:
            buyer, seller, _ = await companies(session)
            await Game._change_inventory(session, seller.id, "steel", 15)
            await Game._change_inventory(session, buyer.id, "steel", 99995)
            await Market.create_limit_order(session, seller.owner_tg_id, "steel", "SELL", 10, 1000)
            await Market.create_limit_order(session, buyer.owner_tg_id, "steel", "SELL", 10, 1000)
            offer = await Service.create_supply(session, buyer.owner_tg_id, seller.id, "steel", 10, 2, 10, 2, NOW)
            row = await session.get(NatNextGameSupplyDeal, offer["id"])
            await Service.respond(session, seller.owner_tg_id, "supply", row.id, True, NOW)
            await Service.settle_all(session, NOW + timedelta(hours=1))
            assert row.delivered == 5
            assert (await Game._inventory_row(session, seller.id, "steel")).quantity == 0
            assert await Market.reserved_sell_quantity(session, seller.id, "steel") == 10
            buyer_inventory = await Game._inventory_row(session, buyer.id, "steel")
            assert buyer_inventory.quantity + await Market.reserved_sell_quantity(session, buyer.id, "steel") == 100000
            await Game._change_inventory(session, seller.id, "steel", 5)
            await Service.settle_all(session, NOW + timedelta(hours=1, minutes=30))
            assert row.delivered == 5 and row.blocked_reason == "Склад покупателя заполнен"
            assert (await Game._inventory_row(session, seller.id, "steel")).quantity == 5
            await Service.cancel(session, buyer.owner_tg_id, "supply", row.id)
            assert buyer.cash + seller.cash == 20000
            await session.commit()
        await engine.dispose()
    asyncio.run(check())
