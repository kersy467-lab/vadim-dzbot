"""Premium rare-resource production gates without market paywalls."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.premium import NatPremiumLicense
from backend.natbirzha.services.building_service import BuildingService
from backend.natbirzha.services.market_service import MarketService
from backend.natbirzha.services.premium_service import PremiumLicenseRequired, PremiumService
from backend.natbirzha.services.production_service import ProductionTickEngine


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        miner = NatCompany(
            user_id=970001, name="Licensed Miner", specialization="miner",
            level=60, cash=3_000_000, territory_tiles=20,
        )
        buyer = NatCompany(
            user_id=970002, name="Market Buyer", specialization="agrarian", cash=50_000
        )
        session.add_all([miner, buyer])
        await session.flush()
        for item_id, quantity in (("grid_quota", 100.0), ("water", 100.0), ("lithium_raw", 10.0)):
            session.add(NatInventory(company_id=miner.id, item_id=item_id, quantity=quantity))
        await session.commit()

        try:
            await BuildingService.build_factory(session, miner, "lithium_mine", commit=False)
        except PremiumLicenseRequired as exc:
            assert exc.license_code == "rare_mining"
        else:
            raise AssertionError("Lithium mine must require an active rare-mining license")

        await PremiumService.apply_pvc(
            session, miner.id, 500, "test_credit", "premium-production-credit", {}
        )
        now = get_game_now()
        license_now = datetime.utcnow()
        await PremiumService.purchase_license(
            session, miner.id, "rare_mining", "rare-license-1", now=license_now
        )
        # The contract grants the visible Tycoon V2 quarry. Classic production
        # remains available as a separately built licensed facility.
        assert await session.scalar(
            select(NatFactory).where(
                NatFactory.company_id == miner.id,
                NatFactory.building_type == "lithium_mine",
            )
        ) is None
        classic_mine = await BuildingService.build_factory(
            session, miner, "lithium_mine", commit=False
        )
        lithium_factory = await session.scalar(
            select(NatFactory).where(NatFactory.id == classic_mine["factory_id"])
        )
        assert lithium_factory is not None and lithium_factory.level == 1

        license_row = await session.scalar(
            select(NatPremiumLicense).where(
                NatPremiumLicense.company_id == miner.id,
                NatPremiumLicense.license_code == "rare_mining",
            )
        )
        license_row.expires_at = license_now - timedelta(seconds=1)
        await session.flush()
        try:
            await BuildingService.build_factory(session, miner, "rare_earth_mine", commit=False)
        except PremiumLicenseRequired:
            pass
        else:
            raise AssertionError("Expired licenses must not unlock construction")

        renewal_now = datetime.utcnow()
        renewed = await PremiumService.purchase_license(
            session, miner.id, "rare_mining", "rare-license-2", now=renewal_now
        )
        assert renewed.starts_at == renewal_now
        rare_build = await BuildingService.build_factory(
            session, miner, "rare_earth_mine", commit=False
        )
        assert rare_build["success"] is True

        start = await ProductionTickEngine.start_cycle(
            session, miner, lithium_factory, "mine_lithium", now=now
        )
        assert start["success"] is True
        license_row.expires_at = datetime.utcnow() + timedelta(seconds=1)
        complete = await ProductionTickEngine.complete_cycle(
            session, miner, lithium_factory, now=now + timedelta(seconds=200)
        )
        assert complete["success"] is True
        assert complete["outputs_produced"]["lithium_raw"] > 0

        # A company without the license may still buy rare resources from players.
        await MarketService.create_order(
            session, miner, "SELL", "lithium_raw", 100.0, 2.0, commit=False
        )
        await MarketService.create_order(
            session, buyer, "BUY", "lithium_raw", 100.0, 2.0, commit=False
        )
        buyer_lithium = await session.scalar(
            select(NatInventory).where(
                NatInventory.company_id == buyer.id,
                NatInventory.item_id == "lithium_raw",
            )
        )
        assert buyer_lithium is not None and buyer_lithium.quantity == 2.0

    await engine.dispose()
    print("NATBIRZHA premium production-gate checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())

