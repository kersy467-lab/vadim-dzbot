"""Hybrid creation/sale must preserve ownership, global capacity and capital."""

import asyncio
from collections import Counter

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import CAREER_BUSINESSES, INDUSTRIES, get_business_spec
from backend.natbirzha.api.hybrid_routes import hybrid_catalog
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, NatInventory
from backend.natbirzha.models.hybrid_mergers import NatHybridMerger
from backend.natbirzha.services.hybrid_merger_service import (
    HYBRID_RECIPES,
    HybridMergerService,
)
from backend.natbirzha.services.business_service import BusinessService
from backend.natbirzha.services.empire_summary_service import EmpireSummaryService


MINER_SOURCE_TYPES = ("coal_open_pit", "iron_quarry")


async def _fixture(company_count: int = 1):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessions() as session:
        users = [
            User(tg_id=992000 + index, full_name=f"Hybrid Player {index}")
            for index in range(company_count)
        ]
        session.add_all(users)
        await session.flush()
        companies = [
            NatCompany(
                user_id=user.id,
                name=f"Hybrid Company {index}",
                specialization="miner",
                cash=1_000_000.0,
            )
            for index, user in enumerate(users)
        ]
        session.add_all(companies)
        await session.flush()
        for company in companies:
            for business_type in MINER_SOURCE_TYPES:
                session.add(
                    NatBusiness(
                        company_id=company.id,
                        business_type=business_type,
                        specialization="miner",
                        stage=1,
                        status="ACTIVE",
                        capital_invested=1_000.0,
                    )
                )
        await session.flush()
        recipe = HYBRID_RECIPES["hybrid_miner"]
        for company in companies:
            for item_id, quantity in recipe["resource_requirements"].items():
                session.add(
                    NatInventory(
                        company_id=company.id,
                        item_id=item_id,
                        quantity=float(quantity) * 10,
                        reserved_quantity=0.0,
                        avg_cost_basis=1.0,
                    )
                )
        await session.commit()
        company_ids = [company.id for company in companies]
    return engine, sessions, company_ids


def test_server_owned_hybrid_recipes_cover_every_active_industry() -> None:
    assert {recipe["specialization"] for recipe in HYBRID_RECIPES.values()} == set(INDUSTRIES)
    assert Counter(recipe["specialization"] for recipe in HYBRID_RECIPES.values()) == {
        specialization: 3 for specialization in INDUSTRIES
    }
    for recipe in HYBRID_RECIPES.values():
        first, second = recipe["source_business_types"]
        assert first != second
        assert all(
            business_type in CAREER_BUSINESSES
            and CAREER_BUSINESSES[business_type]["specialization"] == recipe["specialization"]
            for business_type in (first, second)
        )
        assert all(quantity > 0 for quantity in recipe["resource_requirements"].values())


def test_each_hybrid_has_a_four_level_upgrade_cap() -> None:
    for recipe in HYBRID_RECIPES.values():
        spec = get_business_spec(recipe["business_type"])
        assert recipe["max_stage"] == 4
        assert spec is not None and spec["max_stage"] == 4


def test_each_hybrid_has_a_balanced_resource_production_spec() -> None:
    assert {recipe["specialization"] for recipe in HYBRID_RECIPES.values()} == set(INDUSTRIES)
    for recipe in HYBRID_RECIPES.values():
        spec = get_business_spec(recipe["business_type"])
        assert spec is not None
        assert spec["hybrid_only"] is True
        assert spec["mechanic"] == "resource_production"
        assert spec["inputs_per_hour"]
        assert spec["outputs_per_hour"]
        assert 1 in spec["stage_rates"]
        assert all(
            item_id in CANONICAL_ITEMS
            for item_id in (*spec["inputs_per_hour"], *spec["outputs_per_hour"])
        )
        assert spec["slot_weight"] == 1
        assert recipe["input_reduction_ratio"] > 0
        assert recipe["output_bonus_ratio"] > 0


def test_hybrid_catalog_shows_upgrade_target_level() -> None:
    async def check() -> None:
        engine, sessions, company_ids = await _fixture()
        try:
            async with sessions() as session:
                company = await session.get(NatCompany, company_ids[0])
                source = await session.scalar(select(NatBusiness).where(
                    NatBusiness.company_id == company_ids[0],
                    NatBusiness.business_type == "coal_open_pit",
                ))
                source.status = "UPGRADING"
                source.stage = 25
                source.upgrade_target_stage = 26
                data = await hybrid_catalog(company, session)
                assert "active_hybrid_limit" not in data
                recipe = next(item for item in data["recipes"] if item["id"] == "hybrid_miner")
                assert recipe["max_stage"] == 4
                row = next(item for item in data["businesses"] if item["id"] == source.id)
                assert row["stage"] == 25
                assert row["target_stage"] == 26
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_hybrid_creation_has_no_server_wide_limit() -> None:
    async def check() -> None:
        engine, sessions, company_ids = await _fixture(6)
        try:
            async with sessions() as session:
                for company_id in company_ids:
                    source_ids = await _source_ids(company_id, session)
                    await HybridMergerService.open_hybrid(
                        session, company_id, "hybrid_miner", *source_ids
                    )
                await session.flush()
                active_count = await session.scalar(
                    select(func.count(NatHybridMerger.id)).where(NatHybridMerger.status == "ACTIVE")
                )
                assert active_count == len(company_ids)
        finally:
            await engine.dispose()

    asyncio.run(check())


async def _source_ids(company_id: int, session) -> tuple[int, int]:
    rows = (
        await session.execute(
            select(NatBusiness)
            .where(
                NatBusiness.company_id == company_id,
                NatBusiness.business_type.in_(MINER_SOURCE_TYPES),
            )
            .order_by(NatBusiness.business_type)
        )
    ).scalars().all()
    by_type = {row.business_type: row.id for row in rows}
    return tuple(by_type[business_type] for business_type in MINER_SOURCE_TYPES)


def test_hybrid_rejects_source_business_owned_by_another_company() -> None:
    async def check() -> None:
        engine, sessions, company_ids = await _fixture(2)
        try:
            async with sessions() as session:
                foreign_sources = await _source_ids(company_ids[0], session)
                with pytest.raises(ValueError, match="объединять|компании"):
                    await HybridMergerService.open_hybrid(
                        session, company_ids[1], "hybrid_miner", *foreign_sources
                    )
                statuses = (
                    await session.execute(
                        select(NatBusiness.status).where(NatBusiness.company_id == company_ids[0])
                    )
                ).scalars().all()
                assert set(statuses) == {"ACTIVE"}
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_open_requires_the_recipe_source_types_and_eligible_statuses() -> None:
    async def check() -> None:
        engine, sessions, company_ids = await _fixture()
        try:
            async with sessions() as session:
                sources = await _source_ids(company_ids[0], session)
                wrong_order = (sources[1], sources[0])
                # Reversed source order is supported; a duplicate source is not.
                with pytest.raises(ValueError, match="разных предприятия|пары"):
                    await HybridMergerService.open_hybrid(
                        session, company_ids[0], "hybrid_miner", sources[0], sources[0]
                    )
                mismatched_source = await session.get(NatBusiness, sources[1])
                mismatched_source.business_type = "silver_mine"
                with pytest.raises(ValueError, match="пару|рецепта"):
                    await HybridMergerService.open_hybrid(
                        session, company_ids[0], "hybrid_miner", *sources
                    )
                mismatched_source.business_type = "iron_quarry"
                source = await session.get(NatBusiness, wrong_order[0])
                source.status = "UPGRADING"
                source.stage = 25
                source.upgrade_target_stage = 26
                with pytest.raises(ValueError, match="дождитесь улучшения.*25 → 26"):
                    await HybridMergerService.open_hybrid(
                        session, company_ids[0], "hybrid_miner", *wrong_order
                    )
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_selling_restores_sources_and_refunds_only_added_hybrid_capital() -> None:
    async def check() -> None:
        engine, sessions, company_ids = await _fixture()
        try:
            async with sessions() as session:
                company = await session.get(NatCompany, company_ids[0])
                initial_cash = float(company.cash)
                source_ids = await _source_ids(company.id, session)
                original = [await session.get(NatBusiness, source_id) for source_id in source_ids]
                for row in original:
                    row.status = "PAUSED_MANUAL"
                await session.flush()
                original_statuses = [row.status for row in original]
                original_capital = [float(row.capital_invested) for row in original]
                recipe = HYBRID_RECIPES["hybrid_miner"]
                input_quantities = {
                    row.item_id: float(row.quantity)
                    for row in (
                        await session.execute(
                            select(NatInventory).where(NatInventory.company_id == company.id)
                        )
                    ).scalars().all()
                }

                opened = await HybridMergerService.open_hybrid(
                    session, company.id, "hybrid_miner", *source_ids
                )
                assert opened["additional_capital_invested"] > 0
                assert float(company.cash) == pytest.approx(initial_cash - opened["additional_capital_invested"])
                for source_id in source_ids:
                    source = await session.get(NatBusiness, source_id)
                    assert source.status == "MERGING"
                    assert source.slot_weight == 0
                hybrid_business = await session.get(NatBusiness, opened["hybrid_business_id"])
                assert hybrid_business.business_type == "hybrid_miner"
                assert hybrid_business.status == "ACTIVE"
                assert hybrid_business.slot_weight == 1
                for item_id, quantity in recipe["resource_requirements"].items():
                    inventory = await session.scalar(
                        select(NatInventory).where(
                            NatInventory.company_id == company.id,
                            NatInventory.item_id == item_id,
                        )
                    )
                    assert float(inventory.quantity) == pytest.approx(
                        input_quantities[item_id] - quantity
                    )

                sold = await HybridMergerService.sell_hybrid(session, company.id, opened["id"])
                await session.flush()
                refund = round(opened["additional_capital_invested"] * recipe["sale_refund_ratio"], 2)
                assert sold["refund"] == pytest.approx(refund)
                assert float(company.cash) == pytest.approx(initial_cash - opened["additional_capital_invested"] + refund)
                restored = [await session.get(NatBusiness, source_id) for source_id in source_ids]
                assert [row.status for row in restored] == original_statuses
                assert [row.stage for row in restored] == [1, 1]
                assert [row.slot_weight for row in restored] == [1, 1]
                assert [float(row.capital_invested) for row in restored] == original_capital
                assert await session.scalar(
                    select(func.count(NatBusiness.id)).where(NatBusiness.company_id == company.id)
                ) == 2
                assert await session.get(NatBusiness, opened["hybrid_business_id"]) is None
                hybrid = await session.get(NatHybridMerger, opened["id"])
                assert hybrid.status == "SOLD"
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_regular_sale_rejects_a_business_while_it_is_a_hybrid_source() -> None:
    async def check() -> None:
        engine, sessions, company_ids = await _fixture()
        try:
            async with sessions() as session:
                source_ids = await _source_ids(company_ids[0], session)
                opened = await HybridMergerService.open_hybrid(
                    session, company_ids[0], "hybrid_miner", *source_ids
                )
                with pytest.raises(ValueError, match="гибрид|объедин"):
                    await BusinessService.sell(
                        session, company_ids[0], opened["hybrid_business_id"]
                    )
                with pytest.raises(ValueError, match="гибрид|объедин"):
                    await BusinessService.sell(session, company_ids[0], source_ids[0])
                assert (await session.get(NatHybridMerger, opened["id"])).status == "ACTIVE"
                assert (await session.get(NatBusiness, source_ids[0])).status == "MERGING"
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_hybrid_catalog_entry_cannot_be_opened_as_a_standalone_business() -> None:
    async def check() -> None:
        engine, sessions, company_ids = await _fixture()
        try:
            async with sessions() as session:
                with pytest.raises(ValueError, match="объединение|исходных предприятий"):
                    await BusinessService.open_business(
                        session, company_ids[0], "hybrid_miner"
                    )
                assert await session.scalar(
                    select(func.count(NatHybridMerger.id)).where(
                        NatHybridMerger.company_id == company_ids[0]
                    )
                ) == 0
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_hybrid_sources_are_hidden_from_active_company_businesses() -> None:
    async def check() -> None:
        engine, sessions, company_ids = await _fixture()
        try:
            async with sessions() as session:
                company = await session.get(NatCompany, company_ids[0])
                source_ids = await _source_ids(company.id, session)
                opened = await HybridMergerService.open_hybrid(
                    session, company.id, "hybrid_miner", *source_ids
                )

                summary = await EmpireSummaryService.build(session, company.id)
                active_ids = {row["id"] for row in summary["businesses"]}
                assert active_ids == {opened["hybrid_business_id"]}
                assert {row["business_type"] for row in summary["catalog_businesses"]} >= set(MINER_SOURCE_TYPES)

                stored_sources = [await session.get(NatBusiness, source_id) for source_id in source_ids]
                assert all(row.status == "MERGING" for row in stored_sources)
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_hybrid_sources_are_not_offered_for_another_merger() -> None:
    async def check() -> None:
        engine, sessions, company_ids = await _fixture()
        try:
            async with sessions() as session:
                company = await session.get(NatCompany, company_ids[0])
                source_ids = await _source_ids(company.id, session)
                await HybridMergerService.open_hybrid(
                    session, company.id, "hybrid_miner", *source_ids
                )

                data = await hybrid_catalog(company, session)
                offered_ids = {row["id"] for row in data["businesses"]}
                assert offered_ids.isdisjoint(source_ids)
                assert all(
                    business["id"] not in source_ids
                    for recipe in data["recipes"]
                    for option in recipe["source_options"]
                    for business in option["businesses"]
                )
        finally:
            await engine.dispose()

    asyncio.run(check())
