"""HTTP regressions for paid company renames and request idempotency."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi import Depends, Header
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
from backend.db.session import get_db_session
from backend.main import app
import backend.natbirzha.models  # noqa: F401 - register all NAT tables
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company


def test_company_rename_charges_once_and_replays_idempotently():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessions() as session:
            user = User(tg_id=-981001, full_name="Rename Owner", role="guest", is_tester=False)
            rival = User(tg_id=-981002, full_name="Other Owner", role="guest", is_tester=False)
            poor = User(tg_id=-981003, full_name="Poor Owner", role="guest", is_tester=False)
            session.add_all([user, rival, poor])
            await session.flush()
            owner_id = user.id
            session.add_all([
                NatCompany(user_id=user.id, name="Original Name", specialization="miner", cash=30_000),
                NatCompany(user_id=rival.id, name="Already Used", specialization="miner", cash=30_000),
                NatCompany(user_id=poor.id, name="Poor Company", specialization="miner", cash=9_999),
            ])
            await session.commit()

        async def override_db():
            async with sessions() as session:
                yield session

        async def override_company(
            x_telegram_user_id: str = Header(..., alias="X-Telegram-User-Id"),
            session=Depends(get_db_session),
        ):
            user = await session.scalar(select(User).where(User.tg_id == int(x_telegram_user_id)))
            company = await session.scalar(select(NatCompany).where(NatCompany.user_id == user.id))
            return company

        app.dependency_overrides[get_db_session] = override_db
        headers = {
            "X-Telegram-User-Id": "-981001",
            "Idempotency-Key": "rename-company-1",
        }
        app.dependency_overrides[get_current_company] = override_company
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
                first = await client.post(
                    "/api/natbirzha/company/rename", headers=headers, json={"name": "  New Company  "}
                )
                assert first.status_code == 200, first.text
                assert first.json()["name"] == "New Company"
                assert first.json()["cash"] == 20_000
                assert first.json()["cost_paid"] == 10_000

                replay = await client.post(
                    "/api/natbirzha/company/rename", headers=headers, json={"name": "  New Company  "}
                )
                assert replay.status_code == 200 and replay.json() == first.json()

                conflict = await client.post(
                    "/api/natbirzha/company/rename", headers=headers, json={"name": "Different Name"}
                )
                assert conflict.status_code == 409

                readback = await client.get(
                    "/api/natbirzha/company/me", headers={"X-Telegram-User-Id": headers["X-Telegram-User-Id"]}
                )
                assert readback.status_code == 200
                assert readback.json()["name"] == "New Company"
                assert readback.json()["cash"] == 20_000

                invalid_headers = {"X-Telegram-User-Id": headers["X-Telegram-User-Id"]}
                missing_name = await client.post(
                    "/api/natbirzha/company/rename",
                    headers=invalid_headers,
                    json={},
                )
                assert missing_name.status_code == 422
                unchanged_name = await client.post(
                    "/api/natbirzha/company/rename",
                    headers={**invalid_headers, "Idempotency-Key": "same-company-name"},
                    json={"name": "New Company"},
                )
                assert unchanged_name.status_code == 400
                for name in ("", "   ", "X", "N" * 65, "Already Used", "<img src=x onerror=alert(1)>"):
                    invalid = await client.post(
                        "/api/natbirzha/company/rename",
                        headers={**invalid_headers, "Idempotency-Key": f"invalid-{len(name)}-{name[:2]}"},
                        json={"name": name},
                    )
                    assert invalid.status_code == 400, (name, invalid.status_code, invalid.text)

                poor_headers = {
                    "X-Telegram-User-Id": "-981003",
                    "Idempotency-Key": "rename-without-funds",
                }
                poor = await client.post(
                    "/api/natbirzha/company/rename", headers=poor_headers, json={"name": "Cannot Afford"}
                )
                assert poor.status_code == 400 and "Недостаточно" in poor.text

            async with sessions() as session:
                company = await session.scalar(select(NatCompany).where(NatCompany.user_id == owner_id))
                assert company is not None and company.name == "New Company" and company.cash == 20_000
                poor_company = await session.scalar(select(NatCompany).where(NatCompany.name == "Poor Company"))
                assert poor_company is not None and poor_company.cash == 9_999
        finally:
            app.dependency_overrides.pop(get_db_session, None)
            app.dependency_overrides.pop(get_current_company, None)
            await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    test_company_rename_charges_once_and_replays_idempotently()
    print("NATBIRZHA company rename checks: PASS")
