"""Immutable military-rating changes derived from battle outcomes."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.combat import NatMilitaryRatingEvent
from backend.natbirzha.models.company import NatCompany


class RatingService:
    @staticmethod
    def calculate_delta(rating: int, opponent_rating: int, won: bool) -> int:
        expected = 1.0 / (1.0 + 10 ** ((opponent_rating - rating) / 400.0))
        raw = round(32 * ((1.0 if won else 0.0) - expected))
        magnitude = min(35, max(5, abs(raw)))
        return magnitude if won else -magnitude

    @classmethod
    async def apply_battle_result(
        cls,
        session: AsyncSession,
        company_id: int,
        battle_id: int,
        *,
        won: bool,
        opponent_rating: int,
        reason: str,
    ) -> NatMilitaryRatingEvent:
        existing = await session.scalar(
            select(NatMilitaryRatingEvent).where(
                NatMilitaryRatingEvent.battle_id == battle_id,
                NatMilitaryRatingEvent.company_id == company_id,
            )
        )
        if existing is not None:
            return existing
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if company is None:
            raise ValueError("Company not found")
        before = company.military_rating
        delta = cls.calculate_delta(before, opponent_rating, won)
        company.military_rating = max(0, before + delta)
        event = NatMilitaryRatingEvent(
            battle_id=battle_id,
            company_id=company_id,
            rating_before=before,
            rating_after=company.military_rating,
            delta=company.military_rating - before,
            reason=reason,
        )
        session.add(event)
        await session.flush()
        return event

