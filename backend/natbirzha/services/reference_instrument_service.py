from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Tuple
from xml.etree import ElementTree

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.instruments import (
    NatInstrumentPosition,
    NatInstrumentTrade,
    NatReferenceRateSnapshot,
)


class StaleReferenceRate(ValueError):
    pass


class ReferenceInstrumentService:
    CURRENCY_URL = "https://www.cbr.ru/scripts/XML_daily.asp"
    CURRENCY_DYNAMIC_URL = "https://www.cbr.ru/scripts/XML_dynamic.asp"
    METALS_URL = "https://www.cbr.ru/scripts/xml_metall.asp"
    CURRENCY_IDS = {"USD": "R01235", "EUR": "R01239"}
    HISTORY_DAYS = 370
    SUPPORTED = ("USD", "EUR", "GOLD", "SILVER")
    METAL_CODES = {"1": "GOLD", "2": "SILVER"}
    MAX_RATE_AGE = timedelta(hours=72)
    SPREAD_RATE = 0.01

    @staticmethod
    def _decimal(value: str) -> float:
        return float(value.strip().replace(" ", "").replace(",", "."))

    @staticmethod
    def _date(value: str) -> datetime:
        return datetime.strptime(value, "%d.%m.%Y")

    @classmethod
    def parse_currency_xml(cls, payload: bytes) -> Dict[str, Tuple[float, datetime]]:
        root = ElementTree.fromstring(payload)
        quoted_at = cls._date(root.attrib["Date"])
        result: Dict[str, Tuple[float, datetime]] = {}
        for row in root.findall(".//Valute"):
            code = (row.findtext("CharCode") or "").upper()
            if code not in ("USD", "EUR"):
                continue
            nominal = cls._decimal(row.findtext("Nominal") or "1")
            value_text = row.findtext("VunitRate")
            value = cls._decimal(value_text) if value_text else cls._decimal(row.findtext("Value") or "0") / nominal
            result[code] = (round(value, 6), quoted_at)
        if set(result) != {"USD", "EUR"}:
            raise ValueError("CBR currency response is missing USD or EUR.")
        return result

    @classmethod
    def parse_currency_history_xml(cls, payload: bytes, code: str) -> list[Tuple[float, datetime]]:
        root = ElementTree.fromstring(payload)
        rows: list[Tuple[float, datetime]] = []
        for row in root.findall(".//Record"):
            quoted_at = cls._date(row.attrib["Date"])
            nominal = cls._decimal(row.findtext("Nominal") or "1")
            value_text = row.findtext("VunitRate")
            value = cls._decimal(value_text) if value_text else cls._decimal(row.findtext("Value") or "0") / nominal
            if value > 0:
                rows.append((round(value, 6), quoted_at))
        if not rows:
            raise ValueError(f"CBR currency history is empty for {code}.")
        return rows

    @classmethod
    def parse_metals_history_xml(cls, payload: bytes) -> Dict[str, list[Tuple[float, datetime]]]:
        root = ElementTree.fromstring(payload)
        history: Dict[str, list[Tuple[float, datetime]]] = {"GOLD": [], "SILVER": []}
        for row in root.findall(".//Record"):
            code = cls.METAL_CODES.get(row.attrib.get("Code", ""))
            if code not in history:
                continue
            values = [cls._decimal(v) for v in (row.findtext("Buy"), row.findtext("Sell")) if v not in (None, "")]
            if values:
                history[code].append((round(sum(values) / len(values), 6), cls._date(row.attrib["Date"])))
        if not all(history.values()):
            raise ValueError("CBR metals history is missing gold or silver.")
        return history

    @classmethod
    def parse_metals_xml(cls, payload: bytes) -> Dict[str, Tuple[float, datetime]]:
        root = ElementTree.fromstring(payload)
        latest: Dict[str, Tuple[float, datetime]] = {}
        for row in root.findall(".//Record"):
            code = cls.METAL_CODES.get(row.attrib.get("Code", ""))
            if not code:
                continue
            quoted_at = cls._date(row.attrib["Date"])
            buy_text = row.findtext("Buy")
            sell_text = row.findtext("Sell")
            values = [cls._decimal(v) for v in (buy_text, sell_text) if v not in (None, "")]
            if not values:
                continue
            value = round(sum(values) / len(values), 6)
            previous = latest.get(code)
            if previous is None or quoted_at >= previous[1]:
                latest[code] = (value, quoted_at)
        if set(latest) != {"GOLD", "SILVER"}:
            raise ValueError("CBR metals response is missing gold or silver.")
        return latest

    @classmethod
    async def fetch_official_history(
        cls, now: datetime | None = None, days: int | None = None
    ) -> Dict[str, list[Tuple[float, datetime]]]:
        now = now or get_game_now()
        days = max(7, min(int(days or cls.HISTORY_DAYS), cls.HISTORY_DAYS))
        date_from = (now - timedelta(days=days)).strftime("%d/%m/%Y")
        date_to = now.strftime("%d/%m/%Y")
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            usd, eur, metals = await asyncio.gather(
                client.get(cls.CURRENCY_DYNAMIC_URL, params={"date_req1": date_from, "date_req2": date_to, "VAL_NM_RQ": cls.CURRENCY_IDS["USD"]}),
                client.get(cls.CURRENCY_DYNAMIC_URL, params={"date_req1": date_from, "date_req2": date_to, "VAL_NM_RQ": cls.CURRENCY_IDS["EUR"]}),
                client.get(cls.METALS_URL, params={"date_req1": date_from, "date_req2": date_to}),
            )
        for response in (usd, eur, metals):
            response.raise_for_status()
        metal_history = cls.parse_metals_history_xml(metals.content)
        return {
            "USD": cls.parse_currency_history_xml(usd.content, "USD"),
            "EUR": cls.parse_currency_history_xml(eur.content, "EUR"),
            **metal_history,
        }

    @classmethod
    async def fetch_official_rates(cls, now: datetime | None = None) -> Dict[str, Tuple[float, datetime]]:
        now = now or get_game_now()
        date_from = (now - timedelta(days=7)).strftime("%d/%m/%Y")
        date_to = now.strftime("%d/%m/%Y")
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            currency, metals = await asyncio.gather(
                client.get(cls.CURRENCY_URL),
                client.get(cls.METALS_URL, params={"date_req1": date_from, "date_req2": date_to}),
            )
        currency.raise_for_status()
        metals.raise_for_status()
        return {**cls.parse_currency_xml(currency.content), **cls.parse_metals_xml(metals.content)}

    @classmethod
    async def store_rates(
        cls,
        session: AsyncSession,
        rates: Dict[str, Tuple[float, datetime]],
        fetched_at: datetime | None = None,
    ) -> list[NatReferenceRateSnapshot]:
        fetched_at = fetched_at or get_game_now()
        stored = []
        for code, (value, quoted_at) in rates.items():
            code = code.upper()
            if code not in cls.SUPPORTED or value <= 0:
                raise ValueError(f"Unsupported or invalid reference rate: {code}")
            existing = await session.scalar(
                select(NatReferenceRateSnapshot).where(
                    NatReferenceRateSnapshot.instrument_code == code,
                    NatReferenceRateSnapshot.quoted_at == quoted_at,
                    NatReferenceRateSnapshot.source_id == "cbr",
                )
            )
            if existing:
                stored.append(existing)
                continue
            source_url = cls.CURRENCY_URL if code in ("USD", "EUR") else cls.METALS_URL
            row = NatReferenceRateSnapshot(
                instrument_code=code,
                value_rub=round(value, 6),
                nominal=1.0,
                source_id="cbr",
                source_url=source_url,
                quoted_at=quoted_at,
                fetched_at=fetched_at,
            )
            session.add(row)
            stored.append(row)
        await session.flush()
        return stored

    @classmethod
    async def refresh(cls, session: AsyncSession, now: datetime | None = None) -> list[NatReferenceRateSnapshot]:
        """Cache official CBR history and return the latest stored point per instrument."""
        now = now or get_game_now()
        existing_count = await session.scalar(select(func.count(NatReferenceRateSnapshot.id)))
        history_days = cls.HISTORY_DAYS if int(existing_count or 0) < 30 else 14
        history = await cls.fetch_official_history(now, days=history_days)
        latest: list[NatReferenceRateSnapshot] = []
        for code, points in history.items():
            source_url = cls.CURRENCY_DYNAMIC_URL if code in cls.CURRENCY_IDS else cls.METALS_URL
            last_row = None
            for value, quoted_at in points:
                existing = await session.scalar(select(NatReferenceRateSnapshot).where(
                    NatReferenceRateSnapshot.instrument_code == code,
                    NatReferenceRateSnapshot.quoted_at == quoted_at,
                    NatReferenceRateSnapshot.source_id == "cbr",
                ))
                if existing:
                    last_row = existing
                    continue
                last_row = NatReferenceRateSnapshot(
                    instrument_code=code, value_rub=value, nominal=1.0, source_id="cbr",
                    source_url=source_url, quoted_at=quoted_at, fetched_at=now,
                )
                session.add(last_row)
            if last_row is not None:
                latest.append(last_row)
        await session.flush()
        return latest

    @classmethod
    async def latest_rate(cls, session: AsyncSession, code: str) -> NatReferenceRateSnapshot | None:
        return await session.scalar(
            select(NatReferenceRateSnapshot)
            .where(NatReferenceRateSnapshot.instrument_code == code.upper())
            .order_by(NatReferenceRateSnapshot.quoted_at.desc(), NatReferenceRateSnapshot.id.desc())
            .limit(1)
        )

    @classmethod
    def _trade_result(cls, trade: NatInstrumentTrade) -> dict:
        return {
            "success": True,
            "trade_id": trade.id,
            "instrument_code": trade.instrument_code,
            "side": trade.side,
            "quantity": trade.quantity,
            "unit_price_rub": trade.unit_price_rub,
            "gross_rub": trade.gross_rub,
            "spread_rub": trade.spread_rub,
            "remaining_cash": trade.balance_after,
            "remaining_quantity": trade.position_after,
            "realized_pnl_rub": trade.realized_pnl_rub,
            "quoted_at": trade.created_at.isoformat(),
        }

    @classmethod
    async def trade(
        cls,
        session: AsyncSession,
        company_id: int,
        instrument_code: str,
        side: str,
        quantity: float,
        operation_key: str,
        now: datetime | None = None,
    ) -> dict:
        code = instrument_code.upper()
        side = side.lower()
        now = now or get_game_now()
        if code not in cls.SUPPORTED:
            raise ValueError("Unsupported reference instrument.")
        if side not in ("buy", "sell"):
            raise ValueError("Trade side must be buy or sell.")
        if quantity <= 0 or quantity > 1_000_000:
            raise ValueError("Trade quantity must be positive and within the safety limit.")
        if not operation_key:
            raise ValueError("Operation key is required.")

        existing = await session.scalar(
            select(NatInstrumentTrade).where(NatInstrumentTrade.operation_key == operation_key)
        )
        if existing:
            if existing.company_id != company_id or existing.instrument_code != code or existing.side != side or existing.quantity != quantity:
                raise ValueError("Operation key was already used for a different trade.")
            return cls._trade_result(existing)

        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if not company:
            raise ValueError("Company not found.")
        snapshot = await cls.latest_rate(session, code)
        if not snapshot or now - snapshot.quoted_at > cls.MAX_RATE_AGE:
            raise StaleReferenceRate("Fresh official reference rate is unavailable; trading is suspended.")

        position = await session.scalar(
            select(NatInstrumentPosition).where(
                NatInstrumentPosition.company_id == company_id,
                NatInstrumentPosition.instrument_code == code,
            ).with_for_update()
        )
        if not position:
            position = NatInstrumentPosition(company_id=company_id, instrument_code=code, quantity=0.0, avg_cost_rub=0.0, updated_at=now)
            session.add(position)

        reference = float(snapshot.value_rub)
        unit_price = round(reference * (1 + cls.SPREAD_RATE if side == "buy" else 1 - cls.SPREAD_RATE), 6)
        gross = round(unit_price * quantity, 2)
        spread = round(abs(unit_price - reference) * quantity, 2)
        if side == "buy":
            if company.cash < gross:
                raise ValueError("Insufficient cash.")
            previous_cost = position.avg_cost_rub * position.quantity
            company.cash = round(company.cash - gross, 2)
            position.quantity = round(position.quantity + quantity, 8)
            position.avg_cost_rub = round((previous_cost + gross) / position.quantity, 6)
            realized_pnl = 0.0
        else:
            if position.quantity < quantity:
                raise ValueError("Insufficient instrument holdings.")
            realized_pnl = round(gross - position.avg_cost_rub * quantity, 2)
            company.cash = round(company.cash + gross, 2)
            position.quantity = round(position.quantity - quantity, 8)
            if position.quantity == 0:
                position.avg_cost_rub = 0.0
        position.updated_at = now
        trade = NatInstrumentTrade(
            operation_key=operation_key,
            company_id=company_id,
            instrument_code=code,
            side=side,
            quantity=quantity,
            unit_price_rub=unit_price,
            gross_rub=gross,
            spread_rub=spread,
            balance_after=company.cash,
            position_after=position.quantity,
            avg_cost_after_rub=position.avg_cost_rub,
            realized_pnl_rub=realized_pnl,
            source_snapshot_id=snapshot.id,
            created_at=now,
        )
        session.add(trade)
        await session.flush()
        return cls._trade_result(trade)

    @classmethod
    async def catalog(cls, session: AsyncSession, now: datetime | None = None) -> list[dict]:
        now = now or get_game_now()
        result = []
        for code in cls.SUPPORTED:
            row = await cls.latest_rate(session, code)
            if not row:
                result.append({"code": code, "available": False})
                continue
            history_rows = (await session.execute(
                select(NatReferenceRateSnapshot)
                .where(NatReferenceRateSnapshot.instrument_code == code)
                .order_by(NatReferenceRateSnapshot.quoted_at.desc(), NatReferenceRateSnapshot.id.desc())
                .limit(420)
            )).scalars().all()
            result.append({
                "code": code,
                "available": now - row.quoted_at <= cls.MAX_RATE_AGE,
                "reference_rub": row.value_rub,
                "buy_rub": round(row.value_rub * (1 + cls.SPREAD_RATE), 6),
                "sell_rub": round(row.value_rub * (1 - cls.SPREAD_RATE), 6),
                "quoted_at": row.quoted_at.isoformat(),
                "source": row.source_url,
                "history": [
                    {"timestamp": point.quoted_at.isoformat(), "value": point.value_rub}
                    for point in reversed(history_rows)
                ],
            })
        return result

    @staticmethod
    async def portfolio(session: AsyncSession, company_id: int) -> list[dict]:
        rows = (await session.execute(
            select(NatInstrumentPosition)
            .where(NatInstrumentPosition.company_id == company_id)
            .order_by(NatInstrumentPosition.instrument_code)
        )).scalars().all()
        return [{
            "instrument_code": row.instrument_code,
            "quantity": row.quantity,
            "avg_cost_rub": row.avg_cost_rub,
        } for row in rows]


__all__ = ["ReferenceInstrumentService", "StaleReferenceRate"]
