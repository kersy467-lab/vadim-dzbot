"""Exact rolling-window sale receipts used by city liquidity snapshots."""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
from backend.natbirzha.catalogs.businesses import INDUSTRIES
from backend.natbirzha.config import get_game_tz
from backend.natbirzha.models.city_orders import NatCityOrder, NatCityOrderDelivery
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.economy_metrics import NatEconomyEvent
from backend.natbirzha.models.market import NatMarketOrder, NatMarketTrade
from backend.natbirzha.models.player_deals import NatSupplyDeal, NatSupplyDealSettlement


def test_rolling_sales_use_exact_receipts_without_duplicate_or_future_rows() -> None:
    async def check() -> None:
        from backend.natbirzha.models.liquidity import NatLiquiditySnapshot
        from backend.natbirzha.services.liquidity_service import LiquidityService

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        game_now = datetime(2026, 9, 26, 12, 0)
        window_start = game_now - timedelta(hours=24)
        utc_now = game_now.replace(tzinfo=get_game_tz()).astimezone(timezone.utc).replace(tzinfo=None)
        try:
            async with sessions() as session:
                users = [
                    User(tg_id=998301, full_name="Liquidity A"),
                    User(tg_id=998302, full_name="Liquidity B"),
                ]
                session.add_all(users)
                await session.flush()
                seller, buyer = [
                    NatCompany(user_id=user.id, name=f"Liquidity {index}", specialization="power_engineer", cash=1000)
                    for index, user in enumerate(users)
                ]
                session.add_all([seller, buyer])
                await session.flush()

                sell_order = NatMarketOrder(
                    company_id=seller.id, order_type="SELL", item_id="steel", price=10,
                    quantity=10, remaining_qty=0, status="FILLED", created_at=window_start,
                )
                session.add(sell_order)
                await session.flush()

                # Market trade timestamps use game time. Seller cash is gross less its recorded fee.
                session.add_all([
                    NatMarketTrade(
                        sell_order_id=sell_order.id, buyer_company_id=buyer.id, seller_company_id=seller.id,
                        item_id="steel", price=10, quantity=10, total_amount=100,
                        fee_amount=2, executed_at=window_start,
                    ),
                    NatMarketTrade(
                        sell_order_id=sell_order.id, buyer_company_id=buyer.id, seller_company_id=seller.id,
                        item_id="steel", price=10, quantity=10, total_amount=100,
                        fee_amount=0, executed_at=game_now,
                    ),
                    # Forced-bankruptcy market fills have no sell order and pay the treasury.
                    NatMarketTrade(
                        buyer_company_id=buyer.id, seller_company_id=seller.id,
                        item_id="steel", price=100, quantity=10, total_amount=1000,
                        fee_amount=0, executed_at=game_now - timedelta(minutes=5),
                    ),
                ])

                deal = NatSupplyDeal(
                    buyer_company_id=buyer.id, supplier_company_id=seller.id,
                    item_id="copper", quantity_per_hour=10, reward_type="PROFIT_SHARE",
                    term_seconds=3600, quoted_reference_price=10, status="ACTIVE",
                    created_at=game_now - timedelta(hours=2),
                )
                session.add(deal)
                await session.flush()
                session.add_all([
                    NatSupplyDealSettlement(
                        deal_id=deal.id, idempotency_key="delivery-1", settlement_type="DELIVERY",
                        item_id="copper", quantity=3, cash_amount=45,
                        created_at=game_now - timedelta(hours=1),
                    ),
                    # Profit-share settlements are not product sales and must not be counted.
                    NatSupplyDealSettlement(
                        deal_id=deal.id, idempotency_key="share-1", settlement_type="PROFIT_SHARE",
                        item_id="copper", quantity=0, cash_amount=500,
                        created_at=game_now - timedelta(hours=1),
                    ),
                ])

                order = NatCityOrder(
                    scheduled_slot=game_now - timedelta(hours=3), industry="agrarian",
                    item_id="grain", quantity=10, remaining_quantity=0, unit_price=15,
                    reserved_cash=150, paid_cash=75, status="FILLED",
                    issued_at=game_now - timedelta(hours=3), expires_at=game_now + timedelta(hours=1),
                )
                old_order = NatCityOrder(
                    scheduled_slot=window_start - timedelta(minutes=1), industry="agrarian",
                    item_id="grain", quantity=10, remaining_quantity=0, unit_price=15,
                    reserved_cash=150, paid_cash=200, status="FILLED",
                    issued_at=window_start - timedelta(minutes=1), expires_at=game_now,
                )
                session.add_all([order, old_order])
                await session.flush()
                session.add_all([
                    NatCityOrderDelivery(
                        order_id=order.id, company_id=seller.id, seller_industry="agrarian",
                        item_id="grain", idempotency_key="city-1", request_hash="a" * 64,
                        quantity=5, cash_amount=75, cost_of_goods_sold=40,
                        response_json={}, created_at=game_now - timedelta(hours=2),
                    ),
                    NatCityOrderDelivery(
                        order_id=old_order.id, company_id=seller.id, seller_industry="agrarian",
                        item_id="grain", idempotency_key="city-old", request_hash="b" * 64,
                        quantity=10, cash_amount=200, cost_of_goods_sold=100,
                        response_json={}, created_at=window_start - timedelta(seconds=1),
                    ),
                ])

                # npc_sell is written only on successful NPC reserve sales. Its timestamp default is UTC.
                session.add_all([
                    NatEconomyEvent(
                        company_id=seller.id, flow="SOURCE", category="npc_sell",
                        cash_amount=30, item_id="energy", quantity=4,
                        created_at=utc_now - timedelta(hours=2),
                    ),
                    NatEconomyEvent(
                        company_id=seller.id, flow="SOURCE", category="npc_sell",
                        cash_amount=999, item_id="energy", quantity=99, created_at=utc_now,
                    ),
                    NatEconomyEvent(
                        company_id=seller.id, flow="SINK", category="npc_buy",
                        cash_amount=999, item_id="energy", quantity=99,
                        created_at=utc_now - timedelta(hours=1),
                    ),
                ])
                await session.flush()

                report = await LiquidityService.aggregate_24h(session, now=game_now)
                assert report["window_start"] == window_start
                assert report["window_end"] == game_now
                assert set(report["sectors"]) == set(INDUSTRIES)
                assert report["sectors"]["agrarian"]["seller_cash_received"] == 75
                assert report["sectors"]["power_engineer"]["seller_cash_received"] == 0
                assert report["unassigned"]["seller_cash_received"] == 173
                assert report["unassigned"]["buyer_cash_paid"] == 175
                assert report["unassigned"]["market_fees"] == 2
                assert report["total_seller_cash_received"] == 248
                assert report["total_buyer_cash_paid"] == 250
                assert report["sale_count"] == 4
                assert report["coverage"]["included_sources"] == {
                    "market_trades": "matched NatMarketTrade.total_amount minus fee_amount; seller industry is not snapshotted",
                    "supply_deals": "NatSupplyDealSettlement.cash_amount where settlement_type=DELIVERY; seller industry is not snapshotted",
                    "city_orders": "NatCityOrderDelivery.cash_amount grouped by event-time seller_industry",
                    "npc_reserve_sales": "NatEconomyEvent SOURCE/npc_sell; UTC event timestamp",
                }
                assert any(
                    "NatNpcDailyVolume" in entry
                    for entry in report["coverage"]["excluded_sources"]
                )
                assert any(
                    "sell_order_id=NULL" in entry
                    for entry in report["coverage"]["excluded_sources"]
                )

                snapshot = await LiquidityService.record_snapshot(session, now=game_now)
                await session.flush()
                assert isinstance(snapshot, NatLiquiditySnapshot)
                assert snapshot.window_start == window_start
                assert snapshot.window_end == game_now
                assert snapshot.total_seller_cash_received == 248
                assert snapshot.sectors_json["agrarian"]["seller_cash_received"] == 75

                same_window = await LiquidityService.record_snapshot(session, now=game_now)
                await session.flush()
                assert same_window.id == snapshot.id
                count = await session.scalar(select(func.count()).select_from(NatLiquiditySnapshot))
                assert count == 1
        finally:
            await engine.dispose()

    asyncio.run(check())
