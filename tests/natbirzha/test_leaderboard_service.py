"""Stable public company leaderboard categories and own-rank lookup."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.military import NatArmy
from backend.natbirzha.models.stocks import NatStock, NatStockHolding
from backend.natbirzha.api.stock_routes import get_portfolio
from backend.natbirzha.config import get_game_now
from backend.natbirzha.services.leaderboard_service import LeaderboardService


async def run_async() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with sessions() as session:
        users = [User(tg_id=990100 + index, full_name=f"Player {index}") for index in range(4)]
        session.add_all(users)
        await session.flush()
        companies = [
            NatCompany(user_id=users[0].id, name="Alpha", specialization="miner", cash=10_000, territory_tiles=4, military_rating=1200),
            NatCompany(user_id=users[1].id, name="Bravo", specialization="miner", cash=20_000, territory_tiles=5, military_rating=1000),
            NatCompany(user_id=users[2].id, name="Charlie", specialization="miner", cash=5_000, territory_tiles=8, military_rating=1100),
            NatCompany(user_id=users[3].id, name="Delta", specialization="miner", cash=5_000, territory_tiles=8, military_rating=1100),
        ]
        session.add_all(companies)
        await session.flush()
        session.add_all([
            NatArmy(company_id=companies[0].id, army_strength=700),
            NatArmy(company_id=companies[1].id, army_strength=900),
            NatArmy(company_id=companies[2].id, army_strength=800),
            NatArmy(company_id=companies[3].id, army_strength=800),
        ])

        now = get_game_now()
        issuer_stock = NatStock(
            company_id=companies[0].id,
            total_shares=1_000,
            founder_shares=900,
            float_shares=100,
            current_price=50.0,
            last_valuation=50_000.0,
            valuation_updated_at=now,
            is_listed=True,
        )
        other_stock = NatStock(
            company_id=companies[1].id,
            total_shares=1_000,
            founder_shares=0,
            float_shares=1_000,
            current_price=25.0,
            last_valuation=25_000.0,
            valuation_updated_at=now,
            is_listed=True,
        )
        session.add_all([issuer_stock, other_stock])
        await session.flush()
        session.add_all([
            NatStockHolding(
                stock_id=issuer_stock.id,
                holder_company_id=companies[0].id,
                shares_count=900,
                avg_price=50.0,
            ),
            NatStockHolding(
                stock_id=other_stock.id,
                holder_company_id=companies[0].id,
                shares_count=4,
                avg_price=25.0,
            ),
        ])
        await session.commit()

        portfolio = await get_portfolio(company=companies[0], session=session)
        portfolio_by_stock = {row["stock_id"]: row for row in portfolio["portfolio"]}
        assert portfolio_by_stock[issuer_stock.id]["shares_count"] == 900
        assert portfolio_by_stock[other_stock.id]["shares_count"] == 4

        assets = await LeaderboardService.get_leaderboard(
            session, companies[0].id, category="assets"
        )
        own_assets = assets["my_entry"]
        assert own_assets["stock_value"] == 100.0, own_assets
        assert own_assets["assets"] == 50_100.0, own_assets

        cash = await LeaderboardService.get_leaderboard(session, companies[0].id, category="cash", page=1, page_size=2)
        assert [row["company_name"] for row in cash["entries"]] == ["Bravo", "Alpha"]
        assert cash["my_rank"] == 2 and cash["total"] == 4

        land = await LeaderboardService.get_leaderboard(session, companies[0].id, category="territory", page=1, page_size=2)
        assert [row["company_name"] for row in land["entries"]] == ["Charlie", "Delta"]
        assert land["entries"][0]["rank"] == 1 and land["entries"][1]["rank"] == 2

        army = await LeaderboardService.get_leaderboard(session, companies[0].id, category="army", page=2, page_size=2)
        assert army["entries"][0]["company_name"] == "Delta"
        assert army["my_rank"] == 4

    await engine.dispose()
    print("NATBIRZHA leaderboard categories and stable pagination: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
