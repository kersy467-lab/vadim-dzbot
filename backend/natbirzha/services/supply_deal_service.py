"""Server-authoritative lifecycle and inventory settlement for player supply deals."""

from __future__ import annotations

from datetime import datetime, timedelta
import math
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now, nat_settings, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import (
    CANONICAL_ITEMS, NatInventory, get_item_base_price, get_item_name, get_npc_sell_price,
)
from backend.natbirzha.models.market import NatMarketOrder, NatMarketTrade
from backend.natbirzha.models.player_deals import NatSupplyDeal, NatSupplyDealSettlement
from backend.natbirzha.services.business_income_ledger_service import BusinessIncomeLedgerService
from backend.natbirzha.services.business_rates import resource_business_rates
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.market_procurement_service import MarketProcurementService
from backend.natbirzha.services.production_service import ProductionTickEngine


class SupplyDealService:
    ALLOWED_TERMS = frozenset({600, 1800, 3600, 7200, 21600, 43200, 86400})
    MAX_DISCOUNT_PCT = 50.0
    MAX_PROFIT_SHARE_PCT = 50.0
    MAX_QUANTITY_PER_HOUR = 1_000_000.0
    STATUSES = frozenset({"PENDING", "ACTIVE", "COMPLETED", "REJECTED", "CANCELLED", "BREACHED"})

    @staticmethod
    async def current_reference_price(session: AsyncSession, item_id: str, *, exclude_company_id: int) -> float:
        if item_id not in CANONICAL_ITEMS:
            raise ValueError("Неизвестный ресурс")
        ask = await MarketProcurementService.best_ask_price(
            session, item_id, exclude_company_id=exclude_company_id
        )
        if ask is not None and math.isfinite(float(ask)) and float(ask) > 0:
            return round(float(ask), 6)
        last_trade = await session.scalar(
            select(NatMarketTrade.price)
            .where(NatMarketTrade.item_id == item_id)
            .order_by(NatMarketTrade.executed_at.desc(), NatMarketTrade.id.desc())
            .limit(1)
        )
        if last_trade is not None and math.isfinite(float(last_trade)) and float(last_trade) > 0:
            return round(float(last_trade), 6)
        fallback = float(get_npc_sell_price(item_id) or get_item_base_price(item_id))
        return round(fallback, 6) if math.isfinite(fallback) and fallback > 0 else 1.0

    @classmethod
    async def produced_resources(cls, session: AsyncSession, company_id: int) -> list[dict[str, Any]]:
        """Read real outputs of this company's live V2 businesses and legacy factories."""
        output_rates: dict[str, float] = {}
        producer_names: dict[str, set[str]] = {}
        businesses = (await session.execute(
            select(NatBusiness).where(
                NatBusiness.company_id == company_id,
                NatBusiness.status.notin_(("PAUSED_MANUAL", "BANKRUPT", "MERGING")),
            ).order_by(NatBusiness.id)
        )).scalars().all()
        for business in businesses:
            spec = get_business_spec(business.business_type)
            if not spec or spec.get("mechanic") != "resource_production" or spec.get("legacy_hidden"):
                continue
            for item_id, base_rate in spec.get("outputs_per_hour", {}).items():
                if item_id not in CANONICAL_ITEMS:
                    continue
                rate = max(0.0, float(base_rate)) * max(1, int(business.stage or 1))
                output_rates[item_id] = output_rates.get(item_id, 0.0) + rate
                producer_names.setdefault(item_id, set()).add(
                    business.custom_name or spec.get("name", business.business_type)
                )

        factories = (await session.execute(
            select(NatFactory).where(
                NatFactory.company_id == company_id,
                NatFactory.is_active.is_(True),
            ).order_by(NatFactory.id)
        )).scalars().all()
        for factory in factories:
            recipe = ProductionTickEngine.recipe_for(factory, factory.current_recipe)
            if not recipe:
                continue
            multiplier = ProductionTickEngine.output_multiplier(factory)
            for item_id, base_rate in recipe.get("outputs", {}).items():
                if item_id not in CANONICAL_ITEMS:
                    continue
                rate = max(0.0, float(base_rate)) * multiplier
                output_rates[item_id] = output_rates.get(item_id, 0.0) + rate
                producer_names.setdefault(item_id, set()).add(
                    recipe.get("name") or factory.building_type
                )

        return [
            {
                "item_id": item_id,
                "name": get_item_name(item_id),
                "unit": CANONICAL_ITEMS[item_id]["unit"],
                "outputs_per_hour": round(output_rates[item_id], 3),
                "producers": sorted(producer_names[item_id]),
            }
            for item_id in sorted(output_rates, key=lambda key: (get_item_name(key).casefold(), key))
            if output_rates[item_id] > 0
        ]

    @classmethod
    async def available_companies(
        cls, session: AsyncSession, current_company_id: int, *, current_user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        conditions = [NatCompany.id != current_company_id, NatCompany.is_bankrupt.is_(False)]
        if current_user_id is not None:
            conditions.append(NatCompany.user_id != current_user_id)
        rows = (await session.execute(
            select(NatCompany, User)
            .join(User, User.id == NatCompany.user_id)
            .where(*conditions)
            .order_by(NatCompany.name, NatCompany.id)
        )).all()
        result = []
        for company, user in rows:
            resources = await cls.produced_resources(session, company.id)
            result.append({
                "company_id": company.id,
                "company_name": company.name,
                "player_name": user.display_name,
                "specialization": company.specialization,
                "level": int(company.level or 1),
                "resources": resources,
            })
        return result

    @classmethod
    async def create_offer(
        cls,
        session: AsyncSession,
        buyer: NatCompany,
        *,
        supplier_company_id: int,
        item_id: str,
        quantity_per_hour: float,
        discount_pct: float,
        term_seconds: int,
        reward_type: str,
        profit_share_pct: float | None = None,
        fixed_cash: float | None = None,
        now: datetime | None = None,
    ) -> NatSupplyDeal:
        current = normalize_dt(now or get_game_now())
        item_id = str(item_id or "").strip()
        reward_type = str(reward_type or "").strip().upper()
        quantity = float(quantity_per_hour)
        discount = float(discount_pct)
        if not math.isfinite(quantity) or not math.isfinite(discount):
            raise ValueError("Числовые условия сделки должны быть конечными")
        if buyer.is_bankrupt:
            raise ValueError("Банкротная компания не может предлагать сделки")
        if buyer.id == int(supplier_company_id):
            raise ValueError("Нельзя заключить сделку со своей компанией")
        if item_id not in CANONICAL_ITEMS:
            raise ValueError("Неизвестный ресурс")
        if not 0 < quantity <= cls.MAX_QUANTITY_PER_HOUR:
            raise ValueError("Лимит поставки должен быть больше нуля")
        if not 0 <= discount <= cls.MAX_DISCOUNT_PCT:
            raise ValueError(f"Скидка должна быть от 0 до {cls.MAX_DISCOUNT_PCT:.0f}%")
        if int(term_seconds) not in cls.ALLOWED_TERMS:
            raise ValueError("Недопустимый срок сделки")
        if reward_type == "PROFIT_SHARE":
            pct = float(profit_share_pct or 0)
            if not math.isfinite(pct) or not 0 < pct <= cls.MAX_PROFIT_SHARE_PCT:
                raise ValueError(f"Доля прибыли должна быть больше 0 и не выше {cls.MAX_PROFIT_SHARE_PCT:.0f}%")
            if fixed_cash not in (None, 0):
                raise ValueError("Укажите только один тип вознаграждения")
            profit_share_pct, fixed_cash = pct, None
        elif reward_type == "FIXED_CASH":
            amount = float(fixed_cash or 0)
            if not math.isfinite(amount) or amount <= 0 or amount > 1_000_000_000_000:
                raise ValueError("Фиксированная выплата должна быть больше нуля")
            if profit_share_pct not in (None, 0):
                raise ValueError("Укажите только один тип вознаграждения")
            fixed_cash, profit_share_pct = round(amount, 2), None
        else:
            raise ValueError("Неизвестный тип вознаграждения")

        companies = (await session.execute(
            select(NatCompany).where(NatCompany.id.in_([buyer.id, int(supplier_company_id)]))
            .order_by(NatCompany.id).with_for_update()
        )).scalars().all()
        by_id = {company.id: company for company in companies}
        supplier = by_id.get(int(supplier_company_id))
        if supplier is None or supplier.is_bankrupt:
            raise ValueError("Компания-поставщик недоступна")
        if supplier.user_id == buyer.user_id:
            raise ValueError("Нельзя заключить сделку со своей компанией")
        resources = await cls.produced_resources(session, supplier.id)
        if item_id not in {row["item_id"] for row in resources}:
            raise ValueError("Эта компания не производит выбранный ресурс")
        reference_price = await cls.current_reference_price(
            session, item_id, exclude_company_id=buyer.id
        )
        deal = NatSupplyDeal(
            buyer_company_id=buyer.id,
            supplier_company_id=supplier.id,
            item_id=item_id,
            quantity_per_hour=round(quantity, 6),
            discount_pct=round(discount, 4),
            reward_type=reward_type,
            profit_share_pct=round(float(profit_share_pct), 4) if profit_share_pct is not None else None,
            fixed_cash=round(float(fixed_cash), 2) if fixed_cash is not None else None,
            term_seconds=int(term_seconds),
            quoted_reference_price=reference_price,
            status="PENDING",
            created_at=current,
        )
        session.add(deal)
        await session.flush()
        return deal

    @classmethod
    async def accept(cls, session: AsyncSession, company: NatCompany, deal_id: int, *, now: datetime | None = None) -> NatSupplyDeal:
        current = normalize_dt(now or get_game_now())
        preview = await session.scalar(select(NatSupplyDeal).where(
            NatSupplyDeal.id == int(deal_id)
        ))
        if preview is None or preview.supplier_company_id != company.id:
            raise ValueError("Предложение не найдено")
        await session.execute(
            select(NatCompany.id).where(NatCompany.id.in_([
                preview.buyer_company_id, preview.supplier_company_id,
            ])).order_by(NatCompany.id).with_for_update()
        )
        deal = await session.scalar(select(NatSupplyDeal).where(
            NatSupplyDeal.id == int(deal_id)
        ).with_for_update())
        if deal is None or deal.supplier_company_id != company.id:
            raise ValueError("Предложение не найдено")
        if deal.status != "PENDING":
            raise ValueError("Предложение уже обработано")
        participants = (await session.execute(
            select(NatCompany).where(NatCompany.id.in_([
                deal.buyer_company_id, deal.supplier_company_id,
            ])).order_by(NatCompany.id).with_for_update()
        )).scalars().all()
        companies = {row.id: row for row in participants}
        buyer = companies.get(deal.buyer_company_id)
        supplier = companies.get(deal.supplier_company_id)
        if not buyer or not supplier or buyer.is_bankrupt or supplier.is_bankrupt:
            deal.status = "BREACHED"
            deal.finished_at = current
            raise ValueError("Одна из компаний недоступна")
        if deal.item_id not in {
            row["item_id"] for row in await cls.produced_resources(session, supplier.id)
        }:
            raise ValueError("Поставщик больше не производит выбранный ресурс")

        expires = current + timedelta(seconds=int(deal.term_seconds))
        if deal.reward_type == "PROFIT_SHARE":
            overlapping = (await session.execute(
                select(NatSupplyDeal.profit_share_pct).where(
                    NatSupplyDeal.buyer_company_id == buyer.id,
                    NatSupplyDeal.id != deal.id,
                    NatSupplyDeal.status == "ACTIVE",
                    NatSupplyDeal.starts_at < expires,
                    NatSupplyDeal.expires_at > current,
                    NatSupplyDeal.reward_type == "PROFIT_SHARE",
                ).with_for_update()
            )).scalars().all()
            committed_pct = sum(max(0.0, float(value or 0)) for value in overlapping)
            if committed_pct + float(deal.profit_share_pct or 0) > cls.MAX_PROFIT_SHARE_PCT + 1e-9:
                raise ValueError("Суммарная доля прибыли по активным сделкам не может превышать 50%")
        if deal.reward_type == "FIXED_CASH":
            amount = round(float(deal.fixed_cash or 0), 2)
            if float(buyer.cash) + 1e-9 < amount:
                raise ValueError("У покупателя недостаточно cash для фиксированной выплаты")
            buyer.cash = round(float(buyer.cash) - amount, 2)
            withheld = await DividendService.accrue_cash_inflow(session, supplier, amount, now=current)
            supplier.cash = round(float(supplier.cash) + amount - withheld, 2)
            deal.fixed_cash_paid = amount
            session.add(NatSupplyDealSettlement(
                deal_id=deal.id,
                idempotency_key=f"fixed:{deal.id}",
                settlement_type="FIXED_CASH",
                cash_amount=amount,
                created_at=current,
            ))
            await cls._record_daily_financials(session, buyer.id, supplier.id, amount, current)
        deal.status = "ACTIVE"
        deal.accepted_at = current
        deal.starts_at = current
        deal.expires_at = expires
        deal.settlement_cursor = current
        await session.flush()
        return deal

    @classmethod
    async def reject(cls, session: AsyncSession, company: NatCompany, deal_id: int, *, now: datetime | None = None) -> NatSupplyDeal:
        await session.scalar(select(NatCompany).where(NatCompany.id == company.id).with_for_update())
        deal = await cls._lock_participant_deal(session, company.id, deal_id, role="supplier")
        if deal.status != "PENDING":
            raise ValueError("Предложение уже обработано")
        deal.status = "REJECTED"
        deal.finished_at = normalize_dt(now or get_game_now())
        await session.flush()
        return deal

    @classmethod
    async def cancel(cls, session: AsyncSession, company: NatCompany, deal_id: int, *, now: datetime | None = None) -> NatSupplyDeal:
        await session.scalar(select(NatCompany).where(NatCompany.id == company.id).with_for_update())
        deal = await cls._lock_participant_deal(session, company.id, deal_id, role="buyer")
        if deal.status != "PENDING":
            raise ValueError("Отменить можно только ожидающее предложение")
        deal.status = "CANCELLED"
        deal.finished_at = normalize_dt(now or get_game_now())
        await session.flush()
        return deal

    @staticmethod
    async def _lock_participant_deal(session: AsyncSession, company_id: int, deal_id: int, *, role: str) -> NatSupplyDeal:
        deal = await session.scalar(select(NatSupplyDeal).where(
            NatSupplyDeal.id == int(deal_id)
        ).with_for_update())
        expected = deal.buyer_company_id if deal and role == "buyer" else deal.supplier_company_id if deal else None
        if deal is None or expected != company_id:
            raise ValueError("Сделка не найдена")
        return deal

    @classmethod
    async def settle_expired(cls, session: AsyncSession, company_id: int, *, now: datetime | None = None) -> int:
        current = normalize_dt(now or get_game_now())
        rows = (await session.execute(
            select(NatSupplyDeal).where(
                ((NatSupplyDeal.buyer_company_id == company_id) | (NatSupplyDeal.supplier_company_id == company_id))
                & (NatSupplyDeal.settlement_cursor >= NatSupplyDeal.expires_at),
                NatSupplyDeal.status == "ACTIVE",
                NatSupplyDeal.expires_at <= current,
            ).with_for_update()
        )).scalars().all()
        for row in rows:
            row.status = "COMPLETED"
            row.finished_at = normalize_dt(row.expires_at) or current
        if rows:
            await session.flush()
        return len(rows)

    @classmethod
    async def advance_buyer_cursor(cls, session: AsyncSession, buyer_company_id: int, *, through: datetime) -> None:
        rows = (await session.execute(select(NatSupplyDeal).where(
            NatSupplyDeal.buyer_company_id == buyer_company_id,
            NatSupplyDeal.status == "ACTIVE",
            NatSupplyDeal.starts_at < through,
        ).with_for_update())).scalars().all()
        for row in rows:
            previous = normalize_dt(row.settlement_cursor) if row.settlement_cursor else None
            row.settlement_cursor = max(previous or through, through)
        if rows:
            await session.flush()

    @classmethod
    async def list_deals(cls, session: AsyncSession, company_id: int, view: str, *, now: datetime | None = None) -> list[dict[str, Any]]:
        await cls.settle_expired(session, company_id, now=now)
        common = (NatSupplyDeal.buyer_company_id == company_id) | (NatSupplyDeal.supplier_company_id == company_id)
        if view == "incoming":
            condition = (NatSupplyDeal.supplier_company_id == company_id) & (NatSupplyDeal.status == "PENDING")
        elif view == "outgoing":
            condition = (NatSupplyDeal.buyer_company_id == company_id) & (NatSupplyDeal.status == "PENDING")
        elif view == "active":
            condition = common & (NatSupplyDeal.status == "ACTIVE")
        elif view == "history":
            condition = common & NatSupplyDeal.status.in_(("COMPLETED", "REJECTED", "CANCELLED", "BREACHED"))
        else:
            raise ValueError("Неизвестный раздел сделок")
        deals = (await session.execute(
            select(NatSupplyDeal).where(condition).order_by(NatSupplyDeal.created_at.desc(), NatSupplyDeal.id.desc())
        )).scalars().all()
        return [await cls.serialize(session, deal, company_id, now=now) for deal in deals]

    @classmethod
    async def get_deal(cls, session: AsyncSession, company_id: int, deal_id: int, *, now: datetime | None = None) -> dict[str, Any]:
        deal = await session.scalar(select(NatSupplyDeal).where(
            NatSupplyDeal.id == int(deal_id),
            (NatSupplyDeal.buyer_company_id == company_id) | (NatSupplyDeal.supplier_company_id == company_id),
        ))
        if deal is None:
            raise ValueError("Сделка не найдена")
        return await cls.serialize(session, deal, company_id, now=now)

    @classmethod
    async def serialize(cls, session: AsyncSession, deal: NatSupplyDeal, viewer_company_id: int, *, now: datetime | None = None) -> dict[str, Any]:
        current = normalize_dt(now or get_game_now())
        companies = (await session.execute(select(NatCompany).where(
            NatCompany.id.in_([deal.buyer_company_id, deal.supplier_company_id])
        ))).scalars().all()
        names = {row.id: row.name for row in companies}
        reference = await cls.current_reference_price(session, deal.item_id, exclude_company_id=deal.buyer_company_id)
        unit_price = round(max(0.000001, reference * (1 - float(deal.discount_pct) / 100)), 6)
        remaining = max(0, int((normalize_dt(deal.expires_at) - current).total_seconds())) if deal.expires_at and deal.status == "ACTIVE" else 0
        settlements = (await session.execute(
            select(NatSupplyDealSettlement).where(NatSupplyDealSettlement.deal_id == deal.id)
            .order_by(NatSupplyDealSettlement.id.desc()).limit(50)
        )).scalars().all()
        return {
            "id": deal.id,
            "buyer_company_id": deal.buyer_company_id,
            "buyer_company_name": names.get(deal.buyer_company_id, "Компания"),
            "supplier_company_id": deal.supplier_company_id,
            "supplier_company_name": names.get(deal.supplier_company_id, "Компания"),
            "viewer_role": "buyer" if viewer_company_id == deal.buyer_company_id else "supplier",
            "item_id": deal.item_id,
            "item_name": get_item_name(deal.item_id),
            "unit": CANONICAL_ITEMS[deal.item_id]["unit"],
            "quantity_per_hour": float(deal.quantity_per_hour),
            "discount_pct": float(deal.discount_pct),
            "reference_price": reference,
            "unit_price": unit_price,
            "reward_type": deal.reward_type,
            "profit_share_pct": deal.profit_share_pct,
            "fixed_cash": deal.fixed_cash,
            "term_seconds": deal.term_seconds,
            "status": deal.status,
            "created_at": deal.created_at.isoformat() if deal.created_at else None,
            "accepted_at": deal.accepted_at.isoformat() if deal.accepted_at else None,
            "starts_at": deal.starts_at.isoformat() if deal.starts_at else None,
            "expires_at": deal.expires_at.isoformat() if deal.expires_at else None,
            "finished_at": deal.finished_at.isoformat() if deal.finished_at else None,
            "remaining_seconds": remaining,
            "delivered_quantity": float(deal.delivered_quantity or 0),
            "resource_cash_paid": float(deal.resource_cash_paid or 0),
            "profit_share_paid": float(deal.profit_share_paid or 0),
            "fixed_cash_paid": float(deal.fixed_cash_paid or 0),
            "savings_cash": round(sum(
                max(0.0, float(row.market_reference_price or 0) - float(row.unit_price or 0))
                * float(row.quantity or 0)
                for row in settlements if row.settlement_type == "DELIVERY"
            ), 6),
            "settlements": [{
                "type": row.settlement_type,
                "item_id": row.item_id,
                "quantity": row.quantity,
                "unit_price": row.unit_price,
                "market_reference_price": row.market_reference_price,
                "cash_amount": row.cash_amount,
                "profit_base_cash": row.profit_base_cash,
                "period_start": row.period_start.isoformat() if row.period_start else None,
                "period_end": row.period_end.isoformat() if row.period_end else None,
                "created_at": row.created_at.isoformat(),
            } for row in reversed(settlements)],
        }

    @classmethod
    async def partners_to_settle(cls, session: AsyncSession, buyer_company_id: int, *, now: datetime) -> list[int]:
        deals = (await session.execute(
            select(NatSupplyDeal.supplier_company_id).where(
                NatSupplyDeal.buyer_company_id == buyer_company_id,
                NatSupplyDeal.status == "ACTIVE",
                NatSupplyDeal.starts_at < now,
                NatSupplyDeal.expires_at > now - timedelta(days=7),
            ).order_by(NatSupplyDeal.supplier_company_id)
        )).scalars().all()
        return sorted({int(company_id) for company_id in deals if company_id != buyer_company_id})

    @classmethod
    async def buyers_to_settle(cls, session: AsyncSession, supplier_company_id: int) -> list[int]:
        """Return buyers whose lazy contract settlement should run for supplier views."""
        rows = (await session.execute(
            select(NatSupplyDeal.buyer_company_id).where(
                NatSupplyDeal.supplier_company_id == supplier_company_id,
                NatSupplyDeal.status == "ACTIVE",
            ).distinct().order_by(NatSupplyDeal.buyer_company_id)
        )).scalars().all()
        return [int(company_id) for company_id in rows if int(company_id) != supplier_company_id]

    @classmethod
    async def active_for_buyer(cls, session: AsyncSession, buyer_company_id: int, *, start: datetime, end: datetime) -> list[NatSupplyDeal]:
        return list((await session.execute(
            select(NatSupplyDeal).where(
                NatSupplyDeal.buyer_company_id == buyer_company_id,
                NatSupplyDeal.status == "ACTIVE",
                NatSupplyDeal.starts_at < end,
                NatSupplyDeal.expires_at > start,
            ).order_by(NatSupplyDeal.id).with_for_update()
        )).scalars().all())

    @classmethod
    async def settle_profit_share(
        cls,
        session: AsyncSession,
        buyer: NatCompany,
        profit_slices: list[dict[str, Any]],
        *,
        cash_available: float,
        now: datetime,
    ) -> float:
        """Pay each accepted share once, only against positive net operating profit."""
        if not profit_slices or cash_available <= 1e-9:
            return 0.0
        first = min(row["start"] for row in profit_slices)
        last = max(row["end"] for row in profit_slices)
        deals = (await session.execute(select(NatSupplyDeal).where(
            NatSupplyDeal.buyer_company_id == buyer.id,
            NatSupplyDeal.status == "ACTIVE",
            NatSupplyDeal.reward_type == "PROFIT_SHARE",
            NatSupplyDeal.starts_at < last,
            NatSupplyDeal.expires_at > first,
        ).order_by(NatSupplyDeal.id).with_for_update())).scalars().all()
        if not deals:
            return 0.0
        suppliers = {row.id: row for row in (await session.execute(select(NatCompany).where(
            NatCompany.id.in_([deal.supplier_company_id for deal in deals])
        ).order_by(NatCompany.id).with_for_update())).scalars().all()}
        payout_total = 0.0
        remaining_cash = max(0.0, float(cash_available))
        for deal in deals:
            deal_start, deal_end = normalize_dt(deal.starts_at), normalize_dt(deal.expires_at)
            breakpoints = {max(first, deal_start), min(last, deal_end)}
            for profit_slice in profit_slices:
                if profit_slice["end"] > deal_start and profit_slice["start"] < deal_end:
                    breakpoints.add(max(profit_slice["start"], deal_start))
                    breakpoints.add(min(profit_slice["end"], deal_end))
            points = sorted(point for point in breakpoints if first <= point <= last)
            for start, end in zip(points, points[1:]):
                if end <= start or start < deal_start or end > deal_end:
                    continue
                duration = (end - start).total_seconds()
                operating_profit = 0.0
                contributing = []
                for profit_slice in profit_slices:
                    overlap = max(0.0, (min(end, profit_slice["end"]) - max(start, profit_slice["start"])).total_seconds())
                    total = max(1e-9, (profit_slice["end"] - profit_slice["start"]).total_seconds())
                    if overlap <= 0:
                        continue
                    part = float(profit_slice["net_profit"]) * overlap / total
                    operating_profit += part
                    if part > 0:
                        contributing.append((profit_slice, part))
                if operating_profit <= 1e-9:
                    continue
                key = f"profit:{deal.id}:{start.isoformat()}:{end.isoformat()}"
                exists = await session.scalar(select(NatSupplyDealSettlement.id).where(
                    NatSupplyDealSettlement.deal_id == deal.id,
                    NatSupplyDealSettlement.idempotency_key == key,
                ))
                if exists:
                    continue
                requested = round(operating_profit * float(deal.profit_share_pct or 0) / 100, 6)
                payout = round(min(requested, remaining_cash), 6)
                if payout <= 1e-9:
                    continue
                supplier = suppliers.get(deal.supplier_company_id)
                if supplier is None or supplier.is_bankrupt:
                    continue
                withheld = await DividendService.accrue_cash_inflow(session, supplier, payout, now=normalize_dt(now))
                supplier.cash = round(float(supplier.cash) + payout - withheld, 6)
                deal.profit_share_paid = round(float(deal.profit_share_paid or 0) + payout, 6)
                await cls._record_daily_financials(session, buyer.id, supplier.id, payout, normalize_dt(now))
                supplier_business = await session.scalar(select(NatBusiness).where(
                    NatBusiness.company_id == supplier.id,
                    NatBusiness.status.notin_(("PAUSED_MANUAL", "BANKRUPT", "MERGING")),
                ).order_by(NatBusiness.id).limit(1))
                if supplier_business is not None:
                    await BusinessIncomeLedgerService.record(
                        session, supplier_business.id, normalize_dt(now).date(),
                        gross=payout, maintenance=0.0, resource_cost=0.0,
                    )
                session.add(NatSupplyDealSettlement(
                    deal_id=deal.id,
                    idempotency_key=key,
                    settlement_type="PROFIT_SHARE",
                    period_start=start,
                    period_end=end,
                    cash_amount=payout,
                    profit_base_cash=round(operating_profit, 6),
                    created_at=normalize_dt(now),
                ))
                remaining_cash = round(remaining_cash - payout, 6)
                payout_total = round(payout_total + payout, 6)

                # Book the contract share as an operating expense against the
                # same positive production that generated it, preserving tax/NAV.
                base = sum(amount for _, amount in contributing)
                left = payout
                for index, (source, amount) in enumerate(contributing):
                    part = left if index == len(contributing) - 1 else round(payout * amount / base, 6)
                    left = round(left - part, 6)
                    if part <= 1e-9:
                        continue
                    hours = (source["end"] - source["start"]).total_seconds() / 3600
                    await BusinessIncomeLedgerService.record_interval(
                        session, source["business_id"], start, min(hours, duration / 3600),
                        gross=0.0, maintenance=part,
                    )
        return payout_total

    @classmethod
    async def fulfill_resource_interval(
        cls,
        session: AsyncSession,
        buyer: NatCompany,
        business: NatBusiness,
        spec: dict[str, Any],
        *,
        start: datetime,
        end: datetime,
        now: datetime,
    ) -> list[dict[str, Any]]:
        """Transfer only current input need, with seller inventory and hourly quota enforced."""
        seconds = max(0.0, (end - start).total_seconds())
        if seconds <= 1e-6:
            return []
        deals = (await session.execute(
            select(NatSupplyDeal).where(
                NatSupplyDeal.buyer_company_id == buyer.id,
                NatSupplyDeal.status == "ACTIVE",
                NatSupplyDeal.starts_at < end,
                NatSupplyDeal.expires_at > start,
            ).order_by(NatSupplyDeal.id).with_for_update()
        )).scalars().all()
        if not deals:
            return []
        rates = resource_business_rates(business, spec, upgrading=business.status == "UPGRADING")
        inputs = {key: float(value) * rates.input_multiplier for key, value in spec.get("inputs_per_hour", {}).items()}
        transfers: list[dict[str, Any]] = []
        for deal in deals:
            if deal.item_id not in inputs:
                continue
            active_start = max(start, normalize_dt(deal.starts_at))
            active_end = min(end, normalize_dt(deal.expires_at))
            overlap_seconds = max(0.0, (active_end - active_start).total_seconds())
            if overlap_seconds <= 1e-6:
                continue
            inventory = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == buyer.id, NatInventory.item_id == deal.item_id
            ).with_for_update())
            demand = inputs[deal.item_id] * (overlap_seconds / 3600)
            available = float(inventory.available_quantity) if inventory else 0.0
            needed = max(0.0, demand - available)
            if needed <= 1e-9:
                continue

            used = await cls._delivered_during(session, deal.id, active_start, active_end)
            quota = max(0.0, float(deal.quantity_per_hour) * overlap_seconds / 3600 - used)
            if quota <= 1e-9:
                continue
            supplier_inventory = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == deal.supplier_company_id,
                NatInventory.item_id == deal.item_id,
            ).with_for_update())
            supplier_available = float(supplier_inventory.available_quantity) if supplier_inventory else 0.0
            reference = await cls.current_reference_price(session, deal.item_id, exclude_company_id=buyer.id)
            unit_price = round(max(0.000001, reference * (1 - float(deal.discount_pct) / 100)), 6)
            buyer_quantity = float(inventory.quantity) if inventory else 0.0
            storage_free = max(0.0, float(nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM) - buyer_quantity)
            cash_affordable = max(0.0, float(buyer.cash)) / unit_price
            quantity = round(min(needed, quota, supplier_available, storage_free, cash_affordable), 6)
            if quantity <= 1e-9:
                continue
            amount = round(quantity * unit_price, 6)
            if amount <= 0 or float(buyer.cash) + 1e-9 < amount:
                continue
            if inventory is None:
                inventory = NatInventory(
                    company_id=buyer.id,
                    item_id=deal.item_id,
                    quantity=quantity,
                    reserved_quantity=0.0,
                    avg_cost_basis=unit_price,
                )
                session.add(inventory)
            else:
                old_quantity = float(inventory.quantity)
                new_quantity = old_quantity + quantity
                inventory.avg_cost_basis = round(
                    ((old_quantity * float(inventory.avg_cost_basis or 0)) + amount) / max(new_quantity, 1e-9), 6
                )
                inventory.quantity = round(new_quantity, 6)
            supplier_inventory.quantity = round(max(0.0, float(supplier_inventory.quantity) - quantity), 6)
            buyer.cash = round(float(buyer.cash) - amount, 6)
            supplier = await session.get(NatCompany, deal.supplier_company_id)
            if supplier is None or supplier.is_bankrupt:
                raise ValueError("Поставщик недоступен")
            dividend_withheld = await DividendService.accrue_cash_inflow(session, supplier, amount, now=normalize_dt(now))
            supplier.cash = round(float(supplier.cash) + amount - dividend_withheld, 6)
            deal.delivered_quantity = round(float(deal.delivered_quantity or 0) + quantity, 6)
            deal.resource_cash_paid = round(float(deal.resource_cash_paid or 0) + amount, 6)
            deal.settlement_cursor = max(normalize_dt(deal.settlement_cursor) if deal.settlement_cursor else active_end, active_end)
            settlement_key = f"delivery:{business.id}:{active_start.isoformat()}:{active_end.isoformat()}"
            session.add(NatSupplyDealSettlement(
                deal_id=deal.id,
                idempotency_key=settlement_key,
                settlement_type="DELIVERY",
                business_id=business.id,
                period_start=active_start,
                period_end=active_end,
                item_id=deal.item_id,
                quantity=quantity,
                unit_price=unit_price,
                market_reference_price=reference,
                cash_amount=amount,
                created_at=normalize_dt(now),
            ))
            await cls._record_daily_financials(session, buyer.id, supplier.id, amount, normalize_dt(now))
            producer_rows = (await session.execute(select(NatBusiness).where(
                NatBusiness.company_id == supplier.id,
                NatBusiness.status.notin_(("PAUSED_MANUAL", "BANKRUPT", "MERGING")),
            ).order_by(NatBusiness.id))).scalars().all()
            producer = next((row for row in producer_rows
                if deal.item_id in (get_business_spec(row.business_type) or {}).get("outputs_per_hour", {})), None)
            if producer is not None:
                await BusinessIncomeLedgerService.record(
                    session, producer.id, normalize_dt(now).date(),
                    gross=amount, maintenance=0.0, resource_cost=0.0,
                )
            transfers.append({
                "deal_id": deal.id, "item_id": deal.item_id, "quantity": quantity,
                "unit_price": unit_price, "cash_amount": amount,
            })
            needed = max(0.0, needed - quantity)
        if transfers:
            await session.flush()
        return transfers

    @staticmethod
    async def _delivered_during(session: AsyncSession, deal_id: int, start: datetime, end: datetime) -> float:
        rows = (await session.execute(select(NatSupplyDealSettlement).where(
            NatSupplyDealSettlement.deal_id == deal_id,
            NatSupplyDealSettlement.settlement_type == "DELIVERY",
            NatSupplyDealSettlement.period_start < end,
            NatSupplyDealSettlement.period_end > start,
        ))).scalars().all()
        total = 0.0
        for row in rows:
            row_start, row_end = normalize_dt(row.period_start), normalize_dt(row.period_end)
            duration = max(1.0, (row_end - row_start).total_seconds())
            overlap = max(0.0, (min(end, row_end) - max(start, row_start)).total_seconds())
            total += float(row.quantity) * overlap / duration
        return round(total, 6)

    @staticmethod
    async def _record_daily_financials(session: AsyncSession, buyer_id: int, supplier_id: int, amount: float, now: datetime) -> None:
        from backend.natbirzha.models.restructuring import NatDailyFinancials

        for company_id, revenue, opex in ((buyer_id, 0.0, amount), (supplier_id, amount, 0.0)):
            row = await session.scalar(select(NatDailyFinancials).where(
                NatDailyFinancials.company_id == company_id,
                NatDailyFinancials.calendar_date == now.date(),
            ).with_for_update())
            if row is None:
                row = NatDailyFinancials(
                    company_id=company_id, calendar_date=now.date(),
                    gross_revenue=revenue, opex=opex,
                    closed_profit=round(revenue - opex, 2), developer_fee_paid=0.0,
                )
                session.add(row)
            else:
                row.gross_revenue = round(float(row.gross_revenue or 0) + revenue, 2)
                row.opex = round(float(row.opex or 0) + opex, 2)
                row.closed_profit = round(row.gross_revenue - row.opex, 2)

    @classmethod
    async def bankruptcy_terminate(cls, session: AsyncSession, company_id: int, *, now: datetime | None = None) -> int:
        current = normalize_dt(now or get_game_now())
        rows = (await session.execute(select(NatSupplyDeal).where(
            (NatSupplyDeal.buyer_company_id == company_id) | (NatSupplyDeal.supplier_company_id == company_id),
            NatSupplyDeal.status.in_(("PENDING", "ACTIVE")),
        ).with_for_update())).scalars().all()
        for deal in rows:
            deal.status = "CANCELLED" if deal.status == "PENDING" else "BREACHED"
            deal.finished_at = current
        await session.flush()
        return len(rows)


__all__ = ["SupplyDealService"]
