"""PvE campaign catalog, gates and repeat-frontier scaling."""

from __future__ import annotations

from datetime import datetime, timedelta
from math import ceil
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.combat import NatBattle, NatPveCorporation, NatPveVictory
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.army_service import ArmyService
from backend.natbirzha.services.combat_resolver import ArmySnapshot
from backend.natbirzha.services.pve_catalog import (
    PVE_CATALOG_VERSION,
    PVE_CORPORATIONS,
    PVE_FORCE_REQUIREMENTS,
)
from backend.natbirzha.services.unit_catalog import GROUND_UNITS


class PveCampaignMixin:
    @staticmethod
    def _army_requirements(tier: int) -> dict[str, int]:
        return dict(PVE_FORCE_REQUIREMENTS.get(tier, {}))

    @staticmethod
    def _missing_force_requirements(
        army: ArmySnapshot, requirements: dict[str, int]
    ) -> dict[str, dict[str, int]]:
        missing: dict[str, dict[str, int]] = {}
        for key, required in requirements.items():
            current = (
                sum(army.units.get(unit_type, 0) for unit_type in GROUND_UNITS)
                if key == "ground_total"
                else army.units.get(key, 0)
            )
            if current < required:
                missing[key] = {
                    "required": required,
                    "current": current,
                    "missing": required - current,
                }
        return missing

    @staticmethod
    def _campaign_multiplier(wins: int) -> float:
        return round(1.0 + 0.18 * wins + 0.02 * wins * wins, 4)

    @classmethod
    def _campaign_snapshot(cls, base_units: dict[str, int], wins: int) -> dict[str, int]:
        multiplier = cls._campaign_multiplier(wins)
        return {unit: max(1, ceil(count * multiplier)) for unit, count in base_units.items()}

    @staticmethod
    async def _campaign_wins(session: AsyncSession, company_id: int, target_id: int) -> int:
        rows = await session.execute(
            select(NatBattle.id).where(
                NatBattle.attacker_company_id == company_id,
                NatBattle.pve_corporation_id == target_id,
                NatBattle.mode == "PVE",
                NatBattle.winner_side == "attacker",
                NatBattle.status == "RESOLVED",
            )
        )
        return len(rows.scalars().all())

    @staticmethod
    async def ensure_catalog(session: AsyncSession) -> None:
        codes = [spec["code"] for spec in PVE_CORPORATIONS]
        existing_rows = (
            await session.execute(
                select(NatPveCorporation).where(NatPveCorporation.code.in_(codes))
            )
        ).scalars().all()
        by_code = {row.code: row for row in existing_rows}
        for spec in PVE_CORPORATIONS:
            row = by_code.get(spec["code"])
            values = dict(spec)
            if row is None:
                session.add(
                    NatPveCorporation(
                        **values,
                        catalog_version=PVE_CATALOG_VERSION,
                        is_active=True,
                    )
                )
                continue
            for key, value in values.items():
                setattr(row, key, value)
            row.catalog_version = PVE_CATALOG_VERSION
            row.is_active = True
        await session.flush()

    @staticmethod
    async def _victory_codes(session: AsyncSession, company_id: int) -> set[str]:
        rows = (
            await session.execute(
                select(NatPveCorporation.code)
                .join(NatPveVictory, NatPveVictory.pve_corporation_id == NatPveCorporation.id)
                .where(
                    NatPveVictory.company_id == company_id,
                    NatPveVictory.reward_claimed.is_(True),
                )
            )
        ).scalars().all()
        return set(rows)

    @classmethod
    async def list_targets(cls, session: AsyncSession, company: NatCompany) -> list[dict[str, Any]]:
        await cls.ensure_catalog(session)
        victories = await cls._victory_codes(session, company.id)
        victory_rows = (
            await session.execute(select(NatPveVictory).where(NatPveVictory.company_id == company.id))
        ).scalars().all()
        victory_by_target = {row.pve_corporation_id: row for row in victory_rows}
        now = datetime.utcnow()
        army = await ArmyService.snapshot(session, company.id)
        targets = (
            await session.execute(
                select(NatPveCorporation)
                .where(NatPveCorporation.is_active.is_(True))
                .order_by(NatPveCorporation.tier, NatPveCorporation.id)
            )
        ).scalars().all()
        result: list[dict[str, Any]] = []
        for target in targets:
            campaign_rank = await cls._campaign_wins(session, company.id, target.id)
            campaign_snapshot = cls._campaign_snapshot(target.unit_snapshot, campaign_rank)
            conquered = target.code in victories
            latest_victory = victory_by_target.get(target.id)
            cooldown_until = (
                latest_victory.conquered_at + timedelta(hours=nat_settings.PVE_WIN_COOLDOWN_HOURS)
                if latest_victory
                else None
            )
            army_requirements = cls._army_requirements(target.tier)
            missing_requirements = cls._missing_force_requirements(army, army_requirements)
            reason = None
            if cooldown_until and cooldown_until > now:
                reason = "cooldown"
            elif company.level < target.min_company_level:
                reason = "company_level"
            elif target.prerequisite_code and target.prerequisite_code not in victories:
                reason = "prerequisite"
            elif missing_requirements:
                reason = "force_composition"
            strength = cls._snapshot_strength(campaign_snapshot)
            result.append(
                {
                    "code": target.code,
                    "name": target.name,
                    "industry": target.industry,
                    "tier": target.tier,
                    "min_company_level": target.min_company_level,
                    "prerequisite_code": target.prerequisite_code,
                    "territory_reward": target.territory_reward,
                    "cash_reward": target.cash_reward,
                    "xp_reward": target.xp_reward,
                    "campaign_rank": campaign_rank,
                    "repeatable": campaign_rank > 0,
                    "approximate_strength": strength,
                    "strength_range": {"min": round(strength * 0.75), "max": round(strength * 1.25)},
                    "army_requirements": army_requirements,
                    "missing_army_requirements": missing_requirements,
                    "conquered": conquered,
                    "cooldown_until": cooldown_until.isoformat() if cooldown_until else None,
                    "available": reason is None,
                    "unavailable_reason": reason,
                }
            )
        return result


__all__ = ["PveCampaignMixin"]
