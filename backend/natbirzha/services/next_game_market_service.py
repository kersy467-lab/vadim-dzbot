"""Limit order book for the isolated NATBIRZHA 2.0 economy."""

from datetime import datetime, timezone
from math import isfinite
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.next_game import (
    NatNextGameCompany,
    NatNextGameMarketOrder,
    NatNextGameMarketTrade,
    NatNextGameTreasury,
)
from backend.natbirzha.next_game_catalog import get_next_game_items
from backend.natbirzha.services.next_game_service import (
    MAX_INVENTORY_PER_ITEM,
    MAX_TRADE_QUANTITY,
    NextGameService,
)
from backend.natbirzha.services.next_game_market_read_service import NextGameMarketReadService
from backend.natbirzha.services.next_game_advance_service import NextGameAdvanceService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _cash(value: float) -> float:
    return round(float(value), 8)


class NextGameMarketService:
    """Owns order reservations, price-time matching, cancellation and history."""

    @classmethod
    async def lock_orderbook(cls, session: AsyncSession) -> None:
        """Serialize market mutations and protect company rows on both databases."""
        if session.get_bind().dialect.name == "sqlite":
            # SQLite has no SELECT FOR UPDATE. Updating the singleton treasury row
            # obtains its database write lock before the idempotency read in routes.
            result = await session.execute(
                update(NatNextGameTreasury)
                .where(NatNextGameTreasury.id == 1)
                .values(cash=NatNextGameTreasury.cash)
            )
            if result.rowcount == 0:
                await NextGameService._treasury(session)
                await session.execute(
                    update(NatNextGameTreasury)
                    .where(NatNextGameTreasury.id == 1)
                    .values(cash=NatNextGameTreasury.cash)
                )
            (await session.scalars(
                select(NatNextGameCompany).order_by(NatNextGameCompany.id).with_for_update()
            )).all()
            return

        # A consistent company-id order prevents two cross-company fills from
        # acquiring buyer/seller rows in opposite order. Existing 2.0 services
        # lock one company before the treasury, so take the same order here.
        (await session.scalars(
            select(NatNextGameCompany).order_by(NatNextGameCompany.id).with_for_update()
        )).all()
        treasury = await session.scalar(
            select(NatNextGameTreasury).where(NatNextGameTreasury.id == 1).with_for_update()
        )
        if treasury is None:
            await NextGameService._treasury(session)

    @staticmethod
    async def reserved_sell_quantity(
        session: AsyncSession, company_id: int, item_id: str
    ) -> float:
        reserved = await session.scalar(
            select(func.coalesce(func.sum(NatNextGameMarketOrder.remaining_quantity), 0.0)).where(
                NatNextGameMarketOrder.company_id == company_id,
                NatNextGameMarketOrder.item_id == item_id,
                NatNextGameMarketOrder.side == "SELL",
                NatNextGameMarketOrder.status == "OPEN",
            )
        )
        return float(reserved or 0.0)

    @classmethod
    async def create_limit_order(
        cls,
        session: AsyncSession,
        owner_tg_id: int,
        item_id: str,
        side: str,
        quantity: float,
        limit_price: float,
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        item_id = str(item_id or "").strip()
        normalized_side = str(side or "").upper()
        items = get_next_game_items()
        if item_id not in items:
            raise ValueError("Такого товара нет в рынке 2.0")
        if normalized_side not in {"BUY", "SELL"}:
            raise ValueError("Выберите покупку или продажу")
        try:
            amount = float(quantity)
            price = float(limit_price)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Количество и цена должны быть числами") from exc
        if not isfinite(amount):
            raise ValueError("Количество должно быть конечное число")
        rounded_amount = round(amount, 4)
        if abs(amount - rounded_amount) > 1e-9:
            raise ValueError("Количество можно указать максимум с 4 знаками после запятой")
        amount = rounded_amount
        if amount <= 0 or amount > MAX_TRADE_QUANTITY:
            raise ValueError("Количество должно быть больше нуля и не выше 10 000")
        if not isfinite(price) or price <= 0:
            raise ValueError("Лимитная цена должна быть конечным числом больше нуля")
        rounded_price = round(price, 4)
        if abs(price - rounded_price) > 1e-9:
            raise ValueError("Лимитную цену можно указать максимум с 4 знаками после запятой")
        price = rounded_price
        notional = amount * price
        if not isfinite(notional) or notional <= 0:
            raise ValueError("Сумма заявки должна быть конечным положительным числом")
        reserve = _cash(notional) if normalized_side == "BUY" else 0.0

        await cls.lock_orderbook(session)
        current = now or _utcnow()
        await NextGameService.settle_company(session, owner_tg_id, now=current)
        company = await NextGameService._owned_company(session, owner_tg_id)
        inventory = await NextGameService._inventory_row(session, company.id, item_id)
        if normalized_side == "BUY":
            if float(company.cash) + 1e-8 < reserve:
                raise ValueError("Недостаточно cash для резервирования заявки")
            company.cash = _cash(float(company.cash) - reserve)
        else:
            available = float(inventory.quantity if inventory else 0.0)
            if available + 1e-9 < amount:
                raise ValueError("Недостаточно товара на складе 2.0 для резервирования заявки")
            await NextGameService._change_inventory(
                session, company.id, item_id, -amount, row=inventory,
            )

        order = NatNextGameMarketOrder(
            company_id=company.id,
            item_id=item_id,
            side=normalized_side,
            limit_price=price,
            quantity=amount,
            remaining_quantity=amount,
            reserved_cash=reserve,
            status="OPEN",
            created_at=current,
            updated_at=current,
        )
        session.add(order)
        await session.flush()
        trades = await cls._match_order(session, order, current)
        await NextGameAdvanceService.fund(session, company, order, now=current)
        await session.flush()
        order_payload = (await NextGameAdvanceService.decorate_orders(
            session, [NextGameMarketReadService.order_payload(order, company.name)],
        ))[0]
        return {
            "success": True,
            "order": order_payload,
            "executed_quantity": round(sum(row["quantity"] for row in trades), 4),
            "remaining_quantity": round(float(order.remaining_quantity), 4),
            "trades": trades,
            "company": NextGameService.snapshot_company(company),
        }

    @classmethod
    async def _match_order(
        cls,
        session: AsyncSession,
        incoming: NatNextGameMarketOrder,
        current: datetime,
    ) -> list[dict[str, Any]]:
        if incoming.side == "BUY":
            criteria = (
                NatNextGameMarketOrder.side == "SELL",
                NatNextGameMarketOrder.limit_price <= incoming.limit_price,
            )
            sorting = (NatNextGameMarketOrder.limit_price.asc(), NatNextGameMarketOrder.id.asc())
        else:
            criteria = (
                NatNextGameMarketOrder.side == "BUY",
                NatNextGameMarketOrder.limit_price >= incoming.limit_price,
            )
            sorting = (NatNextGameMarketOrder.limit_price.desc(), NatNextGameMarketOrder.id.asc())
        makers = list((await session.scalars(
            select(NatNextGameMarketOrder).where(
                NatNextGameMarketOrder.item_id == incoming.item_id,
                NatNextGameMarketOrder.status == "OPEN",
                NatNextGameMarketOrder.remaining_quantity > 0,
                NatNextGameMarketOrder.company_id != incoming.company_id,
                *criteria,
            ).order_by(*sorting).with_for_update()
        )).all())
        executed: list[dict[str, Any]] = []
        for maker in makers:
            if incoming.remaining_quantity <= 1e-9:
                break
            buyer_order = incoming if incoming.side == "BUY" else maker
            seller_order = maker if incoming.side == "BUY" else incoming
            buyer = await session.get(NatNextGameCompany, buyer_order.company_id)
            seller = await session.get(NatNextGameCompany, seller_order.company_id)
            if buyer is None or seller is None or buyer.owner_tg_id == seller.owner_tg_id:
                continue

            inventory = await NextGameService._inventory_row(session, buyer.id, incoming.item_id)
            existing_quantity = float(inventory.quantity if inventory else 0.0)
            sell_escrow = await cls.reserved_sell_quantity(session, buyer.id, incoming.item_id)
            from backend.natbirzha.services.next_game_operations_effects import warehouse_capacity
            capacity = max(0.0, await warehouse_capacity(session, buyer.id) - existing_quantity - sell_escrow)
            fill = round(min(
                float(incoming.remaining_quantity),
                float(maker.remaining_quantity),
                capacity,
            ), 4)
            if fill <= 1e-9:
                continue

            # The incoming order is always newer; every matching maker predates it.
            price = float(maker.limit_price)
            trade_value = _cash(fill * price)
            old_reserve = float(buyer_order.reserved_cash)
            next_buyer_quantity = max(0.0, round(float(buyer_order.remaining_quantity) - fill, 4))
            next_reserve = _cash(next_buyer_quantity * float(buyer_order.limit_price))
            if next_buyer_quantity <= 1e-9:
                next_buyer_quantity = 0.0
                next_reserve = 0.0
            released = max(0.0, _cash(old_reserve - next_reserve))
            buyer.cash = _cash(float(buyer.cash) + max(0.0, released - trade_value))
            repayment = await NextGameAdvanceService.repay_fill(session, seller_order, trade_value)
            seller.cash = _cash(float(seller.cash) + trade_value - repayment)
            buyer_order.remaining_quantity = next_buyer_quantity
            buyer_order.reserved_cash = next_reserve
            seller_order.remaining_quantity = max(
                0.0, round(float(seller_order.remaining_quantity) - fill, 4)
            )
            if seller_order.remaining_quantity <= 1e-9:
                seller_order.remaining_quantity = 0.0
            buyer_order.status = "FILLED" if buyer_order.remaining_quantity == 0 else "OPEN"
            seller_order.status = "FILLED" if seller_order.remaining_quantity == 0 else "OPEN"
            buyer_order.updated_at = current
            seller_order.updated_at = current
            await NextGameService._change_inventory(
                session, buyer.id, incoming.item_id, fill, row=inventory,
            )
            trade = NatNextGameMarketTrade(
                buy_order_id=buyer_order.id,
                sell_order_id=seller_order.id,
                buyer_company_id=buyer.id,
                seller_company_id=seller.id,
                item_id=incoming.item_id,
                quantity=fill,
                price=price,
                executed_at=current,
            )
            session.add(trade)
            await session.flush()
            executed.append(NextGameMarketReadService.trade_payload(trade, buyer.name, seller.name))
        return executed

    @classmethod
    async def cancel_order(
        cls,
        session: AsyncSession,
        owner_tg_id: int,
        order_id: int,
    ) -> dict[str, Any]:
        await cls.lock_orderbook(session)
        company = await NextGameService._owned_company(session, owner_tg_id)
        order = await session.scalar(
            select(NatNextGameMarketOrder).where(NatNextGameMarketOrder.id == int(order_id))
            .with_for_update()
        )
        if order is None or order.company_id != company.id:
            raise ValueError("Открытая заявка не найдена")
        if order.status != "OPEN" or order.remaining_quantity <= 0:
            raise ValueError("Заявка уже закрыта")
        funded = (await NextGameAdvanceService.decorate_orders(
            session, [NextGameMarketReadService.order_payload(order, company.name)],
        ))[0]
        if funded["advance_locked"]:
            raise ValueError("Казна профинансировала ордер: снять товар до погашения аванса нельзя")
        released_cash = 0.0
        released_quantity = 0.0
        if order.side == "BUY":
            released_cash = float(order.reserved_cash)
            company.cash = _cash(float(company.cash) + released_cash)
            order.reserved_cash = 0.0
        else:
            released_quantity = float(order.remaining_quantity)
            await NextGameService._change_inventory(
                session, company.id, order.item_id, released_quantity,
            )
        order.status = "CANCELLED"
        order.updated_at = _utcnow()
        await session.flush()
        return {
            "success": True,
            "order": NextGameMarketReadService.order_payload(order, company.name),
            "released_cash": _cash(released_cash),
            "released_quantity": round(released_quantity, 4),
            "company": NextGameService.snapshot_company(company),
        }

    @classmethod
    async def list_market(
        cls, session: AsyncSession, *, item_id: str | None = None
    ) -> dict[str, Any]:
        return await NextGameMarketReadService.list_market(session, item_id=item_id)

    @classmethod
    async def list_my_orders(
        cls, session: AsyncSession, owner_tg_id: int, *, item_id: str | None = None
    ) -> list[dict[str, Any]]:
        return await NextGameMarketReadService.list_my_orders(
            session, owner_tg_id, item_id=item_id,
        )

    @classmethod
    async def market_snapshot(
        cls, session: AsyncSession, *, company_id: int, item_ids: Any
    ) -> dict[str, Any]:
        return await NextGameMarketReadService.market_snapshot(
            session, company_id=company_id, item_ids=item_ids,
        )


__all__ = ["NextGameMarketService"]
