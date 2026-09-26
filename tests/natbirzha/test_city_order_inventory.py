"""City orders may consume only stock not held by another market order."""

import asyncio
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.city_order_service import CityOrderService


def test_reserved_inventory_cannot_be_delivered_to_city_order() -> None:
    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        try:
            async with sessions() as session:
                user = User(tg_id=991598, full_name="Reserved Stock Supplier")
                session.add(user)
                await session.flush()
                company = NatCompany(
                    user_id=user.id, name="Reserved Stock Co", specialization="miner", cash=1000,
                )
                session.add_all([company, NatStateTreasury(id=1, cash=100_000)])
                await session.flush()
                issued = await CityOrderService.issue_due(
                    session, now=datetime(2026, 9, 26, 12, 0),
                )
                order = issued["order"]
                original_cash = company.cash
                held = round(order["quantity"] / 2, 6)
                inventory = NatInventory(
                    company_id=company.id,
                    item_id=order["item_id"],
                    quantity=order["quantity"],
                    reserved_quantity=held,
                    avg_cost_basis=1.0,
                )
                session.add(inventory)
                await session.flush()
                with pytest.raises(ValueError):
                    await CityOrderService.deliver(
                        session, company.id, order["id"], order["quantity"],
                        idempotency_key="city-delivery-held-stock",
                        now=datetime(2026, 9, 26, 12, 2),
                    )
                assert inventory.quantity == order["quantity"]
                assert company.cash == original_cash
                assert (await CityOrderService.get_order(session, order["id"]))["remaining_quantity"] == order["quantity"]
        finally:
            await engine.dispose()

    asyncio.run(check())
