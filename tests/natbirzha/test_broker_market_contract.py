"""Pure broker-contract checks that do not require a database driver."""

from pathlib import Path

from backend.natbirzha.services.reference_instrument_service import ReferenceInstrumentService
from backend.natbirzha.services.stock_service import StockService


CURRENCY_HISTORY_XML = b'''<?xml version="1.0" encoding="windows-1251"?>
<ValCurs ID="R01235" DateRange1="01.09.2026" DateRange2="02.09.2026" name="Foreign Currency Market">
<Record Date="01.09.2026" Id="R01235"><Nominal>1</Nominal><Value>80,0000</Value><VunitRate>80,0000</VunitRate></Record>
<Record Date="02.09.2026" Id="R01235"><Nominal>1</Nominal><Value>81,5000</Value><VunitRate>81,5000</VunitRate></Record>
</ValCurs>'''

METALS_HISTORY_XML = b'''<?xml version="1.0" encoding="windows-1251"?>
<Metall>
<Record Date="01.09.2026" Code="1"><Buy>8000,00</Buy><Sell>8020,00</Sell></Record>
<Record Date="02.09.2026" Code="1"><Buy>8100,00</Buy><Sell>8120,00</Sell></Record>
<Record Date="01.09.2026" Code="2"><Buy>90,00</Buy><Sell>92,00</Sell></Record>
<Record Date="02.09.2026" Code="2"><Buy>95,00</Buy><Sell>97,00</Sell></Record>
</Metall>'''


def run() -> None:
    currency = ReferenceInstrumentService.parse_currency_history_xml(CURRENCY_HISTORY_XML, "USD")
    assert [row[0] for row in currency] == [80.0, 81.5]
    metals = ReferenceInstrumentService.parse_metals_history_xml(METALS_HISTORY_XML)
    assert [row[0] for row in metals["GOLD"]] == [8010.0, 8110.0]
    assert [row[0] for row in metals["SILVER"]] == [91.0, 96.0]

    fair = 100.0
    neutral = StockService.blended_market_price(fair, 100.0, 0.0)
    bid_heavy = StockService.blended_market_price(fair, 100.0, 1.0)
    ask_heavy = StockService.blended_market_price(fair, 100.0, -1.0)
    assert neutral == 100.0
    assert ask_heavy < neutral < bid_heavy
    assert 75.0 <= ask_heavy <= 125.0 and 75.0 <= bid_heavy <= 125.0

    root = Path(__file__).resolve().parents[2]
    orderbook = (root / "backend/natbirzha/services/stock_orderbook_service.py").read_text()
    finance = (root / "frontend/natbirzha/js/screens/market_finance.js").read_text()
    chart = (root / "frontend/natbirzha/js/market_chart.js").read_text()
    assert 'order_type == "BUY"' in orderbook and 'order_type == "SELL"' in orderbook
    assert "NatStockPriceSnapshot" in orderbook and "best_bid" in orderbook and "best_ask" in orderbook
    assert "Стакан" in finance and "getStockOrderbook" in finance and "placeStockOrder" in finance
    assert "Официальный ориентир ЦБ РФ" in finance and "getStockHistory" in finance
    assert "renderRangeButtons" not in chart
    assert "market-range-btn" not in finance
    print("NATBIRZHA broker market contract: PASS")


if __name__ == "__main__":
    run()
