"""PvP combat and target discovery for NATBIRZHA tournaments."""

from datetime import datetime, timedelta
import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import game_dt_iso
from backend.natbirzha.models.combat import NatBattle, NatBattleSnapshot, NatPvpCooldown
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.military import NatTournament, NatTournamentParticipant
from backend.natbirzha.services.army_service import ArmyService
from backend.natbirzha.services.combat_resolver import resolve_battle
from backend.natbirzha.services.military_infrastructure_service import MilitaryInfrastructureService
from backend.natbirzha.services.premium_upgrade_service import PremiumUpgradeService
from backend.natbirzha.services.rating_service import RatingService


class TournamentError(ValueError):
    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


class TournamentCombatMixin:
    @staticmethod
    async def _participant(
        session: AsyncSession, tournament_id: int, company_id: int, *, for_update: bool = False
    ) -> NatTournamentParticipant | None:
        statement = select(NatTournamentParticipant).where(
            NatTournamentParticipant.tournament_id == tournament_id,
            NatTournamentParticipant.company_id == company_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    @classmethod
    async def attack_player(
        cls, session: AsyncSession, tournament_id: int, attacker_company: NatCompany,
        defender_company_id: int, operation_key: str, *, now: datetime,
    ) -> dict[str, Any]:
        if attacker_company.id == defender_company_id:
            raise TournamentError("self_attack", "A company cannot attack itself")
        if not operation_key or len(operation_key) > 160:
            raise TournamentError("invalid_operation_key", "Operation key is required")
        existing = await session.scalar(select(NatBattle).where(NatBattle.operation_key == operation_key))
        if existing is not None:
            if (
                existing.mode != "PVP" or existing.tournament_id != tournament_id
                or existing.attacker_company_id != attacker_company.id
                or existing.defender_company_id != defender_company_id
            ):
                raise TournamentError("operation_conflict", "Operation key was reused")
            return existing.summary_json

        tournament = await session.scalar(
            select(NatTournament).where(NatTournament.id == tournament_id).with_for_update()
        )
        if tournament is None:
            raise TournamentError("tournament_not_found", "Tournament not found")
        if tournament.status != "ACTIVE" or not (tournament.start_time <= now < tournament.finish_time):
            raise TournamentError("tournament_not_active", "PvP is available only during an active tournament")
        attacker_participant = await cls._participant(session, tournament_id, attacker_company.id, for_update=True)
        defender_participant = await cls._participant(session, tournament_id, defender_company_id, for_update=True)
        if attacker_participant is None:
            raise TournamentError("attacker_not_participant", "Attacker is not a tournament participant")
        if defender_participant is None:
            raise TournamentError("target_not_participant", "Target is not a tournament participant")

        locked = (await session.execute(
            select(NatCompany).where(NatCompany.id.in_(sorted((attacker_company.id, defender_company_id))))
            .order_by(NatCompany.id).with_for_update()
        )).scalars().all()
        if len(locked) != 2:
            raise TournamentError("target_not_found", "Target company not found")
        companies = {company.id: company for company in locked}
        attacker_locked, defender_locked = companies[attacker_company.id], companies[defender_company_id]
        cooldown = await session.scalar(
            select(NatPvpCooldown).where(
                NatPvpCooldown.tournament_id == tournament_id,
                NatPvpCooldown.attacker_company_id == attacker_company.id,
                NatPvpCooldown.defender_company_id == defender_company_id,
            ).with_for_update()
        )
        if cooldown is not None and cooldown.available_at > now:
            raise TournamentError("cooldown", f"Target is unavailable until {cooldown.available_at.isoformat()}")

        for company_id in (attacker_company.id, defender_company_id):
            await MilitaryInfrastructureService.settle_training(session, company_id, now=now)
            await MilitaryInfrastructureService.recover_readiness(session, company_id, now=now)
        attacker_army = await ArmyService.snapshot(session, attacker_company.id, for_update=True)
        defender_army = await ArmyService.snapshot(session, defender_company_id, for_update=True)
        if sum(attacker_army.units.values()) <= 0:
            raise TournamentError("empty_army", "Attacker has no army")
        if sum(defender_army.units.values()) <= 0:
            raise TournamentError("target_empty_army", "Target has no army")
        try:
            operation_supply = await MilitaryInfrastructureService.consume_operation_supply(
                session, attacker_company.id, attacker_army
            )
        except ValueError as exc:
            raise TournamentError("insufficient_supply", str(exc)) from exc

        seed = hashlib.sha256(
            f"{operation_key}:{tournament_id}:{attacker_company.id}:{defender_company_id}".encode()
        ).hexdigest()
        battle = NatBattle(
            operation_key=operation_key, mode="PVP", attacker_company_id=attacker_company.id,
            defender_company_id=defender_company_id, tournament_id=tournament_id,
            seed_digest=seed, catalog_version="p2-v1", summary_json={}, status="PENDING", created_at=now,
        )
        session.add(battle)
        await session.flush()
        attacker_modifiers = await PremiumUpgradeService.modifiers(session, attacker_company.id)
        defender_modifiers = await PremiumUpgradeService.modifiers(session, defender_company_id)
        result = resolve_battle(
            attacker_army, defender_army, seed=seed,
            attacker_modifiers=attacker_modifiers, defender_modifiers=defender_modifiers,
        )
        session.add_all([
            NatBattleSnapshot(
                battle_id=battle.id, side="attacker", company_id=attacker_company.id,
                units_json=dict(attacker_army.units), modifiers_json=attacker_modifiers.__dict__,
                strength=round(result.attacker_score), created_at=now,
            ),
            NatBattleSnapshot(
                battle_id=battle.id, side="defender", company_id=defender_company_id,
                units_json=dict(defender_army.units), modifiers_json=defender_modifiers.__dict__,
                strength=round(result.defender_score), created_at=now,
            ),
        ])
        await ArmyService.apply_losses(session, attacker_company.id, result.attacker_losses)
        await ArmyService.apply_losses(session, defender_company_id, result.defender_losses)
        attacker_total = max(1, sum(map(int, attacker_army.units.values())))
        defender_total = max(1, sum(map(int, defender_army.units.values())))
        await MilitaryInfrastructureService.reduce_readiness_after_operation(
            session, attacker_company.id,
            loss_ratio=sum(map(int, result.attacker_losses.values())) / attacker_total,
        )
        await MilitaryInfrastructureService.reduce_readiness_after_operation(
            session, defender_company_id,
            loss_ratio=sum(map(int, result.defender_losses.values())) / defender_total,
        )
        attacker_won = result.winner == "attacker"
        attacker_rating = await RatingService.apply_battle_result(
            session, attacker_company.id, battle.id, won=attacker_won,
            opponent_rating=defender_locked.military_rating, reason="TOURNAMENT_PVP",
        )
        defender_rating = await RatingService.apply_battle_result(
            session, defender_company_id, battle.id, won=not attacker_won,
            opponent_rating=attacker_locked.military_rating, reason="TOURNAMENT_PVP",
        )
        if attacker_won:
            attacker_participant.wins += 1; defender_participant.losses += 1
        else:
            attacker_participant.losses += 1; defender_participant.wins += 1

        cooldown_until = None
        if attacker_won:
            cooldown_until = now + timedelta(hours=2)
            if cooldown is None:
                cooldown = NatPvpCooldown(
                    tournament_id=tournament_id, attacker_company_id=attacker_company.id,
                    defender_company_id=defender_company_id, battle_id=battle.id,
                    available_at=cooldown_until, created_at=now,
                )
                session.add(cooldown)
            else:
                cooldown.battle_id = battle.id; cooldown.available_at = cooldown_until
        summary = {
            "battle_id": battle.id, "mode": "PVP", "tournament_id": tournament_id,
            "attacker_company_id": attacker_company.id, "defender_company_id": defender_company_id,
            "winner": result.winner, "attacker_score": result.attacker_score,
            "defender_score": result.defender_score,
            "attacker_losses": dict(result.attacker_losses), "defender_losses": dict(result.defender_losses),
            "attacker_remaining": {k: v - result.attacker_losses.get(k, 0) for k, v in attacker_army.units.items()},
            "defender_remaining": {k: v - result.defender_losses.get(k, 0) for k, v in defender_army.units.items()},
            "phases": {name: dict(values) for name, values in result.phases.items()},
            "operation_supply": operation_supply, "attacker_rating_delta": attacker_rating.delta,
            "defender_rating_delta": defender_rating.delta,
            "cooldown_until": game_dt_iso(cooldown_until), "resolved_at": game_dt_iso(now),
        }
        battle.winner_side = result.winner; battle.summary_json = summary
        battle.status = "RESOLVED"; battle.resolved_at = now
        await session.flush()
        return summary

    @classmethod
    async def pvp_targets(
        cls, session: AsyncSession, tournament_id: int, company_id: int, *, now: datetime,
    ) -> list[dict[str, Any]]:
        rows = (await session.execute(
            select(NatTournamentParticipant, NatCompany)
            .join(NatCompany, NatCompany.id == NatTournamentParticipant.company_id)
            .where(
                NatTournamentParticipant.tournament_id == tournament_id,
                NatTournamentParticipant.company_id != company_id,
            ).order_by(NatCompany.military_rating.desc())
        )).all()
        cooldowns = (await session.execute(
            select(NatPvpCooldown).where(
                NatPvpCooldown.tournament_id == tournament_id,
                NatPvpCooldown.attacker_company_id == company_id,
            )
        )).scalars().all()
        by_target = {row.defender_company_id: row.available_at for row in cooldowns}
        targets = []
        for participant, company in rows:
            status = await ArmyService.compatibility_status(session, company.id)
            cooldown_until = by_target.get(company.id)
            targets.append({
                "company_id": company.id, "company_name": company.name,
                "rating": company.military_rating, "approximate_strength": status["army_strength"],
                "wins": participant.wins, "losses": participant.losses,
                "cooldown_until": game_dt_iso(cooldown_until),
                "attack_available": cooldown_until is None or cooldown_until <= now,
            })
        return targets


__all__ = ["TournamentCombatMixin", "TournamentError"]
