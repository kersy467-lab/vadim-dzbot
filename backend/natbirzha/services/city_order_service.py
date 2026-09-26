"""Escrow-backed city orders with restart-safe sector rotation and delivery."""

from __future__ import annotations

import math
import secrets
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.city_orders import (
    NatCityOrder, NatCityOrderCycleState, NatCityOrderDelivery,
)
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, NatInventory
from backend.natbirzha.services.city_order_rates import (
    active_city_order_industries, primary_output, sector_output_rate,
)
from backend.natbirzha.services.company_profit_ledger_service import CompanyProfitLedgerService
from backend.natbirzha.services.city_order_helpers import quantity, request_hash, serialize_order
from backend.natbirzha.services.market_settlement import money
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


class CityOrderService:
    ORDER_INTERVAL = timedelta(minutes=30)
    ORDER_TTL = timedelta(hours=1)
    order_model = NatCityOrder

    @classmethod
    async def issue_due(cls, session: AsyncSession, *, now: datetime | None = None) -> dict[str, Any]:
        now = normalize_dt(now or get_game_now())
        expired_count = await cls.expire_due(session, now=now)
        treasury = await StateTreasuryService.get_or_create(
            session, commit=False, for_update=True
        )
        slot = cls._scheduled_slot(now)
        if await cls.count_open_orders(session, now=now) >= 2:
            return {"created": False, "reason": "open_order_limit", "expired_count": expired_count}
        state = await cls._locked_cycle_state(session)
        if state.last_scheduled_slot and state.last_scheduled_slot >= slot:
            return {"created": False, "reason": "slot_already_processed", "expired_count": expired_count}
        if await session.scalar(select(NatCityOrder.id).where(NatCityOrder.scheduled_slot == slot)):
            return {"created": False, "reason": "slot_already_issued", "expired_count": expired_count}

        industries = active_city_order_industries()
        if not industries:
            return {"created": False, "reason": "no_active_industries", "expired_count": expired_count}
        pending = [sector for sector in (state.pending_industries or [])
                   if sector in industries and sector not in (state.issued_industries or [])]
        newly_active = [sector for sector in industries
                        if sector not in pending and sector not in (state.issued_industries or [])]
        secrets.SystemRandom().shuffle(newly_active)
        pending.extend(newly_active)
        issued = list(state.issued_industries or [])
        cycle_number = int(state.cycle_number or 1)
        if not pending:
            cycle_number += 1
            issued = []
            pending = list(industries)
            secrets.SystemRandom().shuffle(pending)

        industry = pending[0]
        output = primary_output(industry)
        if output is None:
            return {"created": False, "reason": "industry_has_no_priced_output", "expired_count": expired_count}
        item_id, starter = output
        price = Decimal(str(CANONICAL_ITEMS[item_id]["base_price"]))
        hourly_rate = await sector_output_rate(session, industry, item_id, starter)
        quantity = cls._quantity(Decimal(str(hourly_rate)) * Decimal("0.5"))
        if quantity <= 0:
            return {"created": False, "reason": "industry_has_no_output_rate", "expired_count": expired_count}

        available_cash = max(
            Decimal(0),
            Decimal(str(treasury.cash or 0.0)).quantize(Decimal("0.01"), rounding=ROUND_DOWN),
        )
        reserve = money(price * quantity)
        if reserve > available_cash:
            quantity = cls._quantity(available_cash / price)
            reserve = money(price * quantity)
        if quantity <= 0 or reserve <= 0:
            return {"created": False, "reason": "treasury_budget_too_small", "expired_count": expired_count}

        order = NatCityOrder(
            scheduled_slot=slot,
            industry=industry,
            item_id=item_id,
            quantity=float(quantity),
            remaining_quantity=float(quantity),
            unit_price=float(price),
            reserved_cash=float(reserve),
            issued_at=now,
            expires_at=now + cls.ORDER_TTL,
        )
        treasury.cash = float(money(available_cash - reserve))
        session.add(order)
        await session.flush()

        state.cycle_number = cycle_number
        state.pending_industries = pending[1:]
        state.issued_industries = [*issued, industry]
        state.last_scheduled_slot = slot
        await session.flush()
        return {"created": True, "order": cls.serialize(order), "expired_count": expired_count}

    @classmethod
    async def deliver(
        cls,
        session: AsyncSession,
        company_id: int,
        order_id: int,
        quantity: float,
        *,
        idempotency_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        key = str(idempotency_key or "").strip()
        if not key or len(key) > 160:
            raise ValueError("Нужен корректный ключ идемпотентности")
        try:
            numeric_quantity = float(quantity)
        except (TypeError, ValueError) as exc:
            raise ValueError("Количество поставки должно быть числом") from exc
        if not math.isfinite(numeric_quantity) or numeric_quantity <= 0:
            raise ValueError("Количество поставки должно быть больше нуля")
        requested = cls._quantity(Decimal(str(numeric_quantity)))
        if requested <= 0:
            raise ValueError("Количество поставки меньше минимального шага")
        request_digest = request_hash(order_id, requested)

        replay = await session.scalar(select(NatCityOrderDelivery).where(
            NatCityOrderDelivery.company_id == company_id,
            NatCityOrderDelivery.order_id == order_id,
            NatCityOrderDelivery.idempotency_key == key,
        ))
        if replay:
            if replay.request_hash != request_digest:
                raise ValueError("Ключ идемпотентности уже использован с другими данными")
            return {**dict(replay.response_json or {}), "replayed": True}

        order = await session.scalar(
            select(NatCityOrder).where(NatCityOrder.id == order_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if order is None:
            raise ValueError("Городской заказ не найден")
        # Recheck after acquiring the order lock to close same-key concurrent
        # retries that both missed the pre-lock lookup.
        replay = await session.scalar(select(NatCityOrderDelivery).where(
            NatCityOrderDelivery.company_id == company_id,
            NatCityOrderDelivery.order_id == order_id,
            NatCityOrderDelivery.idempotency_key == key,
        ))
        if replay:
            if replay.request_hash != request_digest:
                raise ValueError("Ключ идемпотентности уже использован с другими данными")
            return {**dict(replay.response_json or {}), "replayed": True}

        now = normalize_dt(now or get_game_now())
        if order.status != "OPEN":
            raise ValueError("Городской заказ уже закрыт")
        if now >= normalize_dt(order.expires_at):
            # Refund escrow before any company lock: tax settlement follows
            # treasury -> company lock order.
            treasury = await StateTreasuryService.get_or_create(
                session, commit=False, for_update=True
            )
            cls._expire_locked_order(order, treasury)
            await session.flush()
            return {"success": False, "reason": "order_expired"}

        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if company is None:
            raise ValueError("Компания не найдена")
        if requested > Decimal(str(order.remaining_quantity)) + Decimal("0.0000001"):
            raise ValueError("Количество превышает остаток заказа")

        inventory = await session.scalar(
            select(NatInventory).where(
                NatInventory.company_id == company_id,
                NatInventory.item_id == order.item_id,
            ).with_for_update().execution_options(populate_existing=True)
        )
        if inventory is None:
            raise ValueError("На складе нет доступного ресурса")
        deliver_qty = min(requested, cls._quantity(Decimal(str(order.remaining_quantity))))
        available = cls._quantity(Decimal(str(inventory.available_quantity)))
        if deliver_qty > available:
            raise ValueError("Недостаточно доступного ресурса на складе")

        before_delivered = Decimal(str(order.quantity)) - Decimal(str(order.remaining_quantity))
        after_delivered = before_delivered + deliver_qty
        cash_before = money(Decimal(str(order.unit_price)) * before_delivered)
        cash_after = money(Decimal(str(order.unit_price)) * after_delivered)
        payout = cash_after - cash_before
        if payout <= 0:
            raise ValueError("Количество поставки меньше минимальной оплачиваемой суммы")
        if payout < 0 or payout > money(Decimal(str(order.reserved_cash))):
            raise ValueError("Нарушен резерв городского заказа")
        cogs = round(float(deliver_qty) * max(0.0, float(inventory.avg_cost_basis or 0.0)), 6)
        inventory.quantity = round(max(0.0, float(inventory.quantity) - float(deliver_qty)), 6)
        company.cash = float(money(Decimal(str(company.cash or 0.0)) + payout))
        order.remaining_quantity = float(cls._quantity(
            Decimal(str(order.quantity)) - after_delivered
        ))
        order.paid_cash = float(money(Decimal(str(order.paid_cash or 0.0)) + payout))
        order.reserved_cash = float(money(Decimal(str(order.reserved_cash)) - payout))
        if order.remaining_quantity <= 0:
            order.remaining_quantity = 0.0
            order.reserved_cash = 0.0
            order.status = "FULFILLED"
            order.closed_at = now

        await CompanyProfitLedgerService.record(
            session, company.id, now,
            revenue=float(payout), cost_of_goods_sold=cogs,
        )
        response = {
            "success": True,
            "order_id": order.id,
            "item_id": order.item_id,
            "quantity": float(deliver_qty),
            "cash_amount": float(payout),
            "company_cash": float(company.cash),
            "order_status": order.status,
            "remaining_quantity": float(order.remaining_quantity),
            "replayed": False,
        }
        session.add(NatCityOrderDelivery(
            order_id=order.id,
            company_id=company.id,
            seller_industry=company.specialization,
            item_id=order.item_id,
            idempotency_key=key,
            request_hash=request_digest,
            quantity=float(deliver_qty),
            cash_amount=float(payout),
            cost_of_goods_sold=cogs,
            response_json=response,
            created_at=now,
        ))
        await session.flush()
        return response

    @classmethod
    async def expire_due(cls, session: AsyncSession, *, now: datetime | None = None) -> int:
        now = normalize_dt(now or get_game_now())
        orders = (await session.execute(
            select(NatCityOrder).where(
                NatCityOrder.status == "OPEN", NatCityOrder.expires_at <= now,
            ).order_by(NatCityOrder.id).with_for_update(skip_locked=True)
        )).scalars().all()
        if not orders:
            return 0
        treasury = await StateTreasuryService.get_or_create(
            session, commit=False, for_update=True
        )
        for order in orders:
            cls._expire_locked_order(order, treasury)
        await session.flush()
        return len(orders)

    @classmethod
    async def list_orders(
        cls, session: AsyncSession, *, now: datetime | None = None, include_closed: bool = False,
    ) -> list[dict[str, Any]]:
        now = normalize_dt(now or get_game_now())
        statement = select(NatCityOrder)
        if not include_closed:
            statement = statement.where(
                NatCityOrder.status == "OPEN", NatCityOrder.expires_at > now,
            )
        statement = statement.order_by(NatCityOrder.issued_at.desc(), NatCityOrder.id.desc()).limit(100)
        rows = (await session.execute(statement)).scalars().all()
        return [cls.serialize(row) for row in rows]

    @classmethod
    async def count_open_orders(cls, session: AsyncSession, *, now: datetime | None = None) -> int:
        now = normalize_dt(now or get_game_now())
        return len((await session.execute(select(NatCityOrder.id).where(
            NatCityOrder.status == "OPEN", NatCityOrder.expires_at > now,
        ))).scalars().all())

    @classmethod
    async def get_order(cls, session: AsyncSession, order_id: int) -> dict[str, Any] | None:
        order = await session.get(NatCityOrder, order_id)
        return cls.serialize(order) if order else None

    @staticmethod
    async def get_delivery_by_key(session: AsyncSession, key: str) -> NatCityOrderDelivery | None:
        return await session.scalar(select(NatCityOrderDelivery).where(
            NatCityOrderDelivery.idempotency_key == key
        ).order_by(NatCityOrderDelivery.id.desc()).limit(1))

    @classmethod
    def serialize(cls, order: NatCityOrder) -> dict[str, Any]:
        return serialize_order(order)

    @classmethod
    def _scheduled_slot(cls, now: datetime) -> datetime:
        return now.replace(
            minute=(now.minute // 30) * 30, second=0, microsecond=0
        )

    @classmethod
    def _quantity(cls, value: Decimal) -> Decimal:
        return quantity(value)

    @classmethod
    async def _locked_cycle_state(cls, session: AsyncSession) -> NatCityOrderCycleState:
        state = await session.scalar(
            select(NatCityOrderCycleState).where(NatCityOrderCycleState.id == 1)
            .with_for_update().execution_options(populate_existing=True)
        )
        if state is not None:
            return state
        try:
            async with session.begin_nested():
                state = NatCityOrderCycleState(id=1)
                session.add(state)
                await session.flush()
        except IntegrityError:
            state = await session.scalar(
                select(NatCityOrderCycleState).where(NatCityOrderCycleState.id == 1)
                .with_for_update().execution_options(populate_existing=True)
            )
        return state

    @staticmethod
    def _expire_locked_order(order: NatCityOrder, treasury: NatStateTreasury) -> None:
        refund = money(Decimal(str(order.reserved_cash or 0.0)))
        treasury.cash = float(money(Decimal(str(treasury.cash or 0.0)) + refund))
        order.reserved_cash = 0.0
        order.status = "EXPIRED"
        order.closed_at = order.expires_at

__all__ = ["CityOrderService"]
