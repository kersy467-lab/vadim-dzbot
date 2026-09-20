from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.creator import NatStateTreasury


class StateTreasuryService:
    """Single authoritative state treasury row, isolated from player companies."""

    TREASURY_ID = 1
    INITIAL_CASH = 10_000_000.0

    @classmethod
    async def get_or_create(
        cls,
        session: AsyncSession,
        *,
        commit: bool = True,
        for_update: bool = False,
    ) -> NatStateTreasury:
        stmt = select(NatStateTreasury).where(NatStateTreasury.id == cls.TREASURY_ID)
        if for_update:
            stmt = stmt.with_for_update()
        treasury = (await session.execute(stmt)).scalar_one_or_none()
        if treasury:
            return treasury

        try:
            async with session.begin_nested():
                treasury = NatStateTreasury(
                    id=cls.TREASURY_ID,
                    cash=cls.INITIAL_CASH,
                    updated_at=get_game_now(),
                )
                session.add(treasury)
                await session.flush()
        except IntegrityError:
            # Another worker created the singleton first. Re-read the canonical row.
            stmt = select(NatStateTreasury).where(NatStateTreasury.id == cls.TREASURY_ID)
            if for_update:
                stmt = stmt.with_for_update()
            treasury = (await session.execute(stmt)).scalar_one()

        if commit:
            await session.commit()
            await session.refresh(treasury)
        return treasury


__all__ = ["StateTreasuryService"]
