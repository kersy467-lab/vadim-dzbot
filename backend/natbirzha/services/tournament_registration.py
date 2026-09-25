"""Explicit player registration for scheduled and active tournaments."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.alliances import NatAllianceMember
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.military import NatTournament, NatTournamentParticipant
from backend.natbirzha.services.army_service import ArmyService
from backend.natbirzha.config import normalize_dt
from backend.natbirzha.services.tournament_combat import TournamentError


class TournamentRegistrationMixin:
    @classmethod
    async def join(
        cls,
        session: AsyncSession,
        tournament_id: int,
        company: NatCompany,
        *,
        now: datetime,
    ) -> dict[str, Any]:
        tournament = await session.scalar(
            select(NatTournament)
            .where(NatTournament.id == tournament_id)
            .with_for_update()
        )
        if tournament is None:
            raise TournamentError("tournament_not_found", "Tournament not found")
        if tournament.status not in {"PENDING", "SCHEDULED", "ACTIVE"} or normalize_dt(now) >= normalize_dt(tournament.finish_time):
            raise TournamentError("tournament_not_active", "Tournament registration is closed")

        existing = await session.scalar(
            select(NatTournamentParticipant)
            .where(
                NatTournamentParticipant.tournament_id == tournament_id,
                NatTournamentParticipant.company_id == company.id,
            )
            .with_for_update()
        )
        if existing is not None:
            return {
                "joined": True,
                "already_joined": True,
                "tournament_id": tournament_id,
                "message": "Ваша компания уже участвует в турнире",
            }
        if company.is_bankrupt:
            raise TournamentError("company_ineligible", "Банкрот не может участвовать в турнире")

        army = await ArmyService.compatibility_status(session, company.id)
        strength = int(army["army_strength"])
        if strength <= 0:
            raise TournamentError("empty_army", "Сначала сформируйте армию")

        alliance_id = await session.scalar(
            select(NatAllianceMember.alliance_id).where(
                NatAllianceMember.company_id == company.id
            )
        )
        session.add(
            NatTournamentParticipant(
                tournament_id=tournament_id,
                company_id=company.id,
                alliance_id=alliance_id,
                snapshot_strength=strength,
                initial_strength=strength,
                final_strength=strength,
                initial_rating=company.military_rating,
                final_rating=company.military_rating,
                wins=0,
                losses=0,
                army_updated_at=now,
            )
        )
        await session.flush()
        return {
            "joined": True,
            "already_joined": False,
            "tournament_id": tournament_id,
            "message": "Вы зарегистрировались в турнире",
        }
