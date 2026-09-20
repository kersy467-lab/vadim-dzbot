"""PVC ledger and 48-hour premium-license transaction checks."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401 - register all related tables
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.premium import NatPremiumLedgerEntry, NatPremiumLicense
from backend.natbirzha.services.premium_service import InsufficientPvc, PremiumService


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessions() as session:
        company = NatCompany(user_id=910001, name="Premium Test", specialization="miner")
        session.add(company)
        await session.commit()
        company_id = company.id

        credit = await PremiumService.apply_pvc(
            session, company_id, 500, "admin_credit", "credit:1", {"reason": "test"}
        )
        assert credit.balance_before == 0 and credit.balance_after == 500
        debit = await PremiumService.apply_pvc(
            session, company_id, -25, "test_debit", "debit:1", {}
        )
        assert debit.balance_before == 500 and debit.balance_after == 475
        duplicate = await PremiumService.apply_pvc(
            session, company_id, -25, "test_debit", "debit:1", {}
        )
        assert duplicate.id == debit.id
        assert company.pvc_balance == 475

        try:
            await PremiumService.apply_pvc(
                session, company_id, -999, "test_debit", "debit:too-much", {}
            )
        except InsufficientPvc as exc:
            assert exc.required == 999 and exc.available == 475
        else:
            raise AssertionError("Insufficient PVC debit must fail")

        await session.commit()
        ledger_total = await session.scalar(
            select(func.sum(NatPremiumLedgerEntry.amount)).where(
                NatPremiumLedgerEntry.company_id == company_id
            )
        )
        assert ledger_total == company.pvc_balance == 475

        await PremiumService.apply_pvc(
            session, company_id, 10, "rollback_check", "rollback:1", {}
        )
        await session.rollback()

    async with sessions() as session:
        company = await session.get(NatCompany, company_id)
        assert company is not None and company.pvc_balance == 475
        rolled_back = await session.scalar(
            select(NatPremiumLedgerEntry).where(
                NatPremiumLedgerEntry.operation_key == "rollback:1"
            )
        )
        assert rolled_back is None

        now = datetime(2026, 9, 18, 12, 0, 0)
        license_row = await PremiumService.purchase_license(
            session,
            company_id,
            "rare_mining",
            "license:rare:1",
            now=now,
        )
        assert license_row.starts_at == now
        assert license_row.expires_at == now + timedelta(hours=48)
        assert await PremiumService.is_license_active(
            session, company_id, "rare_mining", now + timedelta(hours=47, minutes=59, seconds=59)
        )
        assert not await PremiumService.is_license_active(
            session, company_id, "rare_mining", now + timedelta(hours=48)
        )

        # Renewing before expiry stacks a full 48 hours after the current expiry.
        renewed = await PremiumService.purchase_license(
            session,
            company_id,
            "rare_mining",
            "license:rare:2",
            now=now + timedelta(hours=24),
        )
        assert renewed.expires_at == now + timedelta(hours=96)
        renewed_expiry = renewed.expires_at
        balance_after_renewal = company.pvc_balance

        # Replaying the operation is idempotent and must not extend or debit again.
        replayed = await PremiumService.purchase_license(
            session,
            company_id,
            "rare_mining",
            "license:rare:2",
            now=now + timedelta(hours=25),
        )
        assert replayed.expires_at == renewed_expiry
        assert company.pvc_balance == balance_after_renewal
        await session.commit()

        licenses = (await session.execute(select(NatPremiumLicense))).scalars().all()
        assert len(licenses) == 1
        ledger_total = await session.scalar(
            select(func.sum(NatPremiumLedgerEntry.amount)).where(
                NatPremiumLedgerEntry.company_id == company_id
            )
        )
        assert ledger_total == company.pvc_balance

    await engine.dispose()
    print("NATBIRZHA PVC ledger and timed-license checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())

