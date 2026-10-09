"""Treasury fiscal policy, reserve stock and foreign resource exports."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.creator import NatCreatorAuditLog
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, get_item_base_price, get_item_name
from backend.natbirzha.models.npc import NatStateReserveStock
from backend.natbirzha.services.economy_metrics_service import EconomyMetricsService
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


class StateEconomyService:
    DEFAULT_TRIGGER_CASH = 1_000_000_000_000.0
    DEFAULT_TAX_RATE = 0.30
    DEFAULT_BUYBACK_MULTIPLIER = 0.90
    DEFAULT_RETAIL_MULTIPLIER = 1.10
    EXPORT_INTERVAL = timedelta(minutes=15)
    EXPORT_FRACTION = 0.10
    EXPORT_POLL_SECONDS = 60

    @classmethod
    def is_default_mode(cls, treasury_cash: float) -> bool:
        return float(treasury_cash or 0.0) < cls.DEFAULT_TRIGGER_CASH

    @classmethod
    def tax_rate(
        cls,
        treasury_cash: float,
        *,
        normal_rate: float,
        sabotage_delta: float = 0.0,
    ) -> float:
        rate = max(0.0, float(normal_rate)) + float(sabotage_delta or 0.0)
        if cls.is_default_mode(treasury_cash):
            rate = max(cls.DEFAULT_TAX_RATE, rate)
        return round(max(0.0, rate), 4)

    @classmethod
    def apply_default_quote(cls, quote: dict[str, Any], *, default_mode: bool) -> dict[str, Any]:
        result = dict(quote)
        result["state_default_mode"] = bool(default_mode)
        if not default_mode:
            return result
        result["npc_buy_price"] = round(
            float(result["npc_buy_price"]) * cls.DEFAULT_BUYBACK_MULTIPLIER, 2
        )
        result["npc_sell_price"] = round(
            float(result["npc_sell_price"]) * cls.DEFAULT_RETAIL_MULTIPLIER, 2
        )
        base_price = float(result.get("base_price") or 0.0)
        result["spread_pct"] = round(
            ((result["npc_sell_price"] - result["npc_buy_price"]) / base_price) * 100, 1
        ) if base_price else 0.0
        return result

    @staticmethod
    def _quantity_for_export(available: float) -> float:
        available = max(0.0, round(float(available or 0.0), 2))
        if available <= 0:
            return 0.0
        return round(min(available, max(0.01, available * StateEconomyService.EXPORT_FRACTION)), 2)

    @classmethod
    async def add_state_stock(
        cls,
        session: AsyncSession,
        *,
        item_id: str,
        quantity: float,
        unit_cost: float,
        now: datetime | None = None,
    ) -> NatStateReserveStock:
        now = now or get_game_now()
        stock = await session.scalar(
            select(NatStateReserveStock)
            .where(NatStateReserveStock.item_id == item_id)
            .with_for_update()
        )
        if stock is None:
            try:
                async with session.begin_nested():
                    stock = NatStateReserveStock(
                        item_id=item_id,
                        quantity=0.0,
                        average_cost_basis=0.0,
                        updated_at=now,
                    )
                    session.add(stock)
                    await session.flush()
            except IntegrityError:
                stock = await session.scalar(
                    select(NatStateReserveStock)
                    .where(NatStateReserveStock.item_id == item_id)
                    .with_for_update()
                )
        previous_quantity = float(stock.quantity or 0.0)
        incoming_quantity = round(float(quantity), 2)
        next_quantity = round(previous_quantity + incoming_quantity, 2)
        weighted_cost = (
            previous_quantity * float(stock.average_cost_basis or 0.0)
            + incoming_quantity * max(0.0, float(unit_cost))
        )
        stock.quantity = next_quantity
        stock.average_cost_basis = round(weighted_cost / next_quantity, 6) if next_quantity else 0.0
        stock.updated_at = now
        return stock

    @classmethod
    async def consume_state_stock(
        cls,
        session: AsyncSession,
        *,
        item_id: str,
        quantity: float,
        now: datetime | None = None,
    ) -> float:
        stock = await session.scalar(
            select(NatStateReserveStock)
            .where(NatStateReserveStock.item_id == item_id)
            .with_for_update()
        )
        if stock is None:
            return 0.0
        consumed = min(max(0.0, float(quantity)), max(0.0, float(stock.quantity or 0.0)))
        stock.quantity = round(float(stock.quantity or 0.0) - consumed, 2)
        if stock.quantity <= 0:
            stock.quantity = 0.0
            stock.average_cost_basis = 0.0
        stock.updated_at = now or get_game_now()
        return round(consumed, 2)

    @classmethod
    async def run_foreign_export_cycle(
        cls,
        session: AsyncSession,
        *,
        now: datetime | None = None,
        commit: bool = False,
    ) -> dict[str, Any]:
        current = now or get_game_now()
        treasury = await StateTreasuryService.get_or_create(
            session, commit=False, for_update=True
        )
        result: dict[str, Any] = {
            "enabled": bool(treasury.foreign_exports_enabled),
            "quantity_sold": 0.0,
            "cash_received": 0.0,
            "sales": [],
        }
        if not treasury.foreign_exports_enabled:
            return result

        last_run = treasury.last_foreign_export_at
        if last_run is not None:
            comparable_now = current.replace(tzinfo=None) if current.tzinfo else current
            comparable_last = last_run.replace(tzinfo=None) if last_run.tzinfo else last_run
            if comparable_now - comparable_last < cls.EXPORT_INTERVAL:
                result["next_export_at"] = (comparable_last + cls.EXPORT_INTERVAL).isoformat()
                return result

        stocks = list((await session.execute(
            select(NatStateReserveStock)
            .where(NatStateReserveStock.quantity > 0)
            .order_by(NatStateReserveStock.item_id)
            .with_for_update()
        )).scalars().all())
        total_cash = 0.0
        for stock in stocks:
            if stock.item_id not in CANONICAL_ITEMS:
                continue
            quantity = cls._quantity_for_export(stock.quantity)
            if quantity <= 0:
                continue
            unit_price = get_item_base_price(stock.item_id)
            proceeds = round(unit_price * quantity, 2)
            stock.quantity = round(float(stock.quantity) - quantity, 2)
            if stock.quantity <= 0:
                stock.quantity = 0.0
                stock.average_cost_basis = 0.0
            stock.updated_at = current
            total_cash = round(total_cash + proceeds, 2)
            result["quantity_sold"] = round(result["quantity_sold"] + quantity, 2)
            sale = {
                "item_id": stock.item_id,
                "name": get_item_name(stock.item_id),
                "quantity": quantity,
                "unit_price": unit_price,
                "proceeds": proceeds,
            }
            result["sales"].append(sale)
            await EconomyMetricsService.record(
                session,
                company_id=None,
                flow="SOURCE",
                category="state_foreign_export",
                cash_amount=proceeds,
                item_id=stock.item_id,
                quantity=quantity,
                context={"market": "foreign"},
            )

        treasury.cash = round(float(treasury.cash or 0.0) + total_cash, 2)
        treasury.updated_at = current
        treasury.last_foreign_export_at = current
        result["cash_received"] = total_cash
        result["treasury_cash"] = round(float(treasury.cash), 2)
        if commit:
            await session.commit()
        else:
            await session.flush()
        return result

    @classmethod
    async def set_foreign_exports_enabled(
        cls,
        session: AsyncSession,
        *,
        enabled: bool,
        actor_id: int,
    ) -> dict[str, Any]:
        treasury = await StateTreasuryService.get_or_create(
            session, commit=False, for_update=True
        )
        treasury.foreign_exports_enabled = bool(enabled)
        treasury.updated_at = get_game_now()
        session.add(NatCreatorAuditLog(
            actor_id=int(actor_id),
            action="STATE_EXPORTS_ENABLED" if enabled else "STATE_EXPORTS_DISABLED",
            target_type="state_treasury",
            target_id=str(treasury.id),
            details="Включён экспорт запасов за границу" if enabled else "Выключен экспорт запасов за границу",
        ))
        await session.commit()
        return await cls.creator_snapshot(session)

    @classmethod
    async def creator_snapshot(cls, session: AsyncSession) -> dict[str, Any]:
        treasury = await StateTreasuryService.get_or_create(session, commit=False)
        from backend.natbirzha.config import nat_settings
        from backend.natbirzha.services.sabotage_service import SabotageService

        default_mode = cls.is_default_mode(treasury.cash)
        normal_tax_rate = float(nat_settings.TAX_RATE)
        tax_rate = cls.tax_rate(
            treasury.cash,
            normal_rate=normal_tax_rate,
            sabotage_delta=SabotageService.get_tax_rate_delta(),
        )
        stocks = list((await session.execute(
            select(NatStateReserveStock)
            .where(NatStateReserveStock.quantity > 0)
            .order_by(NatStateReserveStock.item_id)
        )).scalars().all())
        stock_rows = []
        for stock in stocks:
            if stock.item_id not in CANONICAL_ITEMS:
                continue
            quantity = float(stock.quantity or 0.0)
            unit_price = get_item_base_price(stock.item_id)
            stock_rows.append({
                "item_id": stock.item_id,
                "name": get_item_name(stock.item_id),
                "quantity": round(quantity, 2),
                "export_quantity_per_cycle": cls._quantity_for_export(quantity),
                "export_unit_price": unit_price,
                "export_estimate": round(unit_price * cls._quantity_for_export(quantity), 2),
            })
        return {
            "treasury_cash": round(float(treasury.cash or 0.0), 2),
            "default_mode": default_mode,
            "default_threshold_cash": cls.DEFAULT_TRIGGER_CASH,
            "tax_rate_pct": round(tax_rate * 100, 2),
            "normal_tax_rate_pct": round(normal_tax_rate * 100, 2),
            "foreign_exports_enabled": bool(treasury.foreign_exports_enabled),
            "export_interval_minutes": int(cls.EXPORT_INTERVAL.total_seconds() // 60),
            "export_fraction_pct": round(cls.EXPORT_FRACTION * 100, 2),
            "last_export_at": treasury.last_foreign_export_at.isoformat() if treasury.last_foreign_export_at else None,
            "stock": stock_rows,
        }

    @classmethod
    async def run_export_worker(
        cls,
        session_factory: Callable[[], Any],
        *,
        logger: Any = None,
    ) -> None:
        while True:
            try:
                async with session_factory() as session:
                    result = await cls.run_foreign_export_cycle(session, commit=True)
                if result.get("quantity_sold", 0) > 0 and logger:
                    logger.info(
                        "State exported %.2f resource units for %.2f cash",
                        result["quantity_sold"], result["cash_received"],
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                if logger:
                    logger.exception("State foreign export cycle failed")
            await asyncio.sleep(cls.EXPORT_POLL_SECONDS)


__all__ = ["StateEconomyService"]
