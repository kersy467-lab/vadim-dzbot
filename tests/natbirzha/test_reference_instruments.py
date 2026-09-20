"""Official reference-rate parsing and atomic instrument trading checks."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.instruments import NatInstrumentPosition, NatInstrumentTrade
from backend.natbirzha.services.reference_instrument_service import (
    ReferenceInstrumentService,
    StaleReferenceRate,
)


CURRENCY_XML = b"""<?xml version='1.0' encoding='windows-1251'?>
<ValCurs Date="18.09.2026" name="Foreign Currency Market">
  <Valute ID="R01235"><NumCode>840</NumCode><CharCode>USD</CharCode><Nominal>1</Nominal><Name>US Dollar</Name><Value>83,1250</Value><VunitRate>83,1250</VunitRate></Valute>
  <Valute ID="R01239"><NumCode>978</NumCode><CharCode>EUR</CharCode><Nominal>10</Nominal><Name>Euro</Name><Value>975,5000</Value></Valute>
</ValCurs>"""

METAL_XML = b"""<?xml version='1.0' encoding='windows-1251'?>
<Metall name="Precious metals">
  <Record Date="18.09.2026" Code="1"><Buy>10750,25</Buy><Sell>10850,25</Sell></Record>
  <Record Date="18.09.2026" Code="2"><Buy>122,40</Buy><Sell>124,40</Sell></Record>
</Metall>"""


async def run_async() -> None:
    parsed_currency = ReferenceInstrumentService.parse_currency_xml(CURRENCY_XML)
    assert parsed_currency["USD"] == (83.125, datetime(2026, 9, 18))
    assert parsed_currency["EUR"] == (97.55, datetime(2026, 9, 18))

    parsed_metals = ReferenceInstrumentService.parse_metals_xml(METAL_XML)
    assert parsed_metals["GOLD"] == (10800.25, datetime(2026, 9, 18))
    assert parsed_metals["SILVER"] == (123.4, datetime(2026, 9, 18))

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    now = datetime(2026, 9, 18, 12, 0)
    async with sessions() as session:
        company = NatCompany(
            user_id=920001,
            name="Reference Trader",
            specialization="miner",
            cash=10_000.0,
        )
        session.add(company)
        await session.flush()
        await ReferenceInstrumentService.store_rates(
            session,
            {
                "USD": (100.0, now),
                "EUR": (120.0, now),
                "GOLD": (8_000.0, now),
                "SILVER": (90.0, now),
            },
            fetched_at=now,
        )
        await session.commit()

        bought = await ReferenceInstrumentService.trade(
            session,
            company.id,
            "USD",
            "buy",
            10,
            "ref-buy-1",
            now=now,
        )
        assert bought["unit_price_rub"] == 101.0
        assert bought["gross_rub"] == 1010.0
        assert bought["remaining_cash"] == 8990.0

        replay = await ReferenceInstrumentService.trade(
            session,
            company.id,
            "USD",
            "buy",
            10,
            "ref-buy-1",
            now=now + timedelta(minutes=1),
        )
        assert replay == bought

        sold = await ReferenceInstrumentService.trade(
            session,
            company.id,
            "USD",
            "sell",
            4,
            "ref-sell-1",
            now=now + timedelta(minutes=2),
        )
        assert sold["unit_price_rub"] == 99.0
        assert sold["remaining_quantity"] == 6
        assert sold["remaining_cash"] == 9386.0
        await session.commit()

        position = await session.scalar(select(NatInstrumentPosition))
        assert position is not None and position.quantity == 6
        count = await session.scalar(select(func.count(NatInstrumentTrade.id)))
        assert count == 2

        try:
            await ReferenceInstrumentService.trade(
                session,
                company.id,
                "USD",
                "buy",
                1,
                "ref-stale-1",
                now=now + timedelta(hours=72, seconds=1),
            )
        except StaleReferenceRate:
            pass
        else:
            raise AssertionError("A reference rate older than 72 hours must block trading")

    await engine.dispose()
    print("NATBIRZHA reference instruments checks: PASS")


if __name__ == "__main__":
    asyncio.run(run_async())
