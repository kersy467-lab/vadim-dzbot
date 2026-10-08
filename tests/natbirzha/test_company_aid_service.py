"""Voluntary company aid: eligibility, transfer accounting, and rolling cap."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.company_aid import NatCompanyAidRequest, NatCompanyAidTransfer
from backend.natbirzha.api.company_aid_routes import router
from backend.db.session import get_db_session
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.company_aid_service import CompanyAidService


async def _database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, sessions


async def _company(session, user_id: int, *, level: int, cash: float, name: str):
    user = User(id=user_id, tg_id=user_id, full_name=name, role="public")
    session.add(user)
    await session.flush()
    company = NatCompany(
        user_id=user.id, name=name, specialization="miner", level=level, cash=cash,
    )
    session.add(company)
    await session.flush()
    return company


async def run_async() -> None:
    engine, sessions = await _database()
    now = datetime(2026, 10, 8, 12, 0, 0)
    async with sessions() as session:
        donor = await _company(session, 920101, level=20, cash=250_000, name="Aid Donor")
        recipient = await _company(session, 920102, level=6, cash=2_000, name="New Company")
        veteran = await _company(session, 920103, level=11, cash=1_000, name="Veteran Company")
        bankrupt = await _company(session, 920104, level=4, cash=0, name="Bankrupt Company")
        bankrupt.is_bankrupt = True
        stock = NatInventory(
            company_id=donor.id, item_id="water", quantity=100_000,
            reserved_quantity=80_000, avg_cost_basis=1.5,
        )
        session.add(stock)
        await session.commit()
        donor_id, recipient_id, veteran_id = donor.id, recipient.id, veteran.id

        try:
            await CompanyAidService.transfer(
                session, donor_id, recipient_id, amount_cash=1, now=now,
            )
        except ValueError as exc:
            assert "заявк" in str(exc).lower()
        else:
            raise AssertionError("A recipient must request aid before receiving a transfer")

        for invalid_amount in (float("nan"), float("inf"), 0.001):
            try:
                await CompanyAidService.create_request(
                    session, recipient_id, kind="cash", amount_cash=invalid_amount, now=now,
                )
            except ValueError:
                pass
            else:
                raise AssertionError("Cash requests must be finite and at least one cent")
        try:
            await CompanyAidService.create_request(
                session, recipient_id, kind="item", item_id="water",
                item_quantity=0.0000001, now=now,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Inventory requests must use at most six decimal places")

        aid_request = await CompanyAidService.create_request(
            session, recipient_id, kind="cash", amount_cash=60_000,
            message="Нужно запустить заводы", now=now,
        )
        assert aid_request["status"] == "OPEN"
        session.add(NatCompanyAidRequest(
            company_id=veteran_id, kind="cash", amount_cash=500,
            status="OPEN", created_at=now,
        ))
        session.add(NatCompanyAidRequest(
            company_id=bankrupt.id, kind="cash", amount_cash=500,
            status="OPEN", created_at=now,
        ))
        await session.flush()
        listed = await CompanyAidService.list_requests(session, exclude_company_id=donor_id)
        assert listed[0]["company_name"] == "New Company"
        assert all(row["company_id"] != veteran_id for row in listed)
        assert all(row["company_id"] != bankrupt.id for row in listed)
        try:
            await CompanyAidService.create_request(
                session, veteran_id, kind="cash", amount_cash=1_000, now=now,
            )
        except ValueError as exc:
            assert "начинающ" in str(exc).lower()
        else:
            raise AssertionError("Companies over the beginner level limit cannot request aid")

        cash_transfer = await CompanyAidService.transfer(
            session, donor_id, recipient_id, amount_cash=60_000,
            request_id=aid_request["id"], now=now,
        )
        assert cash_transfer["cash_amount"] == 60_000
        assert cash_transfer["aid_value_cash"] == 60_000

        water_transfer = await CompanyAidService.transfer(
            session,
            donor_id,
            recipient_id,
            item_id="water",
            quantity=20_000,
            request_id=(await CompanyAidService.create_request(
                session, recipient_id, kind="item", item_id="water", item_quantity=20_000,
                now=now,
            ))["id"],
            now=now,
        )
        assert water_transfer["item_quantity"] == 20_000
        assert water_transfer["aid_value_cash"] == 40_000

        donor_row = await session.get(NatCompany, donor_id)
        recipient_row = await session.get(NatCompany, recipient_id)
        assert donor_row.cash == 190_000
        assert recipient_row.cash == 62_000
        donor_water = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == donor_id, NatInventory.item_id == "water"
        ))
        recipient_water = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == recipient_id, NatInventory.item_id == "water"
        ))
        assert donor_water.quantity == 80_000
        assert donor_water.reserved_quantity == 80_000
        assert recipient_water.quantity == 20_000

        try:
            over_cap_request = await CompanyAidService.create_request(
                session, recipient_id, kind="cash", amount_cash=1, now=now,
            )
            await CompanyAidService.transfer(
                session, donor_id, recipient_id, amount_cash=1,
                request_id=over_cap_request["id"], now=now,
            )
        except ValueError as exc:
            assert "лимит" in str(exc).lower()
        else:
            raise AssertionError("Rolling weekly aid cap must reject aid over 100,000 cash-equivalent")
        await CompanyAidService.cancel_request(session, recipient_id, over_cap_request["id"])

        try:
            await CompanyAidService.transfer(
                session, donor_id, donor_id, amount_cash=100, now=now,
            )
        except ValueError as exc:
            assert "самой себе" in str(exc).lower()
        else:
            raise AssertionError("Self aid must be rejected")

        try:
            await CompanyAidService.transfer(
                session, donor_id, recipient_id, amount_cash=float("nan"),
                request_id=aid_request["id"], now=now,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Non-finite cash transfers must be rejected")

        try:
            reserved_request = await CompanyAidService.create_request(
                session, recipient_id, kind="item", item_id="water", item_quantity=20_001,
                now=now + timedelta(days=8),
            )
            await CompanyAidService.transfer(
                session, donor_id, recipient_id, item_id="water", quantity=21,
                request_id=reserved_request["id"], now=now + timedelta(days=8),
            )
        except ValueError as exc:
            assert "доступно" in str(exc).lower()
        else:
            raise AssertionError("Reserved inventory must never be transferable")

        await CompanyAidService.cancel_request(session, recipient_id, reserved_request["id"])
        fresh_request = await CompanyAidService.create_request(
            session, recipient_id, kind="cash", amount_cash=100_000,
            now=now + timedelta(days=8),
        )
        try:
            await CompanyAidService.transfer(
                session, donor_id, recipient_id, amount_cash=0.001,
                request_id=fresh_request["id"], now=now + timedelta(days=8),
            )
        except ValueError as exc:
            assert "0.01" in str(exc)
        else:
            raise AssertionError("Sub-cent cash transfers must be rejected")

        # Once the seven-day window expires, a fresh gift may use the full cap.
        later = await CompanyAidService.transfer(
            session, donor_id, recipient_id, amount_cash=100_000,
            request_id=fresh_request["id"],
            now=now + timedelta(days=8),
        )
        assert later["aid_value_cash"] == 100_000

        second_recipient = await _company(
            session, 920105, level=3, cash=0, name="Second New Company",
        )
        third_recipient = await _company(
            session, 920106, level=2, cash=0, name="Third New Company",
        )
        second_request = await CompanyAidService.create_request(
            session, second_recipient.id, kind="cash", amount_cash=1, now=now + timedelta(days=8),
        )
        await CompanyAidService.transfer(
            session, donor_id, second_recipient.id, amount_cash=1,
            request_id=second_request["id"], now=now + timedelta(days=8),
        )
        third_request = await CompanyAidService.create_request(
            session, third_recipient.id, kind="cash", amount_cash=1, now=now + timedelta(days=8),
        )
        before_third_gift = donor_row.cash
        try:
            await CompanyAidService.transfer(
                session, donor_id, third_recipient.id, amount_cash=1,
                request_id=third_request["id"], now=now + timedelta(days=8),
            )
        except ValueError as exc:
            assert "двум" in str(exc).lower()
        else:
            raise AssertionError("One donor may help no more than two different companies per week")
        assert donor_row.cash == before_third_gift
        assert third_recipient.cash == 0
        donor_summary = await CompanyAidService.summary(
            session, donor_id, now=now + timedelta(days=8),
        )
        assert donor_summary["supported_companies"] == 2
        assert donor_summary["total_aid_value_cash"] == 200_001
        assert donor_summary["mentor_title"] == "Наставник"
        assert donor_summary["current_week_supported_count"] == 2
        assert donor_summary["max_supported_companies_per_week"] == 2
        assert donor_summary["recipient_week_remaining_cash"] == 100_000
        recipient_summary = await CompanyAidService.summary(
            session, recipient_id, now=now + timedelta(days=8),
        )
        assert recipient_summary["mentor_title"] == "Будущий наставник"
        assert recipient_summary["recipient_week_remaining_cash"] == 0
        records = (await session.scalars(select(NatCompanyAidTransfer))).all()
        assert len(records) == 4

    await engine.dispose()
    print("Company aid service checks: PASS")


def test_company_aid_transfers_and_weekly_cap() -> None:
    asyncio.run(run_async())


if __name__ == "__main__":
    asyncio.run(run_async())


def test_company_aid_api_is_authenticated_and_idempotent() -> None:
    async def check() -> None:
        engine, sessions = await _database()
        async with sessions() as session:
            donor = await _company(session, 920201, level=20, cash=100_000, name="Route Donor")
            recipient = await _company(session, 920202, level=4, cash=0, name="Route Newcomer")
            await session.commit()
            current = {"company": donor}

            async def override_session():
                yield session

            async def override_company():
                return current["company"]

            app = FastAPI()
            app.include_router(router)
            app.dependency_overrides[get_db_session] = override_session
            app.dependency_overrides[get_current_company] = override_company
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test",
                ) as client:
                    current["company"] = recipient
                    opened = await client.post(
                        "/aid/requests",
                        json={"kind": "cash", "amount_cash": 25_000.01, "message": "Оплата расходов"},
                        headers={"Idempotency-Key": "aid-request-create"},
                    )
                    assert opened.status_code == 200
                    current["company"] = donor
                    transfer_body = {
                        "recipient_company_id": recipient.id,
                        "request_id": opened.json()["request"]["id"],
                        "amount_cash": 25_000.005,
                    }
                    await session.execute(update(NatCompany).where(
                        NatCompany.id == donor.id,
                    ).values(cash=90_000).execution_options(synchronize_session=False))
                    headers = {"Idempotency-Key": "aid-transfer-once"}
                    first = await client.post("/aid/transfer", json=transfer_body, headers=headers)
                    retry = await client.post("/aid/transfer", json=transfer_body, headers=headers)
                    assert first.status_code == retry.status_code == 200
                    assert first.json() == retry.json()
                    assert first.json()["cash_amount"] == 25_000.01
                    assert round(donor.cash, 2) == 64_999.99
                    assert round(recipient.cash, 2) == 25_000.01
                    summary_response = await client.get("/aid/summary")
                    assert summary_response.status_code == 200
                    assert summary_response.json()["summary"]["mentor_title"] == "Наставник"
                    assert summary_response.json()["summary"]["current_week_supported_count"] == 1
                    missing_request = await client.post(
                        "/aid/transfer",
                        json={"recipient_company_id": recipient.id, "amount_cash": 1},
                        headers={"Idempotency-Key": "aid-without-consent"},
                    )
                    assert missing_request.status_code == 422
                    missing_key = await client.post(
                        "/aid/transfer", json={**transfer_body, "amount_cash": 1},
                    )
                    assert missing_key.status_code == 400
            finally:
                app.dependency_overrides.clear()
        await engine.dispose()

    asyncio.run(check())
