import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import func, select

from backend.db.models import Base
from backend.db.session import async_session_factory, engine
from backend.natbirzha.models.creator import NatCreatorAuditLog, NatStateBond
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.creator_service import CreatorService
from backend.natbirzha.services.idempotency_service import IdempotencyService


async def reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


async def run_checks():
    await reset_db()
    endpoint = "/api/natbirzha/creator/bonds/issue"
    payload = {
        "title": "ОФЗ-TEST",
        "volume": 10,
        "face_value": 1000.0,
        "coupon_rate": 7.5,
        "maturity_days": 30,
        "purpose": "Тест реального размещения",
    }

    async with async_session_factory() as session:
        buyer = await CompanyService.create_company(session, 920001, "Bond Buyer", "miner")
        buyer.cash = 50000.0
        treasury = await CreatorService.get_or_create_treasury(session)
        treasury_before = treasury.cash

        # Critical admin mutation and idempotency record commit together.
        issue = await CreatorService.issue_bonds(
            session,
            actor_id=777,
            title=payload["title"],
            volume=payload["volume"],
            face_value=payload["face_value"],
            coupon_rate=payload["coupon_rate"],
            maturity_days=payload["maturity_days"],
            purpose=payload["purpose"],
            commit=False,
        )
        assert issue["raised_funds"] == 0.0
        assert issue["treasury_cash"] == treasury_before
        await IdempotencyService.commit_response(
            session, 777, endpoint, "issue-key", payload, issue
        )
        bond_id = issue["bond_id"]

    async with async_session_factory() as session:
        cached = await IdempotencyService.check_or_conflict(
            session, 777, endpoint, "issue-key", payload
        )
        assert cached and cached[1]["bond_id"] == bond_id
        bond_count = (await session.execute(select(func.count(NatStateBond.id)))).scalar()
        assert bond_count == 1

        buyer = await CompanyService.get_by_owner_id(session, 920001)
        buyer_before = buyer.cash
        treasury = await CreatorService.get_or_create_treasury(session)
        treasury_before = treasury.cash
        purchase = await CreatorService.buy_state_bonds(
            session, buyer, bond_id, quantity=3, commit=True
        )
        assert purchase["total_cost"] == 3000.0
        assert purchase["remaining_cash"] == buyer_before - 3000.0
        assert purchase["treasury_cash"] == treasury_before + 3000.0
        assert purchase["remaining_volume"] == 7

        holdings = await CreatorService.get_company_bond_holdings(session, buyer.id)
        assert len(holdings) == 1 and holdings[0]["quantity"] == 3
        logs = (await session.execute(select(NatCreatorAuditLog))).scalars().all()
        assert any(log.action == "BOND_ISSUANCE" for log in logs)

    print("CREATOR/STATE SERVICES: ALL CHECKS PASSED")


if __name__ == "__main__":
    asyncio.run(run_checks())
