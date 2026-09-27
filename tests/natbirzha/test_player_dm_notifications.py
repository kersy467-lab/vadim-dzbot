"""Private player messages are sent after company actions commit."""

import asyncio

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.db.session import get_db_session
from backend.natbirzha.api.joint_factory_routes import (
    _notify_joint_proposal,
    router as joint_factory_router,
)
from backend.natbirzha.api.supply_deal_routes import (
    _notify_deal_participant,
    router as supply_deal_router,
)
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.joint_factories import NatJointFactoryProposal
from backend.natbirzha.services import player_dm_service
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.auth_service import get_current_company


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)


async def _session_fixture():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session = sessions()
    users = [
        User(tg_id=993801, full_name="Deal Proposer"),
        User(tg_id=993802, full_name="Deal Partner"),
    ]
    session.add_all(users)
    await session.flush()
    companies = [
        NatCompany(user_id=users[0].id, name="Power Co", specialization="power_engineer"),
        NatCompany(user_id=users[1].id, name="Water Co", specialization="water"),
    ]
    session.add_all(companies)
    await session.flush()
    return engine, session, users, companies


def test_supply_deal_notification_goes_to_the_other_company_owner(monkeypatch):
    async def check():
        engine, session, _users, companies = await _session_fixture()
        bot = FakeBot()
        monkeypatch.setattr(player_dm_service, "_current_bot", lambda: bot)
        try:
            buyer, supplier = companies
            deal = {
                "buyer_company_id": buyer.id,
                "buyer_company_name": buyer.name,
                "supplier_company_id": supplier.id,
                "supplier_company_name": supplier.name,
                "item_name": "Электроэнергия",
                "quantity_per_hour": 100,
                "unit": "МВт·ч",
                "discount_pct": 20,
                "reward_type": "PROFIT_SHARE",
                "profit_share_pct": 5,
                "fixed_cash": None,
                "term_seconds": 7200,
                "status": "PENDING",
            }
            await _notify_deal_participant(session, buyer.id, deal, "created")
            assert len(bot.messages) == 1
            assert bot.messages[0]["chat_id"] == 993802
            assert "Power Co" in bot.messages[0]["text"]
            assert "Электроэнергия" in bot.messages[0]["text"]
        finally:
            await session.close()
            await engine.dispose()

    asyncio.run(check())


def test_joint_factory_notifications_cover_proposal_and_response(monkeypatch):
    async def check():
        engine, session, _users, companies = await _session_fixture()
        bot = FakeBot()
        monkeypatch.setattr(player_dm_service, "_current_bot", lambda: bot)
        try:
            proposer, partner = companies
            proposal = NatJointFactoryProposal(
                proposer_company_id=proposer.id,
                partner_company_id=partner.id,
                recipe_id="joint_power_engineer_water",
                operation="BUILD",
                target_level=1,
                status="PENDING",
            )
            session.add(proposal)
            await session.commit()

            await _notify_joint_proposal(session, proposer.id, proposal.id, "created")
            await session.refresh(proposal)
            proposal.status = "ACCEPTED"
            await session.commit()
            await _notify_joint_proposal(session, partner.id, proposal.id, "accepted")

            assert [row["chat_id"] for row in bot.messages] == [993802, 993801]
            assert "совместное предприятие" in bot.messages[0]["text"]
            assert "приняла предложение" in bot.messages[1]["text"]
        finally:
            await session.close()
            await engine.dispose()

    asyncio.run(check())


def test_supply_deal_routes_send_direct_messages_once(monkeypatch):
    async def check():
        engine, seed_session, _users, companies = await _session_fixture()
        buyer, supplier = companies
        seed_session.add(NatBusiness(
            company_id=supplier.id,
            business_type="artesian_well",
            specialization="water",
            stage=1,
            status="ACTIVE",
        ))
        await seed_session.commit()
        await seed_session.close()
        actor = {"company_id": buyer.id}
        bot = FakeBot()
        monkeypatch.setattr(player_dm_service, "_current_bot", lambda: bot)

        app = FastAPI()
        app.include_router(supply_deal_router)

        async def test_session():
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                yield session

        async def test_company(session: AsyncSession = Depends(get_db_session)):
            return await session.get(NatCompany, actor["company_id"])

        app.dependency_overrides[get_db_session] = test_session
        app.dependency_overrides[get_current_company] = test_company
        payload = {
            "supplier_company_id": supplier.id,
            "item_id": "water",
            "quantity_per_hour": 1,
            "discount_pct": 0,
            "term_seconds": 600,
            "reward_type": "PROFIT_SHARE",
            "profit_share_pct": 1,
        }
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app, raise_app_exceptions=True),
                base_url="http://test",
            ) as client:
                created = await client.post(
                    "/market/deals", headers={"Idempotency-Key": "dm-deal-create"}, json=payload
                )
                assert created.status_code == 200, created.text
                deal_id = created.json()["id"]
                replay = await client.post(
                    "/market/deals", headers={"Idempotency-Key": "dm-deal-create"}, json=payload
                )
                assert replay.json() == created.json()
                assert [message["chat_id"] for message in bot.messages] == [993802]

                actor["company_id"] = supplier.id
                accepted = await client.post(
                    f"/market/deals/{deal_id}/accept",
                    headers={"Idempotency-Key": "dm-deal-accept"},
                )
                assert accepted.status_code == 200, accepted.text
                assert accepted.json()["status"] == "ACTIVE"
                assert [message["chat_id"] for message in bot.messages] == [993802, 993801]
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_joint_factory_routes_send_proposal_and_rejection_dms(monkeypatch):
    async def check():
        engine, seed_session, _users, companies = await _session_fixture()
        proposer, partner = companies
        await seed_session.commit()
        await seed_session.close()
        actor = {"company_id": proposer.id}
        bot = FakeBot()
        monkeypatch.setattr(player_dm_service, "_current_bot", lambda: bot)

        app = FastAPI()
        app.include_router(joint_factory_router)

        async def test_session():
            async with async_sessionmaker(engine, expire_on_commit=False)() as session:
                yield session

        async def test_company(session: AsyncSession = Depends(get_db_session)):
            return await session.get(NatCompany, actor["company_id"])

        app.dependency_overrides[get_db_session] = test_session
        app.dependency_overrides[get_current_company] = test_company
        payload = {
            "partner_company_id": partner.id,
            "recipe_id": "joint_power_engineer_water",
        }
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app, raise_app_exceptions=True),
                base_url="http://test",
            ) as client:
                created = await client.post(
                    "/joint-factories/proposals",
                    headers={"Idempotency-Key": "dm-joint-create"},
                    json=payload,
                )
                assert created.status_code == 200, created.text
                proposal_id = created.json()["proposal_id"]
                replay = await client.post(
                    "/joint-factories/proposals",
                    headers={"Idempotency-Key": "dm-joint-create"},
                    json=payload,
                )
                assert replay.json() == created.json()
                assert [message["chat_id"] for message in bot.messages] == [993802]

                actor["company_id"] = partner.id
                rejected = await client.post(
                    f"/joint-factories/proposals/{proposal_id}/reject",
                    headers={"Idempotency-Key": "dm-joint-reject"},
                )
                assert rejected.status_code == 200, rejected.text
                assert rejected.json()["status"] == "REJECTED"
                assert [message["chat_id"] for message in bot.messages] == [993802, 993801]
        finally:
            await engine.dispose()

    asyncio.run(check())


def test_idempotency_replay_is_not_reported_as_a_second_commit():
    async def check():
        engine, session, users, _companies = await _session_fixture()
        try:
            response, created = await IdempotencyService.commit_response_once(
                session,
                users[0].id,
                "/test/private-message",
                "same-action",
                {"action": "create"},
                {"id": 123, "status": "PENDING"},
            )
            replay, replay_created = await IdempotencyService.commit_response_once(
                session,
                users[0].id,
                "/test/private-message",
                "same-action",
                {"action": "create"},
                {"id": 123, "status": "PENDING"},
            )
            assert response == replay
            assert created is True
            assert replay_created is False
        finally:
            await session.close()
            await engine.dispose()

    asyncio.run(check())


def test_dm_delivery_failure_never_raises_to_the_game_action(monkeypatch):
    async def check():
        engine, session, _users, companies = await _session_fixture()

        class BrokenBot:
            async def send_message(self, **kwargs):
                raise RuntimeError("Telegram is unavailable")

        monkeypatch.setattr(player_dm_service, "_current_bot", lambda: BrokenBot())
        try:
            assert await player_dm_service.send_company_dm(session, companies[0].id, "notification") is False
        finally:
            await session.close()
            await engine.dispose()

    asyncio.run(check())
