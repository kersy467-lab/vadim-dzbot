"""Exact cent arithmetic for commodity market escrow and settlement."""

from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.market import NatMarketOrder, NatMarketTrade


def money(value: Decimal | float) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


async def remaining_buy_escrow(session: AsyncSession, order: NatMarketOrder) -> Decimal:
    remaining = money(Decimal(str(order.price)) * Decimal(str(order.quantity)))
    trades = (await session.execute(
        select(NatMarketTrade).where(NatMarketTrade.buy_order_id == order.id).order_by(NatMarketTrade.id)
    )).scalars().all()
    for trade in trades:
        remaining -= Decimal(str(trade.total_amount))
        improvement = money(
            max(Decimal(0), Decimal(str(order.price)) - Decimal(str(trade.price)))
            * Decimal(str(trade.quantity))
        )
        remaining -= min(improvement, max(Decimal(0), remaining))
    return max(Decimal(0), remaining)


async def cancel_market_order(
    session: AsyncSession, company: NatCompany, order_id: int, *, commit: bool = True
) -> bool:
    locked = (await session.execute(
        select(NatCompany).where(NatCompany.id == company.id).with_for_update()
    )).scalar_one_or_none()
    company = locked or company
    order = (await session.execute(
        select(NatMarketOrder).where(
            NatMarketOrder.id == order_id,
            NatMarketOrder.company_id == company.id,
            NatMarketOrder.status == "ACTIVE",
        ).with_for_update()
    )).scalar_one_or_none()
    if not order:
        return False
    if order.order_type == "BUY":
        refund = await remaining_buy_escrow(session, order)
        company.cash = float(money(Decimal(str(company.cash)) + refund))
    elif order.order_type == "SELL":
        inventory = await session.scalar(
            select(NatInventory).where(
                NatInventory.company_id == company.id, NatInventory.item_id == order.item_id
            ).with_for_update()
        )
        if inventory:
            inventory.reserved_quantity = max(0.0, inventory.reserved_quantity - order.remaining_qty)
    order.status = "CANCELLED"
    order.closed_at = get_game_now()
    if commit:
        await session.commit()
    else:
        await session.flush()
    return True
