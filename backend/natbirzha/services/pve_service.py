"""Transactional PvE corporate wars and territory rewards."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.combat import (
    NatBattle,
    NatBattleSnapshot,
    NatPveCorporation,
    NatPveVictory,
)
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.army_service import ArmyService
from backend.natbirzha.services.combat_resolver import ArmySnapshot, PremiumModifiers, resolve_battle
from backend.natbirzha.services.pve_catalog import PVE_CATALOG_VERSION
from backend.natbirzha.services.rating_service import RatingService
from backend.natbirzha.services.premium_upgrade_service import PremiumUpgradeService
from backend.natbirzha.services.pve_campaign_service import PveCampaignMixin
from backend.natbirzha.services.pve_reward_service import PveRewardService
from backend.natbirzha.services.progression_service import apply_xp
from backend.natbirzha.services.unit_catalog import GROUND_UNITS, UNIT_CATALOG


class PveWarError(ValueError):
    def __init__(self, reason: str, message: str) -> None:
        self.reason = reason
        super().__init__(message)


class PveService(PveCampaignMixin):
    @classmethod
    async def scout_target(
        cls, session: AsyncSession, company: NatCompany, target_code: str
    ) -> dict[str, Any]:
        await cls.ensure_catalog(session)
        target = await session.scalar(
            select(NatPveCorporation).where(
                NatPveCorporation.code == target_code,
                NatPveCorporation.is_active.is_(True),
            )
        )
        if target is None:
            raise PveWarError("target_not_found", "PvE corporation not found")
        army = await ArmyService.snapshot(session, company.id)
        drones = army.units.get("drones", 0)
        campaign_rank = await cls._campaign_wins(session, company.id, target.id)
        defender_units = cls._campaign_snapshot(target.unit_snapshot, campaign_rank)
        strength = cls._snapshot_strength(defender_units)
        if drones >= 20:
            lower = upper = strength
            accuracy = "exact"
        else:
            uncertainty = max(0.05, 0.35 - drones * 0.015)
            lower = round(strength * (1.0 - uncertainty))
            upper = round(strength * (1.0 + uncertainty))
            accuracy = "estimated"
        attacker_modifiers = await PremiumUpgradeService.modifiers(session, company.id)
        army_requirements = cls._army_requirements(target.tier)
        missing_requirements = cls._missing_force_requirements(army, army_requirements)
        defender = ArmySnapshot(units=defender_units)
        defender_modifiers = PremiumModifiers(**target.premium_modifiers)
        simulations = [
            resolve_battle(
                army,
                defender,
                seed=hashlib.sha256(
                    f"scout:{company.id}:{target.id}:{PVE_CATALOG_VERSION}:{index}".encode("utf-8")
                ).hexdigest(),
                attacker_modifiers=attacker_modifiers,
                defender_modifiers=defender_modifiers,
            )
            for index in range(12)
        ]
        expected_losses = {}
        for unit_type in UNIT_CATALOG:
            samples = [result.attacker_losses.get(unit_type, 0) for result in simulations]
            expected_losses[unit_type] = {"min": min(samples), "max": max(samples)}
        total_units = max(1, sum(army.units.values()))
        worst_loss_fraction = sum(row["max"] for row in expected_losses.values()) / total_units
        attacker_win_rate = sum(result.winner == "attacker" for result in simulations) / len(simulations)
        if attacker_win_rate >= 0.9 and worst_loss_fraction <= 0.12:
            risk = "low"
        elif attacker_win_rate >= 0.6:
            risk = "medium"
        elif attacker_win_rate > 0:
            risk = "high"
        else:
            risk = "extreme"
        return {
            "target_code": target.code,
            "target_name": target.name,
            "campaign_rank": campaign_rank,
            "strength_range": {"min": lower, "max": upper},
            "accuracy": accuracy,
            "scouting_drones": drones,
            "known_units": dict(target.unit_snapshot) if accuracy == "exact" else None,
            "territory_reward": target.territory_reward,
            "cash_reward": target.cash_reward,
            "resource_rewards": target.resource_rewards,
            "army_requirements": army_requirements,
            "missing_army_requirements": missing_requirements,
            "risk": risk,
            "expected_losses": expected_losses,
        }

    @staticmethod
    def _snapshot_strength(units: dict[str, int]) -> int:
        return sum(
            quantity * UNIT_CATALOG[unit_type].base_power
            for unit_type, quantity in units.items()
        )

    @staticmethod
    async def _check_access(
        session: AsyncSession, company: NatCompany, target: NatPveCorporation, now: datetime
    ) -> None:
        if not target.is_active:
            raise PveWarError("target_inactive", "PvE corporation is inactive")
        if company.level < target.min_company_level:
            raise PveWarError("company_level", "Company level is too low")
        existing = await session.scalar(
            select(NatPveVictory).where(
                NatPveVictory.company_id == company.id,
                NatPveVictory.pve_corporation_id == target.id,
            )
        )
        if existing is not None:
            available_at = existing.conquered_at + timedelta(hours=nat_settings.PVE_WIN_COOLDOWN_HOURS)
            if available_at > now:
                raise PveWarError("cooldown", f"Target is unavailable until {available_at.isoformat()}")
        if target.prerequisite_code:
            prerequisite = await session.scalar(
                select(NatPveVictory)
                .join(NatPveCorporation, NatPveVictory.pve_corporation_id == NatPveCorporation.id)
                .where(
                    NatPveVictory.company_id == company.id,
                    NatPveCorporation.code == target.prerequisite_code,
                    NatPveVictory.reward_claimed.is_(True),
                )
            )
            if prerequisite is None:
                raise PveWarError("prerequisite", "Previous PvE corporation is not conquered")

    @staticmethod
    async def _apply_resource_rewards(
        session: AsyncSession, company_id: int, rewards: dict[str, float]
    ) -> None:
        for item_id, quantity in rewards.items():
            inventory = await session.scalar(
                select(NatInventory)
                .where(
                    NatInventory.company_id == company_id,
                    NatInventory.item_id == item_id,
                )
                .with_for_update()
            )
            if inventory is None:
                inventory = NatInventory(
                    company_id=company_id,
                    item_id=item_id,
                    quantity=0.0,
                    reserved_quantity=0.0,
                    avg_cost_basis=0.0,
                )
                session.add(inventory)
            inventory.quantity += quantity

    @classmethod
    async def attack_target(
        cls,
        session: AsyncSession,
        company: NatCompany,
        target_code: str,
        operation_key: str,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not operation_key or len(operation_key) > 160:
            raise PveWarError("invalid_operation_key", "Operation key is required")
        existing_battle = await session.scalar(
            select(NatBattle).where(NatBattle.operation_key == operation_key)
        )
        if existing_battle is not None:
            if (
                existing_battle.attacker_company_id != company.id
                or existing_battle.mode != "PVE"
                or existing_battle.summary_json.get("target_code") != target_code
            ):
                raise PveWarError("operation_conflict", "Operation key was reused")
            return existing_battle.summary_json

        now = now or datetime.utcnow()
        await cls.ensure_catalog(session)
        locked_company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
        )
        if locked_company is None:
            raise PveWarError("company_not_found", "Company not found")
        target = await session.scalar(
            select(NatPveCorporation).where(NatPveCorporation.code == target_code)
        )
        if target is None:
            raise PveWarError("target_not_found", "PvE corporation not found")
        await cls._check_access(session, locked_company, target, now)
        campaign_rank = await cls._campaign_wins(session, company.id, target.id)
        attacker = await ArmyService.snapshot(session, company.id, for_update=True)
        if not any(attacker.units.get(unit_type, 0) > 0 for unit_type in GROUND_UNITS):
            raise PveWarError("insufficient_ground_force", "A surviving ground force is required")
        requirements = cls._army_requirements(target.tier)
        missing_requirements = cls._missing_force_requirements(attacker, requirements)
        if missing_requirements:
            raise PveWarError(
                "insufficient_force_composition",
                "Army does not meet the combined-arms requirements for this PvE tier",
            )

        seed = hashlib.sha256(
            f"{operation_key}:{company.id}:{target.id}:{PVE_CATALOG_VERSION}".encode("utf-8")
        ).hexdigest()
        battle = NatBattle(
            operation_key=operation_key,
            mode="PVE",
            attacker_company_id=company.id,
            pve_corporation_id=target.id,
            winner_side=None,
            seed_digest=seed,
            catalog_version=PVE_CATALOG_VERSION,
            summary_json={},
            status="PENDING",
            created_at=now,
        )
        session.add(battle)
        await session.flush()

        defender = ArmySnapshot(units=cls._campaign_snapshot(target.unit_snapshot, campaign_rank))
        defender_modifiers = PremiumModifiers(**target.premium_modifiers)
        attacker_modifiers = await PremiumUpgradeService.modifiers(session, company.id)
        result = resolve_battle(
            attacker,
            defender,
            seed=seed,
            attacker_modifiers=attacker_modifiers,
            defender_modifiers=defender_modifiers,
        )
        session.add_all(
            [
                NatBattleSnapshot(
                    battle_id=battle.id,
                    side="attacker",
                    company_id=company.id,
                    units_json=dict(attacker.units),
                    modifiers_json=attacker_modifiers.__dict__,
                    strength=round(result.attacker_score),
                    created_at=now,
                ),
                NatBattleSnapshot(
                    battle_id=battle.id,
                    side="defender",
                    company_id=None,
                    units_json=dict(defender.units),
                    modifiers_json=target.premium_modifiers,
                    strength=round(result.defender_score),
                    created_at=now,
                ),
            ]
        )
        await ArmyService.apply_losses(session, company.id, result.attacker_losses)
        won = result.winner == "attacker"
        target_rating = 850 + target.tier * 150
        rating_event = await RatingService.apply_battle_result(
            session,
            company.id,
            battle.id,
            won=won,
            opponent_rating=target_rating,
            reason="PVE_WAR",
        )

        territory_awarded = 0
        reward_budget = PveRewardService.cash_reward(
            configured_cap=target.cash_reward, losses=result.attacker_losses
        )
        rewards: dict[str, Any] = {
            "cash": 0.0, "xp": 0, "resources": {}, "recovery": reward_budget
        }
        if won and result.attacker_can_occupy:
            territory_awarded = target.territory_reward if campaign_rank == 0 else 0
            locked_company.territory_tiles += territory_awarded
            locked_company.max_territory = max(
                locked_company.max_territory, locked_company.territory_tiles
            )
            locked_company.cash = round(locked_company.cash + reward_budget["cash"], 2)
            apply_xp(locked_company, target.xp_reward)
            await cls._apply_resource_rewards(
                session, company.id, target.resource_rewards
            )
            victory = await session.scalar(
                select(NatPveVictory).where(
                    NatPveVictory.company_id == company.id,
                    NatPveVictory.pve_corporation_id == target.id,
                ).with_for_update()
            )
            if victory is None:
                session.add(NatPveVictory(
                    company_id=company.id, pve_corporation_id=target.id, battle_id=battle.id,
                    reward_claimed=True, conquered_at=now,
                ))
            else:
                victory.battle_id = battle.id
                victory.reward_claimed = True
                victory.conquered_at = now
            rewards = {
                "cash": reward_budget["cash"],
                "xp": target.xp_reward,
                "resources": target.resource_rewards,
                "recovery": reward_budget,
            }

        summary = {
            "battle_id": battle.id,
            "mode": "PVE",
            "target_code": target.code,
            "target_name": target.name,
            "campaign_rank": campaign_rank,
            "winner": result.winner,
            "attacker_score": result.attacker_score,
            "defender_score": result.defender_score,
            "attacker_losses": dict(result.attacker_losses),
            "defender_losses": dict(result.defender_losses),
            "attacker_remaining": {
                unit_type: quantity - result.attacker_losses.get(unit_type, 0)
                for unit_type, quantity in attacker.units.items()
            },
            "defender_remaining": {
                unit_type: quantity - result.defender_losses.get(unit_type, 0)
                for unit_type, quantity in defender.units.items()
            },
            "phases": {name: dict(values) for name, values in result.phases.items()},
            "territory_awarded": territory_awarded,
            "rewards": rewards,
            "rating_before": rating_event.rating_before,
            "rating_after": rating_event.rating_after,
            "rating_delta": rating_event.delta,
            "resolved_at": now.isoformat(),
        }
        battle.winner_side = result.winner
        battle.summary_json = summary
        battle.status = "RESOLVED"
        battle.resolved_at = now
        await session.flush()
        return summary

    @staticmethod
    async def battle_history(
        session: AsyncSession, company_id: int, *, limit: int = 50
    ) -> list[dict[str, Any]]:
        rows = (
            await session.execute(
                select(NatBattle)
                .where(
                    or_(
                        NatBattle.attacker_company_id == company_id,
                        NatBattle.defender_company_id == company_id,
                    )
                )
                .order_by(NatBattle.id.desc())
                .limit(min(max(limit, 1), 200))
            )
        ).scalars().all()
        return [row.summary_json for row in rows]
