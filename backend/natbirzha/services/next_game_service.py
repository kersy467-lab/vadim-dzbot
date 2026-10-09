"""Persistence and validation for the isolated administrator preview game."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.next_game_catalog import find_next_game_sector, get_next_game_catalog


class NextGameService:
    @staticmethod
    def snapshot_company(company: NatNextGameCompany | None) -> dict[str, Any] | None:
        if company is None:
            return None
        return {
            "id": company.id,
            "name": company.name,
            "cash": float(company.cash),
            "sector_id": company.sector_id,
            "branch_path": list(company.branch_path or []),
        }

    @classmethod
    async def snapshot(cls, session: AsyncSession, owner_tg_id: int) -> dict[str, Any]:
        company = await session.scalar(
            select(NatNextGameCompany).where(NatNextGameCompany.owner_tg_id == owner_tg_id)
        )
        return {"company": cls.snapshot_company(company), "corporations": get_next_game_catalog()}

    @classmethod
    async def create_company(
        cls, session: AsyncSession, owner_tg_id: int, name: str
    ) -> dict[str, Any]:
        company = await session.scalar(
            select(NatNextGameCompany).where(NatNextGameCompany.owner_tg_id == owner_tg_id)
            .with_for_update()
        )
        if company is None:
            company = NatNextGameCompany(
                owner_tg_id=int(owner_tg_id), name=name.strip()[:80], branch_path=[], cash=10_000.0
            )
            session.add(company)
            await session.flush()
        return {"success": True, "company": cls.snapshot_company(company)}

    @classmethod
    async def select_sector(
        cls, session: AsyncSession, owner_tg_id: int, sector_id: str
    ) -> dict[str, Any]:
        sector = find_next_game_sector(sector_id)
        if sector is None:
            raise ValueError("Отрасль отсутствует на карте 2.0")
        company = await cls._owned_company(session, owner_tg_id)
        if company.sector_id and company.sector_id != sector_id:
            raise ValueError("Стартовая отрасль уже выбрана и сохранена")
        company.sector_id = sector_id
        await session.flush()
        return {"success": True, "company": cls.snapshot_company(company)}

    @classmethod
    async def select_branch(
        cls, session: AsyncSession, owner_tg_id: int, branch_id: str
    ) -> dict[str, Any]:
        company = await cls._owned_company(session, owner_tg_id)
        if not company.sector_id:
            raise ValueError("Сначала выберите стартовую корпорацию")
        sector = find_next_game_sector(company.sector_id)
        branch = next((item for item in sector["branches"] if item["id"] == branch_id), None)
        if branch is None:
            raise ValueError("Эта ветка не относится к выбранной корпорации")
        path = list(company.branch_path or [])
        if path and path[0] != branch_id:
            raise ValueError("Первая ветка развития уже выбрана")
        if not path:
            company.branch_path = [branch_id]
            company.updated_at = datetime.utcnow()
        await session.flush()
        return {"success": True, "company": cls.snapshot_company(company)}

    @staticmethod
    async def _owned_company(session: AsyncSession, owner_tg_id: int) -> NatNextGameCompany:
        company = await session.scalar(
            select(NatNextGameCompany).where(NatNextGameCompany.owner_tg_id == owner_tg_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if company is None:
            raise ValueError("Сначала создайте тестовую компанию 2.0")
        return company


__all__ = ["NextGameService"]
