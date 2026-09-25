"""Restart-safe 72-hour tournament cadence and 18-hour event lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.alliances import NatAllianceMember
from backend.natbirzha.models.military import NatTournament, NatTournamentParticipant
from backend.natbirzha.services.army_service import ArmyService
from backend.natbirzha.services.premium_service import PremiumService
from backend.natbirzha.services.tournament_combat import TournamentCombatMixin, TournamentError
from backend.natbirzha.services.tournament_registration import TournamentRegistrationMixin
from backend.natbirzha.config import game_dt_iso, normalize_dt


TOURNAMENT_CADENCE = timedelta(hours=72)
TOURNAMENT_DURATION = timedelta(hours=18)
DEFAULT_REWARDS = (150, 100, 70)


class TournamentService(TournamentRegistrationMixin, TournamentCombatMixin):
    @staticmethod
    async def _next_number(session: AsyncSession) -> int:
        current = await session.scalar(select(func.max(NatTournament.tournament_number)))
        return int(current or 0) + 1

    @classmethod
    async def ensure_next_scheduled(
        cls, session: AsyncSession, now: datetime
    ) -> NatTournament:
        existing = await session.scalar(
            select(NatTournament)
            .where(
                NatTournament.tournament_type == "AUTO",
                NatTournament.status.in_(("SCHEDULED", "ACTIVE", "RESOLVING")),
            )
            .order_by(NatTournament.start_time.desc())
            .limit(1)
        )
        if existing is not None:
            return existing
        latest = await session.scalar(
            select(NatTournament)
            .where(NatTournament.tournament_type == "AUTO")
            .order_by(NatTournament.start_time.desc())
            .limit(1)
        )
        start_time = now if latest is None else latest.start_time + TOURNAMENT_CADENCE
        tournament = NatTournament(
            tournament_number=await cls._next_number(session),
            start_time=start_time,
            snapshot_time=start_time,
            finish_time=start_time + TOURNAMENT_DURATION,
            status="SCHEDULED",
            prize_pool_nat=0,
            tournament_type="AUTO",
            reward_first_pvc=DEFAULT_REWARDS[0],
            reward_second_pvc=DEFAULT_REWARDS[1],
            reward_third_pvc=DEFAULT_REWARDS[2],
        )
        session.add(tournament)
        await session.flush()
        return tournament

    @classmethod
    async def _snapshot_participants(
        cls, session: AsyncSession, tournament: NatTournament, now: datetime
    ) -> None:
        existing_rows = (
            await session.execute(
                select(NatTournamentParticipant)
                .where(NatTournamentParticipant.tournament_id == tournament.id)
                .with_for_update()
            )
        ).scalars().all()
        existing_by_company = {row.company_id: row for row in existing_rows}
        companies = (
            await session.execute(
                select(NatCompany)
                .where(NatCompany.is_bankrupt.is_(False))
                .order_by(NatCompany.id)
            )
        ).scalars().all()
        alliance_by_company = dict(
            (
                await session.execute(
                    select(NatAllianceMember.company_id, NatAllianceMember.alliance_id)
                )
            ).all()
        )
        for company in companies:
            status = await ArmyService.compatibility_status(session, company.id)
            if status["army_strength"] <= 0:
                continue
            strength = status["army_strength"]
            participant = existing_by_company.get(company.id)
            if participant is not None:
                participant.alliance_id = alliance_by_company.get(company.id)
                participant.snapshot_strength = strength
                participant.initial_strength = strength
                participant.final_strength = strength
                participant.initial_rating = company.military_rating
                participant.final_rating = company.military_rating
                participant.army_updated_at = now
                continue
            session.add(NatTournamentParticipant(
                tournament_id=tournament.id,
                company_id=company.id,
                alliance_id=alliance_by_company.get(company.id),
                snapshot_strength=strength,
                initial_strength=strength,
                final_strength=strength,
                initial_rating=company.military_rating,
                final_rating=company.military_rating,
                wins=0,
                losses=0,
                army_updated_at=now,
            ))
        await session.flush()

    @classmethod
    async def activate_due(
        cls, session: AsyncSession, now: datetime
    ) -> list[NatTournament]:
        tournaments = (
            await session.execute(
                select(NatTournament)
                .where(
                    NatTournament.status.in_(("SCHEDULED", "PENDING")),
                    NatTournament.start_time <= now,
                )
                .order_by(NatTournament.start_time)
                .with_for_update()
            )
        ).scalars().all()
        for tournament in tournaments:
            tournament.status = "ACTIVE"
            tournament.snapshot_time = now
            await cls._snapshot_participants(session, tournament, now)
        await session.flush()
        return tournaments

    @classmethod
    async def create_custom(
        cls,
        session: AsyncSession,
        *,
        now: datetime,
        created_by_user_id: int,
        rewards: tuple[int, int, int],
    ) -> NatTournament:
        if len(rewards) != 3 or any(
            isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000
            for value in rewards
        ):
            raise ValueError("Custom tournament requires three integer PVC rewards from 0 to 10000")
        tournament = NatTournament(
            tournament_number=await cls._next_number(session),
            start_time=now,
            snapshot_time=now,
            finish_time=now + TOURNAMENT_DURATION,
            status="ACTIVE",
            prize_pool_nat=0,
            tournament_type="CUSTOM",
            reward_first_pvc=rewards[0],
            reward_second_pvc=rewards[1],
            reward_third_pvc=rewards[2],
            created_by_user_id=created_by_user_id,
        )
        session.add(tournament)
        await session.flush()
        await cls._snapshot_participants(session, tournament, now)
        return tournament

    @classmethod
    async def leaderboard(
        cls, session: AsyncSession, tournament_id: int
    ) -> list[dict[str, Any]]:
        rows = (
            await session.execute(
                select(NatTournamentParticipant, NatCompany)
                .join(NatCompany, NatCompany.id == NatTournamentParticipant.company_id)
                .where(NatTournamentParticipant.tournament_id == tournament_id)
            )
        ).all()
        result = []
        for participant, company in rows:
            status = await ArmyService.compatibility_status(session, company.id)
            result.append(
                {
                    "company_id": company.id,
                    "company_name": company.name,
                    "current_strength": status["army_strength"],
                    "initial_strength": participant.initial_strength,
                    "final_strength": participant.final_strength,
                    "rating": company.military_rating,
                    "wins": participant.wins,
                    "losses": participant.losses,
                    "rank": participant.final_rank,
                    "prize_pvc": participant.prize_pvc,
                }
            )
        return sorted(result, key=lambda row: (-row["current_strength"], row["company_id"]))

    @staticmethod
    def _reward_for_rank(tournament: NatTournament, rank: int) -> int:
        return {
            1: tournament.reward_first_pvc,
            2: tournament.reward_second_pvc,
            3: tournament.reward_third_pvc,
        }.get(rank, 0)

    @staticmethod
    async def _serialize_result(
        session: AsyncSession, tournament: NatTournament
    ) -> dict[str, Any]:
        rows = (
            await session.execute(
                select(NatTournamentParticipant, NatCompany)
                .join(NatCompany, NatCompany.id == NatTournamentParticipant.company_id)
                .where(NatTournamentParticipant.tournament_id == tournament.id)
                .order_by(
                    NatTournamentParticipant.final_rank.asc(),
                    NatTournamentParticipant.final_strength.desc(),
                    NatTournamentParticipant.company_id.asc(),
                )
            )
        ).all()
        ranking = [
            {
                "company_id": company.id,
                "company_name": company.name,
                "rank": participant.final_rank,
                "strength": participant.final_strength,
                "rating": participant.final_rating,
                "wins": participant.wins,
                "losses": participant.losses,
                "prize_pvc": participant.prize_pvc,
            }
            for participant, company in rows
        ]
        winner = ranking[0] if ranking else None
        return {
            "status": "completed" if ranking else "no_participants",
            "tournament_id": tournament.id,
            "tournament_number": tournament.tournament_number,
            "tournament_type": tournament.tournament_type,
            "winner_company_id": winner["company_id"] if winner else None,
            "winner_name": winner["company_name"] if winner else None,
            "winner_strength": winner["strength"] if winner else 0,
            "prize_awarded_nat": tournament.prize_pool_nat if winner else 0,
            "top_three": [row for row in ranking if row["rank"] and row["rank"] <= 3],
            "ranking": ranking,
        }

    @classmethod
    async def history(
        cls, session: AsyncSession, company_id: int, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Return completed tournaments with immutable results and the caller's own line."""
        tournaments = (
            await session.execute(
                select(NatTournament)
                .where(NatTournament.status == "COMPLETED")
                .order_by(NatTournament.resolved_at.desc(), NatTournament.id.desc())
                .limit(max(1, min(limit, 50)))
            )
        ).scalars().all()
        history = []
        for tournament in tournaments:
            result = await cls._serialize_result(session, tournament)
            ranking = result["ranking"]
            history.append(
                {
                    "tournament_id": tournament.id,
                    "tournament_number": tournament.tournament_number,
                    "tournament_type": tournament.tournament_type,
                    "start_time": game_dt_iso(tournament.start_time),
                    "finish_time": game_dt_iso(tournament.finish_time),
                    "resolved_at": game_dt_iso(tournament.resolved_at),
                    "top_three": result["top_three"],
                    "my_participation": next(
                        (row for row in ranking if row["company_id"] == company_id), None
                    ),
                }
            )
        return history

    @classmethod
    async def resolve(
        cls,
        session: AsyncSession,
        tournament_id: int,
        *,
        now: datetime,
        force: bool = False,
    ) -> dict[str, Any]:
        tournament = await session.scalar(
            select(NatTournament)
            .where(NatTournament.id == tournament_id)
            .with_for_update()
        )
        if tournament is None:
            raise ValueError("Tournament not found")
        if tournament.status == "COMPLETED":
            return await cls._serialize_result(session, tournament)
        if not force and normalize_dt(now) < normalize_dt(tournament.finish_time):
            raise ValueError("Tournament is still active")
        if tournament.status in {"SCHEDULED", "PENDING"}:
            await cls._snapshot_participants(session, tournament, tournament.start_time)
        tournament.status = "RESOLVING"
        await session.flush()

        participants = (
            await session.execute(
                select(NatTournamentParticipant)
                .where(NatTournamentParticipant.tournament_id == tournament.id)
                .order_by(NatTournamentParticipant.company_id)
                .with_for_update()
            )
        ).scalars().all()
        scored: list[NatTournamentParticipant] = []
        for participant in participants:
            company = await session.get(NatCompany, participant.company_id)
            status = await ArmyService.compatibility_status(session, participant.company_id)
            participant.final_strength = status["army_strength"]
            participant.final_rating = company.military_rating if company else participant.initial_rating
            scored.append(participant)
        scored.sort(key=lambda row: (-row.final_strength, row.company_id))

        previous_strength: int | None = None
        current_rank = 0
        for position, participant in enumerate(scored, start=1):
            if previous_strength is None or participant.final_strength != previous_strength:
                current_rank = position
            participant.final_rank = current_rank
            previous_strength = participant.final_strength
            prize = cls._reward_for_rank(tournament, current_rank)
            participant.prize_pvc = prize
            if prize:
                await PremiumService.apply_pvc(
                    session,
                    participant.company_id,
                    prize,
                    "tournament_reward",
                    f"tournament:{tournament.id}:reward:{participant.company_id}",
                    {"tournament_id": tournament.id, "rank": current_rank},
                )

        if scored and tournament.prize_pool_nat > 0:
            legacy_winner = await session.get(NatCompany, scored[0].company_id)
            if legacy_winner is not None:
                legacy_winner.nat_balance += tournament.prize_pool_nat
                scored[0].prize_nat = tournament.prize_pool_nat
        tournament.status = "COMPLETED"
        tournament.resolved_at = now
        await session.flush()
        return await cls._serialize_result(session, tournament)

    @classmethod
    async def tick(cls, session: AsyncSession, now: datetime) -> dict[str, int]:
        await cls.ensure_next_scheduled(session, now)
        activated = await cls.activate_due(session, now)
        due = (
            await session.execute(
                select(NatTournament).where(
                    NatTournament.status.in_(("ACTIVE", "RESOLVING")),
                    NatTournament.finish_time <= now,
                )
            )
        ).scalars().all()
        for tournament in due:
            await cls.resolve(session, tournament.id, now=now)
        await cls.ensure_next_scheduled(session, now)
        return {"activated": len(activated), "resolved": len(due)}
