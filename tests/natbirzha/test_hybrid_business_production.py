"""Hybrid NatBusiness rows use the ordinary input/output settlement path."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import HYBRID_RECIPES, get_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.hybrid_mergers import NatHybridMerger
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.hybrid_merger_service import HybridMergerService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


async def _fixture():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        user = User(tg_id=993001, full_name="Hybrid Producer")
        session.add(user)
        await session.flush()
        company = NatCompany(
            user_id=user.id,
            name="Hybrid Producer Co",
            specialization="miner",
            cash=1_000_000.0,
        )
        session.add(company)
        await session.flush()
        sources = [
            NatBusiness(
                company_id=company.id,
                business_type=business_type,
                specialization="miner",
                stage=1,
                status="PAUSED_MANUAL",
                capital_invested=1_000.0,
            )
            for business_type in HYBRID_RECIPES["hybrid_miner"]["source_business_types"]
        ]
        session.add_all(sources)
        for item_id, quantity in HYBRID_RECIPES["hybrid_miner"]["resource_requirements"].items():
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
        company_id = company.id
    return engine, sessions, company_id


def test_hybrid_settlement_consumes_inputs_and_adds_produced_inventory() -> None:
    async def check() -> None:
        engine, sessions, company_id = await _fixture()
        try:
            async with sessions() as session:
                source_ids = (
                    await session.execute(
                        select(NatBusiness.id)
                        .where(NatBusiness.company_id == company_id)
                        .order_by(NatBusiness.id)
                    )
                ).scalars().all()
                started = datetime.utcnow() + timedelta(seconds=1)
                opened = await HybridMergerService.open_hybrid(
                    session, company_id, "hybrid_miner", *source_ids, now=started
                )
                hybrid = await session.get(NatBusiness, opened["hybrid_business_id"])
                spec = get_business_spec(hybrid.business_type)
                assert spec is not None and spec["mechanic"] == "resource_production"

                for item_id, per_hour in spec["inputs_per_hour"].items():
                    inventory = await session.scalar(
                        select(NatInventory).where(
                            NatInventory.company_id == company_id,
                            NatInventory.item_id == item_id,
                        )
                    )
                    if inventory is None:
                        session.add(NatInventory(
                            company_id=company_id,
                            item_id=item_id,
                            quantity=float(per_hour) * 2,
                            reserved_quantity=0.0,
                            avg_cost_basis=1.0,
                        ))
                    else:
                        inventory.quantity = max(
                            float(inventory.quantity), float(per_hour) * 2
                        )
                await session.flush()

                async def quantities(item_ids: list[str]) -> dict[str, float]:
                    result: dict[str, float] = {}
                    for item_id in item_ids:
                        value = await session.scalar(
                            select(NatInventory.quantity).where(
                                NatInventory.company_id == company_id,
                                NatInventory.item_id == item_id,
                            )
                        )
                        result[item_id] = float(value or 0.0)
                    return result

                output_ids = list(spec["outputs_per_hour"])
                input_ids = list(spec["inputs_per_hour"])
                before_output = await quantities(output_ids)
                before_input = await quantities(input_ids)
                await IdleEconomyService.settle_company(
                    session, company_id, now=started + timedelta(hours=1)
                )
                after_output = await quantities(output_ids)
                after_input = await quantities(input_ids)

                assert any(after_output[item] > before_output[item] for item in output_ids)
                assert any(after_input[item] < before_input[item] for item in input_ids)
                assert (await session.get(NatHybridMerger, opened["id"])).hybrid_business_id == hybrid.id
                for source_id in source_ids:
                    source = await session.get(NatBusiness, source_id)
                    assert source.status == "MERGING"
        finally:
            await engine.dispose()

    asyncio.run(check())
