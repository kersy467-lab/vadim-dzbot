"""Creator asset seizures are reflected as finite, auditable state-share issues."""

import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.creator import NatCreatorAuditLog, NatStateTreasury
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.state_shares import NatStateShare
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.forced_bankruptcy_service import ForcedBankruptcyService


def test_admin_bankruptcy_removes_seventy_percent_nav_and_issues_state_shares_once() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            company = NatCompany(
                user_id=820_001, name="Water Corp", specialization="water",
                cash=10_000, territory_tiles=10,
            )
            treasury = NatStateTreasury(id=1, cash=5_000_000)
            session.add_all([company, treasury])
            await session.flush()
            session.add_all([
                NatFactory(
                    company_id=company.id, building_type="farm_grain",
                    specialization="water", level=2,
                ),
                NatFactory(
                    company_id=company.id, building_type="farm_grain",
                    specialization="water", level=2,
                ),
                NatInventory(company_id=company.id, item_id="water", quantity=100),
                NatBusiness(
                    company_id=company.id, business_type="water_utility", stage=1,
                    status="ACTIVE", capital_invested=100_000,
                    base_income_per_hour=0, base_maintenance_per_hour=12,
                ),
            ])
            await session.commit()
            company_id = company.id
            nav_before = await CompanyService.calculate_audited_nav(session, company)

            response = await ForcedBankruptcyService.execute(
                session, company_id=company_id, actor_id=777,
                operation_key="creator-bankruptcy-water-corp-1",
            )
            await session.refresh(company)
            nav_after = await CompanyService.calculate_audited_nav(session, company)
            issue = await session.get(NatStateShare, response["share_id"])
            audit = await session.scalar(select(NatCreatorAuditLog).where(
                NatCreatorAuditLog.action == "CREATOR_BANKRUPTCY_LIQUIDATION"
            ))

            assert issue is not None
            assert issue.title == 'Распродажа компании "Water Corp"'
            assert issue.total_volume == 10_000
            assert issue.dividend_rate_pct == 0
            assert issue.projected_annual_profit == 0
            assert abs((nav_before - nav_after) - response["seized_value"]) < 0.02
            assert abs(response["seized_value"] / nav_before - 0.70) < 0.08
            assert abs(issue.issue_price * issue.total_volume - response["seized_value"]) <= 50
            assert company.is_bankrupt is False
            assert audit is not None and audit.target_id == str(company_id)

            replay = await ForcedBankruptcyService.execute(
                session, company_id=company_id, actor_id=777,
                operation_key="creator-bankruptcy-water-corp-1",
            )
            nav_after_replay = await CompanyService.calculate_audited_nav(session, company)
            issue_count = await session.scalar(select(func.count()).select_from(NatStateShare))
            assert replay["share_id"] == response["share_id"]
            assert nav_after_replay == nav_after
            assert issue_count == 1
            try:
                await ForcedBankruptcyService.execute(
                    session, company_id=company_id, actor_id=777,
                    operation_key="creator-bankruptcy-water-corp-second-attempt",
                )
            except ValueError as exc:
                assert "already" in str(exc).lower()
            else:
                raise AssertionError("A second bankruptcy operation must not seize the remaining assets")
            assert await session.scalar(select(func.count()).select_from(NatStateShare)) == 1

        await engine.dispose()

    asyncio.run(check())
