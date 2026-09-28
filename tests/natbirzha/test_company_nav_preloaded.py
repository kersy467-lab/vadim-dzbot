from types import SimpleNamespace
from unittest.mock import AsyncMock

from backend.natbirzha.models.inventory import get_item_base_price
from backend.natbirzha.services.company_service import CompanyService


class _EmptyBusinessResult:
    def scalars(self):
        return self

    def all(self):
        return []


def test_audited_nav_reuses_preloaded_factory_and_inventory_rows():
    async def run():
        session = AsyncMock()
        session.execute = AsyncMock(return_value=_EmptyBusinessResult())
        company = SimpleNamespace(id=7, cash=1250.0, territory_tiles=2)
        factories = [SimpleNamespace(level=3)]
        inventory = [SimpleNamespace(item_id="water", quantity=4.0)]

        nav = await CompanyService.calculate_audited_nav(
            session, company, factories=factories, inventory=inventory
        )

        expected = 1250 + 2 * 10_000 + 3 * 25_000 + 4 * get_item_base_price("water")
        assert nav == round(expected, 2)
        assert session.execute.await_count == 1  # businesses only

    import asyncio
    asyncio.run(run())