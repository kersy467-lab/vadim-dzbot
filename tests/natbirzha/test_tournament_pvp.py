"""Tournament-only PvP, losses, ratings, replay, and winner cooldown."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.combat import NatArmyUnit, NatPvpCooldown
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.tournament_service import TournamentError, TournamentService


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessions() as session:
        strong = NatCompany(
            user_id=950001, name="PvP Strong", specialization="metallurgist",
            cash=50_000, territory_tiles=8, military_rating=1000,
        )
        weak = NatCompany(
            user_id=950002, name="PvP Weak", specialization="agrarian",
            cash=50_000, territory_tiles=6, military_rating=1000,
        )
        session.add_all([strong, weak])
        await session.flush()
        session.add_all(
            [
                NatArmyUnit(company_id=strong.id, unit_type="infantry", quantity=500),
                NatArmyUnit(company_id=strong.id, unit_type="tanks", quantity=10),
                NatArmyUnit(company_id=weak.id, unit_type="infantry", quantity=20),
            ]
        )
        await session.commit()

        now = datetime(2026, 9, 19, 12, 0, 0)
        tournament = await TournamentService.create_custom(
            session, now=now, created_by_user_id=999, rewards=(150, 100, 70)
        )
        outsider = NatCompany(
            user_id=950003, name="PvP Outsider", specialization="forester"
        )
        session.add(outsider)
        await session.commit()

        try:
            await TournamentService.attack_player(
                session, tournament.id, strong, strong.id, "pvp:self", now=now
            )
        except TournamentError as exc:
            assert exc.reason == "self_attack"
        else:
            raise AssertionError("Self attacks must be rejected")

        try:
            await TournamentService.attack_player(
                session, tournament.id, strong, outsider.id, "pvp:outsider", now=now
            )
        except TournamentError as exc:
            assert exc.reason == "target_not_participant"
        else:
            raise AssertionError("Non-participants must not be valid targets")

        economic_before = (strong.cash, weak.cash, strong.territory_tiles, weak.territory_tiles)
        result = await TournamentService.attack_player(
            session, tournament.id, strong, weak.id, "pvp:strong:1", now=now
        )
        assert result["winner"] == "attacker"
        cooldown_until = datetime.fromisoformat(result["cooldown_until"])
        assert cooldown_until.utcoffset() is not None
        assert cooldown_until.replace(tzinfo=None) == now + timedelta(hours=2)
        assert strong.military_rating > 1000
        assert weak.military_rating < 1000
        assert (strong.cash, weak.cash, strong.territory_tiles, weak.territory_tiles) == economic_before

        rating_after = (strong.military_rating, weak.military_rating)
        replay = await TournamentService.attack_player(
            session, tournament.id, strong, weak.id, "pvp:strong:1", now=now + timedelta(minutes=1)
        )
        assert replay == result
        assert (strong.military_rating, weak.military_rating) == rating_after

        try:
            await TournamentService.attack_player(
                session, tournament.id, strong, weak.id, "pvp:strong:2", now=now + timedelta(minutes=1)
            )
        except TournamentError as exc:
            assert exc.reason == "cooldown"
        else:
            raise AssertionError("Winning pair must be blocked for two hours")

        # A losing attack creates no attacker->defender cooldown.
        loss = await TournamentService.attack_player(
            session, tournament.id, weak, strong.id, "pvp:weak:1", now=now + timedelta(minutes=2)
        )
        assert loss["winner"] == "defender"
        assert loss["cooldown_until"] is None
        weak_cooldown = await session.scalar(
            select(NatPvpCooldown).where(
                NatPvpCooldown.attacker_company_id == weak.id,
                NatPvpCooldown.defender_company_id == strong.id,
            )
        )
        assert weak_cooldown is None

        after_cooldown = await TournamentService.attack_player(
            session, tournament.id, strong, weak.id, "pvp:strong:3", now=now + timedelta(hours=2)
        )
        assert after_cooldown["winner"] == "attacker"

        tournament.status = "COMPLETED"
        await session.flush()
        try:
            await TournamentService.attack_player(
                session, tournament.id, strong, weak.id, "pvp:closed", now=now + timedelta(hours=3)
            )
        except TournamentError as exc:
            assert exc.reason == "tournament_not_active"
        else:
            raise AssertionError("PvP outside an active tournament must fail")

    await engine.dispose()
    print("NATBIRZHA tournament PvP checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
