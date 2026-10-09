"""Admins can clear post-rebirth progress without advancing the rebirth rank."""

import asyncio
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models import NatBusiness, NatCompany, NatInventory
from backend.natbirzha.models.creator import NatBondSettlement, NatStateBond
from backend.natbirzha.models.rebirth import NatCompanyRebirth
from backend.natbirzha.services.admin_rebirth_reset_service import AdminRebirthResetService


def test_admin_reset_restarts_two_companies_at_the_same_rebirth_rank():
    async def check():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text("PRAGMA foreign_keys=ON"))
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        target_ids = [1053722876, 7755842535]
        with patch(
            "backend.natbirzha.services.admin_rebirth_reset_service.get_creator_tg_ids",
            return_value=set(target_ids),
        ):
            async with sessions() as session:
                for index, tg_id in enumerate(target_ids):
                    user = User(id=991100 + index, tg_id=tg_id, full_name=f"Admin {index}")
                    session.add(user)
                    await session.flush()
                    company = NatCompany(
                        user_id=user.id, name=f"Reset {index}", specialization="miner",
                        level=35, xp=20000, mastery_rank=7, mastery_xp=8000,
                        cash=9_000_000 + index, rebirth_count=1,
                        rebirth_announcement_for_count=1,
                    )
                    session.add(company)
                    await session.flush()
                    session.add(NatCompanyRebirth(
                        company_id=company.id, rank=1, cash_before=50_000, tax_paid=0,
                    ))
                    session.add(NatBusiness(
                        company_id=company.id, business_type="mine_v2", specialization="miner",
                        stage=18, status="ACTIVE",
                    ))
                    session.add(NatInventory(company_id=company.id, item_id="coal", quantity=50))
                    bond = NatStateBond(
                        title=f"Pending coupon {index}", total_volume=10, remaining_volume=0,
                        face_value=1_000, coupon_rate=10, maturity_days=30,
                        coupon_interval_days=1, purpose="reset check", actor_id=991100,
                        is_active=False, status="MATURED",
                    )
                    session.add(bond)
                    await session.flush()
                    session.add(NatBondSettlement(
                        operation_key=f"pending-rebirth-coupon-{index}", bond_id=bond.id,
                        company_id=company.id, settlement_type="COUPON", period_number=1,
                        entitled_quantity=5, amount_rub=5_000, status="PENDING",
                        due_at=datetime(2026, 10, 1, 12),
                    ))
                await session.commit()

                result = await AdminRebirthResetService.reset_to_first_rebirth(
                    session, target_ids, actor_tg_id=target_ids[0], operation_key="test-reset-rank-one"
                )
                assert result["success"] is True
                assert len(result["companies"]) == 2
                companies = list((await session.scalars(
                    select(NatCompany).order_by(NatCompany.id)
                )).all())
                assert [company.rebirth_count for company in companies] == [1, 1]
                assert [company.level for company in companies] == [1, 1]
                assert [company.cash for company in companies] == [nat_settings.STARTING_CASH] * 2
                assert [company.mastery_rank for company in companies] == [0, 0]
                assert [company.rebirth_announcement_for_count for company in companies] == [None, None]
                assert await session.scalar(select(NatCompanyRebirth.id).where(
                    NatCompanyRebirth.rank == 1
                ).limit(1)) is not None
                assert await session.scalar(select(NatInventory.id).where(
                    NatInventory.item_id == "coal", NatInventory.quantity >= 50
                ).limit(1)) is None
                assert await session.scalar(select(NatBusiness.stage).where(
                    NatBusiness.company_id == companies[0].id, NatBusiness.stage == 18
                ).limit(1)) is None
                assert await session.scalar(select(NatBondSettlement.id).where(
                    NatBondSettlement.company_id.in_([company.id for company in companies])
                ).limit(1)) is None
        await engine.dispose()

    asyncio.run(check())
