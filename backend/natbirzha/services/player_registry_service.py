"""Persistent list of Telegram users who have opened Natbirzha.

The registry lives in the shared ``class_settings`` table so a world reset can
remove every mutable ``nat_*`` row without losing the IDs needed for a relaunch
announcement.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import ClassSetting

_PLAYER_KEY_PREFIX = "natbirzha_registered_player_"


class PlayerRegistryService:
    @classmethod
    async def register_tg_ids(
        cls,
        session: AsyncSession,
        tg_ids: list[int] | tuple[int, ...] | set[int],
        *,
        commit: bool = False,
    ) -> int:
        """Remember Telegram IDs, returning the number of newly registered IDs."""
        ids = {int(tg_id) for tg_id in tg_ids if tg_id is not None and int(tg_id) > 0}
        if not ids:
            return 0

        rows = [
            {"key": f"{_PLAYER_KEY_PREFIX}{tg_id}", "value": "true"}
            for tg_id in sorted(ids)
        ]
        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            statement = postgres_insert(ClassSetting).values(rows).on_conflict_do_nothing(
                index_elements=[ClassSetting.key]
            )
        elif dialect == "sqlite":
            statement = sqlite_insert(ClassSetting).values(rows).on_conflict_do_nothing(
                index_elements=[ClassSetting.key]
            )
        else:
            existing = set(
                (
                    await session.execute(
                        select(ClassSetting.key).where(
                            ClassSetting.key.in_([row["key"] for row in rows])
                        )
                    )
                )
                .scalars()
                .all()
            )
            missing = [row for row in rows if row["key"] not in existing]
            session.add_all(ClassSetting(**row) for row in missing)
            await session.flush()
            if commit and missing:
                await session.commit()
            return len(missing)

        result = await session.execute(statement)
        inserted = max(0, int(result.rowcount or 0))
        if commit and inserted:
            await session.commit()
        return inserted

    @classmethod
    async def register_user(cls, session: AsyncSession, tg_id: int | None) -> bool:
        if tg_id is None:
            return False
        return bool(await cls.register_tg_ids(session, [int(tg_id)], commit=True))

    @classmethod
    async def get_registered_tg_ids(cls, session: AsyncSession) -> list[int]:
        rows = (
            await session.execute(
                select(ClassSetting.key).where(
                    func.substr(ClassSetting.key, 1, len(_PLAYER_KEY_PREFIX)) == _PLAYER_KEY_PREFIX
                )
            )
        ).scalars().all()
        result: set[int] = set()
        for key in rows:
            raw_id = key.removeprefix(_PLAYER_KEY_PREFIX)
            try:
                tg_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if tg_id > 0:
                result.add(tg_id)
        return sorted(result)


__all__ = ["PlayerRegistryService"]
