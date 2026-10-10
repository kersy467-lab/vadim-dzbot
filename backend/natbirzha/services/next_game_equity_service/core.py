"""IPO creation and protected price-time share matching for the 2.0 market."""

from datetime import datetime, timezone
from math import isfinite
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameFacility
from backend.natbirzha.models.next_game_equity import (
    NatNextGameShareHolding, NatNextGameShareIssue, NatNextGameShareOrder,
    NatNextGameShareTrade,
)
from backend.natbirzha.services.next_game_market_service import NextGameMarketService
from backend.natbirzha.services.next_game_service import NextGameService

TOTAL_SHARES = 100_000
IPO_FLOAT_SHARES = 10_000
MIN_IPO_COMPANY_LEVEL = 5
MAX_ORDER_SHARES = 1_000_000
MAX_SHARE_PRICE = 1_000_000_000.0
MAX_PRICE_CHANGE = 0.15


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _cash(value: float) -> float:
    return round(float(value), 8)


class NextGameEquityCoreMixin:
    @classmethod
    async def open_ipo(
        cls, session: AsyncSession, owner_tg_id: int, *, now: datetime | None = None,
    ) -> dict[str, Any]:
        await NextGameMarketService.lock_orderbook(session)
        company = await NextGameService._owned_company(session, owner_tg_id)
        if int(company.level) < MIN_IPO_COMPANY_LEVEL:
            raise ValueError(f"Для IPO нужен уровень компании {MIN_IPO_COMPANY_LEVEL}")
        facility_count = await session.scalar(
            select(func.count(NatNextGameFacility.id)).where(
                NatNextGameFacility.company_id == company.id,
            )
        )
        if not facility_count:
            raise ValueError("Для IPO сначала построй хотя бы один завод")
        existing = await session.scalar(
            select(NatNextGameShareIssue).where(
                NatNextGameShareIssue.company_id == company.id,
            )
        )
        if existing:
            raise ValueError("У компании уже открыто IPO")

        price = max(0.01, round(float(company.cash) / IPO_FLOAT_SHARES, 4))
        issue = NatNextGameShareIssue(
            company_id=company.id,
            total_shares=TOTAL_SHARES,
            float_shares=IPO_FLOAT_SHARES,
            initial_price=price,
            last_price=price,
            status="ACTIVE",
            listed_at=now or _utcnow(),
        )
        session.add(issue)
        await session.flush()
        session.add(NatNextGameShareHolding(
            issue_id=issue.id, company_id=company.id,
            shares=TOTAL_SHARES, average_price=price,
        ))
        session.add(NatNextGameShareOrder(
            issue_id=issue.id, company_id=company.id, side="SELL",
            limit_price=price, quantity=IPO_FLOAT_SHARES,
            remaining_shares=IPO_FLOAT_SHARES, reserved_cash=0.0,
            status="OPEN", created_at=issue.listed_at, updated_at=issue.listed_at,
        ))
        await session.flush()
        return {"success": True, "issue": cls.issue_payload(issue, company.name)}

    @classmethod
    async def create_order(
        cls, session: AsyncSession, owner_tg_id: int, issue_id: int, side: str,
        shares: int, limit_price: float, *, now: datetime | None = None,
    ) -> dict[str, Any]:
        normalized_side = str(side or "").upper()
        if normalized_side not in {"BUY", "SELL"}:
            raise ValueError("Выберите покупку или продажу акций")
        try:
            amount_value = float(shares)
            price = float(limit_price)
            normalized_issue_id = int(issue_id)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Количество акций и лимитная цена должны быть числами") from exc
        if normalized_issue_id <= 0:
            raise ValueError("IPO не найдено")
        if not isfinite(amount_value) or not amount_value.is_integer():
            raise ValueError("Количество акций должно быть целым числом")
        amount = int(amount_value)
        if amount <= 0 or amount > MAX_ORDER_SHARES:
            raise ValueError(f"Количество должно быть от 1 до {MAX_ORDER_SHARES:,} акций")
        if not isfinite(price) or price <= 0 or price > MAX_SHARE_PRICE:
            raise ValueError("Лимитная цена должна быть конечной и положительной")
        rounded_price = round(price, 4)
        if abs(price - rounded_price) > 1e-9:
            raise ValueError("Цену можно указать максимум с четырьмя знаками после запятой")
        price = rounded_price
        reserve = _cash(amount * price) if normalized_side == "BUY" else 0.0

        await NextGameMarketService.lock_orderbook(session)
        current = now or _utcnow()
        await NextGameService.settle_company(session, owner_tg_id, now=current)
        company = await NextGameService._owned_company(session, owner_tg_id)
        issue = await session.scalar(
            select(NatNextGameShareIssue).where(
                NatNextGameShareIssue.id == normalized_issue_id,
                NatNextGameShareIssue.status == "ACTIVE",
            ).with_for_update()
        )
        if issue is None:
            raise ValueError("Активное IPO не найдено")
        if normalized_side == "BUY":
            if company.id == issue.company_id:
                raise ValueError("Компания не может покупать собственные акции")
            if float(company.cash) + 1e-8 < reserve:
                raise ValueError("Недостаточно cash для резерва заявки на акции")
            company.cash = _cash(float(company.cash) - reserve)
        else:
            holding = await cls._holding(session, issue.id, company.id, lock=True)
            reserved = await cls._reserved_shares(session, issue.id, company.id)
            available = int(holding.shares if holding else 0) - reserved
            if available < amount:
                raise ValueError(f"Свободно для продажи только {max(0, available):,} акций")

        order = NatNextGameShareOrder(
            issue_id=issue.id, company_id=company.id, side=normalized_side,
            limit_price=price, quantity=amount, remaining_shares=amount,
            reserved_cash=reserve, status="OPEN", created_at=current, updated_at=current,
        )
        session.add(order)
        await session.flush()
        trades = await cls._match_order(session, order, issue, current)
        await session.flush()
        return {
            "success": True,
            "order": cls.order_payload(order, company.name),
            "executed_shares": sum(row["shares"] for row in trades),
            "remaining_shares": int(order.remaining_shares),
            "trades": trades,
            "company": NextGameService.snapshot_company(company),
        }

    @classmethod
    async def _match_order(
        cls, session: AsyncSession, incoming: NatNextGameShareOrder,
        issue: NatNextGameShareIssue, current: datetime,
    ) -> list[dict[str, Any]]:
        if incoming.side == "BUY":
            criteria = (NatNextGameShareOrder.side == "SELL",
                        NatNextGameShareOrder.limit_price <= incoming.limit_price)
            sorting = (NatNextGameShareOrder.limit_price.asc(), NatNextGameShareOrder.id.asc())
        else:
            criteria = (NatNextGameShareOrder.side == "BUY",
                        NatNextGameShareOrder.limit_price >= incoming.limit_price)
            sorting = (NatNextGameShareOrder.limit_price.desc(), NatNextGameShareOrder.id.asc())
        rows = (await session.execute(
            select(NatNextGameShareOrder, NatNextGameCompany.name).join(
                NatNextGameCompany, NatNextGameCompany.id == NatNextGameShareOrder.company_id,
            ).where(
                NatNextGameShareOrder.issue_id == issue.id,
                NatNextGameShareOrder.status == "OPEN",
                NatNextGameShareOrder.remaining_shares > 0,
                NatNextGameShareOrder.company_id != incoming.company_id,
                *criteria,
            ).order_by(*sorting).with_for_update()
        )).all()
        executed = []
        for maker, maker_name in rows:
            if incoming.remaining_shares <= 0:
                break
            trade_price = float(maker.limit_price)
            reference = float(issue.last_price or issue.initial_price)
            if not reference or abs(trade_price / reference - 1) > MAX_PRICE_CHANGE + 1e-9:
                continue
            buyer_order = incoming if incoming.side == "BUY" else maker
            seller_order = maker if incoming.side == "BUY" else incoming
            buyer = await session.get(NatNextGameCompany, buyer_order.company_id)
            seller = await session.get(NatNextGameCompany, seller_order.company_id)
            if buyer is None or seller is None or buyer.id == seller.id:
                continue
            fill = min(int(incoming.remaining_shares), int(maker.remaining_shares))
            if fill <= 0:
                continue

            trade_value = _cash(fill * trade_price)
            old_reserve = float(buyer_order.reserved_cash)
            next_buyer_shares = max(0, int(buyer_order.remaining_shares) - fill)
            next_reserve = _cash(next_buyer_shares * float(buyer_order.limit_price))
            released = max(0.0, _cash(old_reserve - next_reserve))
            buyer.cash = _cash(float(buyer.cash) + max(0.0, released - trade_value))
            seller.cash = _cash(float(seller.cash) + trade_value)
            buyer_order.remaining_shares = next_buyer_shares
            buyer_order.reserved_cash = next_reserve
            seller_order.remaining_shares = max(0, int(seller_order.remaining_shares) - fill)
            buyer_order.status = "FILLED" if next_buyer_shares == 0 else "OPEN"
            seller_order.status = "FILLED" if seller_order.remaining_shares == 0 else "OPEN"
            buyer_order.updated_at = seller_order.updated_at = current

            buyer_holding = await cls._holding(session, issue.id, buyer.id, lock=True)
            seller_holding = await cls._holding(session, issue.id, seller.id, lock=True)
            if seller_holding is None or int(seller_holding.shares) < fill:
                raise ValueError("У продавца недостаточно свободных акций для исполнения")
            if buyer_holding is None:
                buyer_holding = NatNextGameShareHolding(
                    issue_id=issue.id, company_id=buyer.id, shares=0, average_price=0.0,
                )
                session.add(buyer_holding)
                await session.flush()
            old_shares = int(buyer_holding.shares)
            buyer_holding.shares = old_shares + fill
            buyer_holding.average_price = round(
                (old_shares * float(buyer_holding.average_price) + fill * trade_price)
                / buyer_holding.shares, 4,
            )
            seller_holding.shares = int(seller_holding.shares) - fill
            if seller_holding.shares == 0:
                seller_holding.average_price = 0.0
            issue.last_price = trade_price

            trade = NatNextGameShareTrade(
                issue_id=issue.id, buy_order_id=buyer_order.id,
                sell_order_id=seller_order.id, buyer_company_id=buyer.id,
                seller_company_id=seller.id, shares=fill,
                price=trade_price, executed_at=current,
            )
            session.add(trade)
            await session.flush()
            executed.append(cls.trade_payload(trade, buyer.name, seller.name))
        return executed

    @classmethod
    async def cancel_order(
        cls, session: AsyncSession, owner_tg_id: int, order_id: int,
    ) -> dict[str, Any]:
        await NextGameMarketService.lock_orderbook(session)
        company = await NextGameService._owned_company(session, owner_tg_id)
        order = await session.scalar(
            select(NatNextGameShareOrder).where(
                NatNextGameShareOrder.id == int(order_id),
                NatNextGameShareOrder.company_id == company.id,
                NatNextGameShareOrder.status == "OPEN",
            ).with_for_update()
        )
        if order is None:
            raise ValueError("Открытая заявка на акции не найдена")
        released_cash = float(order.reserved_cash)
        if order.side == "BUY":
            company.cash = _cash(float(company.cash) + released_cash)
        order.reserved_cash = 0.0
        order.remaining_shares = 0
        order.status = "CANCELLED"
        order.updated_at = _utcnow()
        await session.flush()
        return {"success": True, "released_cash": released_cash}

    @staticmethod
    async def _holding(
        session: AsyncSession, issue_id: int, company_id: int, *, lock: bool = False,
    ) -> NatNextGameShareHolding | None:
        query = select(NatNextGameShareHolding).where(
            NatNextGameShareHolding.issue_id == issue_id,
            NatNextGameShareHolding.company_id == company_id,
        )
        if lock:
            query = query.with_for_update()
        return await session.scalar(query)

    @staticmethod
    async def _reserved_shares(session: AsyncSession, issue_id: int, company_id: int) -> int:
        amount = await session.scalar(
            select(func.coalesce(func.sum(NatNextGameShareOrder.remaining_shares), 0)).where(
                NatNextGameShareOrder.issue_id == issue_id,
                NatNextGameShareOrder.company_id == company_id,
                NatNextGameShareOrder.side == "SELL",
                NatNextGameShareOrder.status == "OPEN",
            )
        )
        return int(amount or 0)

    @staticmethod
    def issue_payload(issue: NatNextGameShareIssue, company_name: str) -> dict[str, Any]:
        return {
            "id": int(issue.id), "company_id": int(issue.company_id),
            "company_name": str(company_name), "total_shares": int(issue.total_shares),
            "float_shares": int(issue.float_shares),
            "initial_price": round(float(issue.initial_price), 4),
            "last_price": round(float(issue.last_price), 4),
            "status": str(issue.status), "listed_at": issue.listed_at.isoformat(),
        }

    @staticmethod
    def order_payload(order: NatNextGameShareOrder, company_name: str) -> dict[str, Any]:
        return {
            "id": int(order.id), "issue_id": int(order.issue_id),
            "company_id": int(order.company_id), "company_name": str(company_name),
            "side": str(order.side), "limit_price": round(float(order.limit_price), 4),
            "quantity": int(order.quantity), "remaining_shares": int(order.remaining_shares),
            "reserved_cash": round(float(order.reserved_cash), 8),
            "status": str(order.status),
            "created_at": order.created_at.isoformat() if order.created_at else None,
        }

    @staticmethod
    def trade_payload(
        trade: NatNextGameShareTrade, buyer_name: str, seller_name: str,
    ) -> dict[str, Any]:
        return {
            "id": int(trade.id), "issue_id": int(trade.issue_id),
            "buy_order_id": int(trade.buy_order_id), "sell_order_id": int(trade.sell_order_id),
            "buyer_company_id": int(trade.buyer_company_id),
            "seller_company_id": int(trade.seller_company_id),
            "buyer_company_name": str(buyer_name), "seller_company_name": str(seller_name),
            "shares": int(trade.shares), "price": round(float(trade.price), 4),
            "executed_at": trade.executed_at.isoformat() if trade.executed_at else None,
        }


__all__ = ["NextGameEquityCoreMixin"]
