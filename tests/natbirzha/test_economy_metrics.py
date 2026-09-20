"""Economy telemetry must separate faucets, sinks and non-cash consumption."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        company = NatCompany(user_id=991003, name="Metrics Test", specialization="miner")
        session.add(company)
        await session.flush()
        await EconomyMetricsService.record(
            session, company_id=company.id, flow="SOURCE", category="pve_reward", cash_amount=5000
        )
        await EconomyMetricsService.record(
            session, company_id=company.id, flow="SINK", category="army_recruitment", cash_amount=2000
        )
        await EconomyMetricsService.record(
            session, company_id=company.id, flow="CONSUMPTION", category="pve_casualties",
            item_id="army_units", quantity=17,
        )
        await session.commit()
        summary = await EconomyMetricsService.summary(session, days=7)
        assert summary["cash_sources"] == 5000
        assert summary["cash_sinks"] == 2000
        assert summary["net_cash_faucet"] == 3000
        assert summary["categories"]["pve_casualties"]["quantity"] == 17

    await engine.dispose()
    print("NATBIRZHA economy metrics checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
