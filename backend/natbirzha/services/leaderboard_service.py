"""Read-only, server-valued company leaderboards."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.creator import NatStateBond, NatStateBondHolding
from backend.natbirzha.models.inventory import NatInventory, get_item_base_price
from backend.natbirzha.models.military import NatArmy
from backend.natbirzha.models.stocks import NatStock, NatStockHolding


class LeaderboardService:
    CATEGORIES = {
        "assets": "Активы",
        "territory": "Земля",
        "army": "Армия",
        "cash": "Деньги",
        "company_value": "Стоимость компании",
        "military_rating": "Военный рейтинг",
    }

    @staticmethod
    async def _aggregate_values(session: AsyncSession) -> list[dict[str, Any]]:
        """Build all sortable values in bounded aggregate queries, not N+1 requests."""
        companies = (
            await session.execute(
                select(NatCompany, User)
                .outerjoin(User, User.id == NatCompany.user_id)
                .where(NatCompany.is_bankrupt.is_(False))
            )
        ).all()
        if not companies:
            return []
        company_ids = [company.id for company, _user in companies]

        factory_rows = await session.execute(
            select(NatFactory.company_id, func.count(NatFactory.id))
            .where(NatFactory.company_id.in_(company_ids))
            .group_by(NatFactory.company_id)
        )
        factory_count = dict(factory_rows.all())
        army_rows = await session.execute(
            select(NatArmy.company_id, NatArmy.army_strength)
            .where(NatArmy.company_id.in_(company_ids))
        )
        army_strength = dict(army_rows.all())
        inventory_rows = await session.execute(
            select(NatInventory.company_id, NatInventory.item_id, NatInventory.quantity)
            .where(NatInventory.company_id.in_(company_ids), NatInventory.quantity > 0)
        )
        inventory_value: dict[int, float] = defaultdict(float)
        for company_id, item_id, quantity in inventory_rows.all():
            try:
                inventory_value[company_id] += float(quantity) * get_item_base_price(item_id)
            except ValueError:
                continue
        stock_rows = await session.execute(
            select(
                NatStockHolding.holder_company_id,
                func.sum(NatStockHolding.shares_count * NatStock.current_price),
            )
            .join(NatStock, NatStock.id == NatStockHolding.stock_id)
            .where(NatStockHolding.holder_company_id.in_(company_ids))
            .group_by(NatStockHolding.holder_company_id)
        )
        stock_value = {company_id: float(value or 0) for company_id, value in stock_rows.all()}
        bond_rows = await session.execute(
            select(
                NatStateBondHolding.company_id,
                func.sum(NatStateBondHolding.quantity * NatStateBond.face_value),
            )
            .join(NatStateBond, NatStateBond.id == NatStateBondHolding.bond_id)
            .where(NatStateBondHolding.company_id.in_(company_ids))
            .group_by(NatStateBondHolding.company_id)
        )
        bond_value = {company_id: float(value or 0) for company_id, value in bond_rows.all()}

        rows: list[dict[str, Any]] = []
        for company, user in companies:
            cid = company.id
            nav = round(
                float(company.cash)
                + company.territory_tiles * 10_000.0
                + factory_count.get(cid, 0) * 25_000.0
                + inventory_value[cid],
                2,
            )
            shares = round(stock_value.get(cid, 0.0), 2)
            bonds = round(bond_value.get(cid, 0.0), 2)
            rows.append({
                "company_id": cid,
                "company_name": company.name,
                "specialization": company.specialization,
                "level": company.level,
                "cash": round(float(company.cash), 2),
                "territory": company.territory_tiles,
                "factory_count": factory_count.get(cid, 0),
                "army": int(army_strength.get(cid, 0) or 0),
                "military_rating": company.military_rating,
                "company_value": nav,
                "stock_value": shares,
                "bond_value": bonds,
                "assets": round(nav + shares + bonds, 2),
                "pvc_balance": company.pvc_balance,
                "last_activity_at": company.updated_at.isoformat(),
                "telegram_name": user.display_name if user else None,
                "telegram_username": user.username if user else None,
            })
        return rows

    @classmethod
    async def get_leaderboard(
        cls,
        session: AsyncSession,
        current_company_id: int,
        *,
        category: str = "assets",
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        if category not in cls.CATEGORIES:
            raise ValueError("Unknown leaderboard category")
        page = max(1, page)
        page_size = max(1, min(page_size, 50))
        rows = await cls._aggregate_values(session)
        rows.sort(key=lambda row: (-float(row[category]), row["company_id"]))
        for rank, row in enumerate(rows, start=1):
            row["rank"] = rank
            row["value"] = row[category]
        own = next((row for row in rows if row["company_id"] == current_company_id), None)
        start = (page - 1) * page_size
        return {
            "category": category,
            "category_title": cls.CATEGORIES[category],
            "page": page,
            "page_size": page_size,
            "total": len(rows),
            "entries": rows[start:start + page_size],
            "my_rank": own["rank"] if own else None,
            "my_entry": own,
        }

    @classmethod
    async def get_players(
        cls,
        session: AsyncSession,
        *,
        query: str = "",
        sort: str = "last_activity_at",
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        rows = await cls._aggregate_values(session)
        needle = query.strip().casefold()
        if needle:
            rows = [row for row in rows if needle in " ".join(str(row.get(key) or "") for key in ("company_name", "telegram_name", "telegram_username")).casefold()]
        allowed = {"last_activity_at", "level", "cash", "assets", "territory", "army", "military_rating", "pvc_balance"}
        if sort not in allowed:
            raise ValueError("Unknown player sort")
        # Stable company-id tie-breaker, including newest-first activity sort.
        rows.sort(key=lambda row: row["company_id"])
        rows.sort(key=lambda row: row[sort], reverse=True)
        page = max(1, page)
        page_size = max(1, min(page_size, 50))
        start = (page - 1) * page_size
        return {"query": query, "sort": sort, "page": page, "page_size": page_size, "total": len(rows), "players": rows[start:start + page_size]}


__all__ = ["LeaderboardService"]
