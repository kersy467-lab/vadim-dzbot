"""Read-only, server-valued company leaderboards."""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.joint_factories import NatJointFactory
from backend.natbirzha.models.creator import NatStateBond, NatStateBondHolding
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, NatInventory, get_item_base_price
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
        """Build leaderboard values in two bounded queries, without per-item reads."""
        inventory_prices = {
            item_id: get_item_base_price(item_id)
            for item_id in CANONICAL_ITEMS
        }
        inventory_price = case(
            inventory_prices,
            value=NatInventory.item_id,
            else_=0.0,
        )
        active_company_ids = select(NatCompany.id).where(NatCompany.is_bankrupt.is_(False))
        factory_totals = (
            select(NatFactory.company_id.label("company_id"), func.count(NatFactory.id).label("factory_count"))
            .where(NatFactory.company_id.in_(active_company_ids))
            .group_by(NatFactory.company_id)
            .subquery()
        )
        army_totals = (
            select(NatArmy.company_id.label("company_id"), NatArmy.army_strength.label("army_strength"))
            .where(NatArmy.company_id.in_(active_company_ids))
            .subquery()
        )
        inventory_totals = (
            select(
                NatInventory.company_id.label("company_id"),
                func.sum(NatInventory.quantity * inventory_price).label("inventory_value"),
                func.count(NatInventory.id).label("inventory_rows"),
            )
            .where(NatInventory.quantity > 0, NatInventory.company_id.in_(active_company_ids))
            .group_by(NatInventory.company_id)
            .subquery()
        )
        stock_totals = (
            select(
                NatStockHolding.holder_company_id.label("company_id"),
                func.sum(NatStockHolding.shares_count * NatStock.current_price).label("stock_value"),
            )
            .join(NatStock, NatStock.id == NatStockHolding.stock_id)
            .where(
                NatStock.company_id != NatStockHolding.holder_company_id,
                NatStockHolding.holder_company_id.in_(active_company_ids),
            )
            .group_by(NatStockHolding.holder_company_id)
            .subquery()
        )
        bond_totals = (
            select(
                NatStateBondHolding.company_id.label("company_id"),
                func.sum(NatStateBondHolding.quantity * NatStateBond.face_value).label("bond_value"),
            )
            .join(NatStateBond, NatStateBond.id == NatStateBondHolding.bond_id)
            .where(NatStateBondHolding.company_id.in_(active_company_ids))
            .group_by(NatStateBondHolding.company_id)
            .subquery()
        )
        companies = (await session.execute(
            select(
                NatCompany,
                User,
                func.coalesce(factory_totals.c.factory_count, 0),
                func.coalesce(army_totals.c.army_strength, 0),
                func.coalesce(inventory_totals.c.inventory_value, 0.0),
                func.coalesce(inventory_totals.c.inventory_rows, 0),
                func.coalesce(stock_totals.c.stock_value, 0.0),
                func.coalesce(bond_totals.c.bond_value, 0.0),
            )
            .outerjoin(User, User.id == NatCompany.user_id)
            .outerjoin(factory_totals, factory_totals.c.company_id == NatCompany.id)
            .outerjoin(army_totals, army_totals.c.company_id == NatCompany.id)
            .outerjoin(inventory_totals, inventory_totals.c.company_id == NatCompany.id)
            .outerjoin(stock_totals, stock_totals.c.company_id == NatCompany.id)
            .outerjoin(bond_totals, bond_totals.c.company_id == NatCompany.id)
            .where(NatCompany.is_bankrupt.is_(False))
        )).all()
        if not companies:
            return []
        company_ids = [row[0].id for row in companies]
        inventory_value = {
            row[0].id: float(row[4] or 0)
            for row in companies if int(row[5] or 0) > 0
        }
        joint_rows = (await session.execute(
            select(NatJointFactory).where(
                NatJointFactory.company_a_id.in_(company_ids)
                | NatJointFactory.company_b_id.in_(company_ids)
            )
        )).scalars().all()
        for joint_factory in joint_rows:
            for owner_id, owner_stock in (
                (joint_factory.company_a_id, joint_factory.stock_a_json or {}),
                (joint_factory.company_b_id, joint_factory.stock_b_json or {}),
            ):
                if owner_id not in inventory_value:
                    continue
                for item_id, quantity in owner_stock.items():
                    try:
                        inventory_value[owner_id] += float(quantity) * get_item_base_price(item_id)
                    except ValueError:
                        continue

        rows: list[dict[str, Any]] = []
        for company, user, factories, army, _inventory_total, _inventory_rows, stocks, bonds in companies:
            cid = company.id
            nav = round(
                float(company.cash)
                + company.territory_tiles * 10_000.0
                + int(factories or 0) * 25_000.0
                + inventory_value.get(cid, 0.0),
                2,
            )
            shares = round(float(stocks or 0.0), 2)
            bond_value = round(float(bonds or 0.0), 2)
            rows.append({
                "company_id": cid,
                "company_name": company.name,
                "specialization": company.specialization,
                "level": company.level,
                "cash": round(float(company.cash), 2),
                "territory": company.territory_tiles,
                "factory_count": int(factories or 0),
                "army": int(army or 0),
                "military_rating": company.military_rating,
                "company_value": nav,
                "stock_value": shares,
                "bond_value": bond_value,
                "assets": round(nav + shares + bond_value, 2),
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
