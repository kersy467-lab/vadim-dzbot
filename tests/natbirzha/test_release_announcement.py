"""NATBIRZHA 1.5 sends one formatted group post and two DMs per player."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, ClassSetting, User
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.player_registry_service import PlayerRegistryService
from backend.natbirzha.services.release_announcement import (
    BONUS_MESSAGE,
    RELEASE_KEY,
    RELEASE_MESSAGE,
    send_natbirzha_v1_5_announcement,
)


class RecordingBot:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_message(self, **kwargs) -> None:
        self.messages.append(kwargs)


def test_release_announcement_sends_patch_and_bonus_once() -> None:
    async def scenario() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            user = User(tg_id=801, full_name="Release Player", role="student")
            registered_only = User(tg_id=802, full_name="Registered Player", role="student")
            session.add_all([user, registered_only])
            await session.flush()
            session.add(NatCompany(
                user_id=user.id,
                name="Release Corp",
                specialization="mining",
                cash=50_000,
            ))
            await PlayerRegistryService.register_tg_ids(session, [802])
            await session.commit()

        bot = RecordingBot()
        first = await send_natbirzha_v1_5_announcement(bot, sessions)
        assert first == {"group_sent": True, "dms_sent": 2, "dms_failed": 0, "skipped": False}
        assert [message["text"] for message in bot.messages] == [
            RELEASE_MESSAGE, BONUS_MESSAGE,
            RELEASE_MESSAGE, BONUS_MESSAGE,
            RELEASE_MESSAGE, BONUS_MESSAGE,
        ]
        assert [message["chat_id"] for message in bot.messages] == [
            -1004491945174, -1004491945174,
            801, 801,
            802, 802,
        ]
        assert bot.messages[0]["parse_mode"] == "HTML"
        assert bot.messages[1]["parse_mode"] is None

        second = await send_natbirzha_v1_5_announcement(bot, sessions)
        assert second["skipped"] is True, second
        assert len(bot.messages) == 6
        async with sessions() as session:
            marker = await session.get(ClassSetting, RELEASE_KEY)
            assert '"status": "COMPLETE"' in marker.value, marker.value

        await engine.dispose()

    asyncio.run(scenario())


if __name__ == "__main__":
    test_release_announcement_sends_patch_and_bonus_once()
    print("NATBIRZHA 1.5 announcement delivery checks: PASS")
