"""Debt is capped by net NAV and must create a repayable obligation."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.loan_service import LoanService, MAX_DEBT_TO_NAV


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        company = NatCompany(
            user_id=991002,
            name="Debt Test",
            specialization="miner",
            level=14,
            cash=100_000,
            territory_tiles=20,
        )
        session.add(company)
        await session.commit()

        status = await LoanService.status(session, company)
        assert status["quote"]["eligible"] is True
        assert status["quote"]["max_debt_to_nav"] == MAX_DEBT_TO_NAV
        principal = min(80_000.0, status["quote"]["max_principal"])
        cash_before = company.cash
        issued = await LoanService.borrow(session, company, principal)
        assert issued["loan"]["remaining_debt"] == principal
        assert company.cash == cash_before + principal

        # The new borrowed cash cannot recursively expand the credit line.
        after = await LoanService.status(session, company)
        assert after["active_debt"] >= principal
        assert after["quote"]["max_principal"] < status["quote"]["max_principal"]

        repaid = await LoanService.repay(session, company, issued["loan"]["id"], principal)
        assert repaid["loan"]["remaining_debt"] <= 0.01
        assert repaid["loan"]["status"] == "PAID"

    await engine.dispose()
    print("NATBIRZHA loan checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
