"""Admin game access commands and release notice regressions."""

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

sys.path.insert(0, os.path.abspath("."))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.db.models import Base, ClassSetting, User
from backend.db.session import get_db_session
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.api import build_natbirzha_router
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user
from backend.natbirzha.services.maintenance_service import (
    LEGACY_MAINTENANCE_SETTING_KEY,
    MAINTENANCE_SETTING_KEY,
    MaintenanceService,
)
from backend.natbirzha.services.player_registry_service import PlayerRegistryService


def test_persisted_open_state_overrides_closed_launch_default():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            player = User(tg_id=990101, username="player", full_name="Player", role="student")
            session.add_all([player, ClassSetting(key=MAINTENANCE_SETTING_KEY, value="false")])
            await session.commit()

        previous_mode = nat_settings.ADMIN_ONLY_ACCESS
        previous_creators = nat_settings.CREATOR_TG_IDS
        nat_settings.ADMIN_ONLY_ACCESS = True
        nat_settings.CREATOR_TG_IDS = "990001"
        actor = {"user": player}

        async def db_session():
            async with sessions() as session:
                yield session

        async def current_user():
            return actor["user"]

        app = FastAPI()
        app.include_router(build_natbirzha_router(admin_only=True), prefix="/api")
        app.dependency_overrides[get_strict_natbirzha_user] = current_user
        app.dependency_overrides[get_db_session] = db_session
        try:
            with TestClient(app) as client:
                login = client.post("/api/natbirzha/auth/login")
                assert login.status_code == 200
                assert login.json()["game_access"] is True
                assert login.json()["maintenance_mode"] is False
                assert client.get("/api/natbirzha/company/industries").status_code == 200

                async def close_game():
                    async with sessions() as session:
                        await MaintenanceService.set_maintenance_active(session, True)

                await close_game()
                blocked = client.get("/api/natbirzha/company/industries")
                assert blocked.status_code == 403
                assert blocked.json()["detail"]["code"] == "GAME_ACCESS_CLOSED"

                actor["user"] = User(
                    id=2, tg_id=990001, username="owner", full_name="Admin", role="admin"
                )
                assert client.get("/api/natbirzha/company/industries").status_code == 200
        finally:
            nat_settings.ADMIN_ONLY_ACCESS = previous_mode
            nat_settings.CREATOR_TG_IDS = previous_creators
            await engine.dispose()

    asyncio.run(run())


def test_legacy_frontend_toggle_does_not_accidentally_open_admin_only_launch():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        previous_mode = nat_settings.ADMIN_ONLY_ACCESS
        nat_settings.ADMIN_ONLY_ACCESS = True
        try:
            async with sessions() as session:
                session.add(ClassSetting(key=LEGACY_MAINTENANCE_SETTING_KEY, value="false"))
                await session.commit()
                assert await MaintenanceService.is_maintenance_active(session) is True

                # The new explicit admin action overrides both old values.
                await MaintenanceService.set_maintenance_active(session, False)
                assert await MaintenanceService.is_maintenance_active(session) is False
        finally:
            nat_settings.ADMIN_ONLY_ACCESS = previous_mode
            await engine.dispose()

    asyncio.run(run())


def test_ban_and_unban_commands_are_idempotent_and_notify_registered_players():
    async def run():
        from backend.bot.handlers.admin.natbirzha_notice import (
            cmd_natbirzha_ban,
            cmd_natbirzha_unban,
        )
        from backend.natbirzha.services.world_reset_service import WorldResetService

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            admin = User(tg_id=990001, username="admin", full_name="Admin", role="admin")
            player = User(tg_id=990102, username="player", full_name="Player", role="student")
            session.add_all([admin, player])
            await session.flush()
            session.add(NatCompany(user_id=player.id, name="Player Corp", specialization="miner", cash=50_000))
            await MaintenanceService.set_maintenance_active(session, False)

            make_message = lambda command, tg_id: SimpleNamespace(  # noqa: E731
                text=command,
                chat=SimpleNamespace(type="private"),
                from_user=SimpleNamespace(id=tg_id),
                answer=AsyncMock(),
            )
            bot = AsyncMock()

            await cmd_natbirzha_ban(make_message("/ban", admin.tg_id), admin, session)
            assert await MaintenanceService.is_maintenance_active(session) is True

            # The full world wipe removes the company row but preserves its
            # owner in the release audience registry.
            await WorldResetService.execute(
                session,
                actor_tg_id=admin.tg_id,
                confirmation=WorldResetService.CONFIRMATION_PHRASE,
            )

            await cmd_natbirzha_unban(make_message("/unban", admin.tg_id), bot, admin, session)
            assert await MaintenanceService.is_maintenance_active(session) is False
            bot.send_message.assert_awaited_once()
            sent = bot.send_message.await_args.kwargs
            assert sent["chat_id"] == player.tg_id
            assert "НАТБИРЖА снова открыта" in sent["text"]
            assert "/natbirzha" in sent["text"]

            # A repeated /unban must not resend the launch announcement.
            await cmd_natbirzha_unban(make_message("/unban", admin.tg_id), bot, admin, session)
            assert bot.send_message.await_count == 1
        await engine.dispose()

    asyncio.run(run())


def test_non_admin_cannot_change_game_access():
    async def run():
        from backend.bot.handlers.admin.natbirzha_notice import cmd_natbirzha_ban

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with sessions() as session:
            player = User(tg_id=990103, username="player", full_name="Player", role="student")
            session.add(player)
            await session.commit()
            message = SimpleNamespace(
                text="/ban",
                chat=SimpleNamespace(type="private"),
                from_user=SimpleNamespace(id=player.tg_id),
                answer=AsyncMock(),
            )
            await cmd_natbirzha_ban(message, player, session)
            assert await MaintenanceService.is_maintenance_active(session) is nat_settings.ADMIN_ONLY_ACCESS
            message.answer.assert_awaited_once()
        await engine.dispose()

    asyncio.run(run())


def test_world_reset_keeps_registered_player_recipients():
    async def run():
        from backend.natbirzha.services.world_reset_service import WorldResetService

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with sessions() as session:
            player = User(tg_id=990104, username="player", full_name="Player", role="student")
            session.add(player)
            await session.flush()
            session.add(NatCompany(user_id=player.id, name="Player Corp", specialization="miner", cash=50_000))
            await session.commit()

            preview = await WorldResetService.preview(session)
            assert preview["affected_companies"] == 1
            assert preview["registered_natbirzha_players"] == 1
            await WorldResetService.execute(
                session,
                actor_tg_id=1053722876,
                confirmation=WorldResetService.CONFIRMATION_PHRASE,
            )
            recipients = await PlayerRegistryService.get_registered_tg_ids(session)
            assert recipients == [player.tg_id]
            assert await PlayerRegistryService.register_tg_ids(session, [player.tg_id]) == 0
            assert await session.scalar(select(NatCompany.id)) is None
        await engine.dispose()

    asyncio.run(run())


def test_game_access_commands_are_listed_only_for_admins():
    from backend.bot.services.commands import ADMIN_COMMANDS, STUDENT_COMMANDS

    admin_commands = {command.command for command in ADMIN_COMMANDS}
    student_commands = {command.command for command in STUDENT_COMMANDS}
    assert {"ban", "unban"}.issubset(admin_commands)
    assert "ban" not in student_commands
    assert "unban" not in student_commands


if __name__ == "__main__":
    for test in (
        test_persisted_open_state_overrides_closed_launch_default,
        test_legacy_frontend_toggle_does_not_accidentally_open_admin_only_launch,
        test_ban_and_unban_commands_are_idempotent_and_notify_registered_players,
        test_non_admin_cannot_change_game_access,
        test_world_reset_keeps_registered_player_recipients,
        test_game_access_commands_are_listed_only_for_admins,
    ):
        test()
    print("Admin game ban/unban commands: PASS")
