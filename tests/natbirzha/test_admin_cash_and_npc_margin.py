"""Regression coverage for admin onboarding cash and NPC pricing."""

import asyncio

from backend.db.models import User
from backend.natbirzha.config import nat_settings
from backend.natbirzha.migrations import _migrate_p2_creator_grant
from backend.natbirzha.models.inventory import get_npc_buy_price, get_npc_sell_price
from backend.natbirzha.services.company_service import CompanyService
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


class _Session:
    def __init__(self, user=None):
        self.user = user

    async def get(self, model, user_id):
        return self.user if self.user and self.user.id == user_id else None

    async def execute(self, _statement):
        class _Result:
            @staticmethod
            def scalar_one_or_none():
                return None

        return _Result()


def test_admin_and_creator_start_with_normal_cash_without_losing_creator_pvc():
    async def run():
        admin = User(id=71, tg_id=987654321, full_name="Admin", role="admin")
        admin_cash, admin_pvc = await CompanyService.get_starting_grant(_Session(admin), admin.id)
        creator_cash, creator_pvc = await CompanyService.get_starting_grant(_Session(), 1053722876)

        assert admin_cash == nat_settings.STARTING_CASH
        assert creator_cash == nat_settings.STARTING_CASH
        assert admin_pvc == 200
        assert creator_pvc == 200

    asyncio.run(run())


def test_npc_markup_is_fifty_percent_and_buy_discount_stays_twenty_percent():
    # Copper has a base price of 60 cash.
    assert get_npc_sell_price("copper") == 90.0
    assert get_npc_buy_price("copper") == 48.0


def test_pending_creator_migration_only_grants_pvc_not_starting_cash():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, tg_id BIGINT, username TEXT)"))
            await connection.execute(text("CREATE TABLE nat_companies (user_id INTEGER, cash FLOAT, pvc_balance INTEGER, nat_balance INTEGER)"))
            await connection.execute(text("INSERT INTO users (id, tg_id, username) VALUES (1, 1053722876, 'notariuspiva')"))
            await connection.execute(text("INSERT INTO nat_companies (user_id, cash, pvc_balance, nat_balance) VALUES (1, 50000, 0, 0)"))

            await _migrate_p2_creator_grant(connection)

            result = await connection.execute(text("SELECT cash, pvc_balance, nat_balance FROM nat_companies WHERE user_id = 1"))
            cash, pvc, nat = result.one()
            assert cash == 50000
            assert pvc == 200 and nat == 200
        await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    test_admin_and_creator_start_with_normal_cash_without_losing_creator_pvc()
    test_npc_markup_is_fifty_percent_and_buy_discount_stays_twenty_percent()
    test_pending_creator_migration_only_grants_pvc_not_starting_cash()
    print("NATBIRZHA admin grant and NPC margin: PASS")
