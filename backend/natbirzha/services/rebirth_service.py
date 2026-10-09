"""Atomic company renewal with preserved public shares and protected obligations."""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.natbirzha.catalogs.businesses import visible_business_specs
from backend.natbirzha.config import get_game_now, normalize_dt, nat_settings
from backend.natbirzha.models import (
    NatCompany,
    NatBusiness,
    NatLoan,
    NatStateCreditLoan,
    NatMarketOrder,
    NatStock,
    NatStateShareHolding,
    NatInstrumentPosition,
    NatSupplyDeal,
    NatContract,
    NatJointFactory,
)
from backend.natbirzha.models.rebirth import NatCompanyRebirth
from backend.natbirzha.models.company_aid import NatCompanyAidRequest
from backend.natbirzha.services.player_registry_service import PlayerRegistryService

logger = logging.getLogger(__name__)
MAX_REBIRTHS = 10


class RebirthService:
    @staticmethod
    def _cycle_specs(company: NatCompany) -> list[dict]:
        rank = max(0, int(company.rebirth_count or 0))
        return [
            spec for spec in visible_business_specs(specialization=company.specialization)
            if int(spec.get("rebirth_required", 0)) == rank
        ]

    @classmethod
    def terminal_spec(cls, company: NatCompany) -> dict:
        specs = cls._cycle_specs(company)
        if not specs:
            raise ValueError("Для этой отрасли не настроено перерождение")
        return max(specs, key=lambda spec: (spec["industry_order"], spec["id"]))

    @classmethod
    def announcement_gate_spec(cls, company: NatCompany) -> dict:
        """Use the penultimate factory; a one-factory rebirth stage uses its sole factory."""
        specs = sorted(
            cls._cycle_specs(company),
            key=lambda spec: (spec["industry_order"], spec["id"]),
        )
        if not specs:
            raise ValueError("Для этой отрасли не настроено перерождение")
        return specs[-2] if len(specs) > 1 else specs[-1]

    @classmethod
    async def blockers(cls, session: AsyncSession, company: NatCompany) -> list[str]:
        cid = company.id
        reasons = []
        checks = (
            (NatLoan, (NatLoan.company_id == cid, NatLoan.remaining_debt > 0.001, NatLoan.status.in_(("ACTIVE", "DEFAULTED"))), "Погасите кредит"),
            (NatStateCreditLoan, (NatStateCreditLoan.company_id == cid, NatStateCreditLoan.status.in_(("PENDING", "ACTIVE", "DEFAULTED"))), "Закройте заявку или долг по государственному кредиту"),
            (NatMarketOrder, (NatMarketOrder.company_id == cid, or_(NatMarketOrder.state_advance_remaining_amount > 0.001, NatMarketOrder.state_advance_remaining_quantity > 1e-9)), "Верните аванс государству через продажу профинансированного товара"),
            (NatSupplyDeal, (or_(NatSupplyDeal.buyer_company_id == cid, NatSupplyDeal.supplier_company_id == cid), NatSupplyDeal.status.in_(("PENDING", "ACTIVE"))), "Завершите активные сделки и предложения"),
            (NatContract, (or_(NatContract.issuer_company_id == cid, NatContract.target_company_id == cid), NatContract.status.in_(("OPEN", "ACTIVE"))), "Завершите действующий контракт"),
            (NatStateShareHolding, (NatStateShareHolding.company_id == cid, NatStateShareHolding.quantity > 0), "Продайте акции государства"),
            (NatInstrumentPosition, (NatInstrumentPosition.company_id == cid, NatInstrumentPosition.quantity > 0), "Закройте финансовые позиции"),
        )
        for model, clauses, message in checks:
            if await session.scalar(select(model.id).where(*clauses).limit(1)):
                reasons.append(message)

        factories = list((await session.scalars(select(NatJointFactory).where(or_(
            NatJointFactory.company_a_id == cid,
            NatJointFactory.company_b_id == cid,
        )))).all())
        for factory in factories:
            own_stock = factory.stock_a_json if factory.company_a_id == cid else factory.stock_b_json
            if factory.status == "ACTIVE" or any(float(value) > 0.000001 for value in (own_stock or {}).values()):
                reasons.append("Закройте совместный завод и заберите свою продукцию")
                break
        return reasons

    @classmethod
    async def snapshot(cls, session: AsyncSession, company: NatCompany) -> dict:
        rank = max(0, int(company.rebirth_count or 0))
        terminal = cls.terminal_spec(company)
        gate = cls.announcement_gate_spec(company)
        owned = await session.scalar(select(NatBusiness.id).where(
            NatBusiness.company_id == company.id,
            NatBusiness.business_type == terminal["id"],
            NatBusiness.status.not_in(("BANKRUPT", "MERGING")),
        ).limit(1))
        gate_owned = await session.scalar(select(NatBusiness.id).where(
            NatBusiness.company_id == company.id,
            NatBusiness.business_type == gate["id"],
            NatBusiness.status.not_in(("BANKRUPT", "MERGING")),
        ).limit(1))
        reasons = await cls.blockers(session, company)
        if not owned:
            reasons.insert(0, f"Откройте «{terminal['name']}»")
        if rank >= MAX_REBIRTHS:
            reasons.insert(0, "Все десять перерождений завершены")
        if company.is_bankrupt:
            reasons.append("Завершите банкротство")

        announcement_sent = company.rebirth_announcement_for_count == rank
        return {
            "count": rank,
            "max_count": MAX_REBIRTHS,
            "bonus_pct": rank * 25,
            "next_bonus_pct": (rank + 1) * 25,
            "available": not reasons,
            "reasons": reasons,
            "terminal_name": terminal["name"],
            "next_factory": next((
                spec["name"] for spec in visible_business_specs(specialization=company.specialization)
                if int(spec.get("rebirth_required", 0)) == rank + 1
            ), None),
            "announcement_gate_name": gate["name"],
            "announcement_gate_reached": bool(gate_owned),
            "announcement_sent": announcement_sent,
            "announcement_available": bool(gate_owned) and not announcement_sent and rank < MAX_REBIRTHS,
            "preserved": "Название, отрасль, PVC-баланс, купленная PVC-прокачка, премиальные улучшения, акции и держатели, дивиденды и история выплат",
            "reset": "Cash, склад, заводы, уровни, мастерство, армия, территория и обычные улучшения. Облигации списываются без возврата: их стоимость остаётся в казне",
        }

    @classmethod
    async def _notice_recipients(cls, session: AsyncSession) -> list[int]:
        current_players = await session.scalars(
            select(User.tg_id)
            .join(NatCompany, NatCompany.user_id == User.id)
            .distinct()
        )
        ids = {int(tg_id) for tg_id in current_players.all() if tg_id is not None and int(tg_id) > 0}
        ids.update(await PlayerRegistryService.get_registered_tg_ids(session))
        return sorted(ids)

    @classmethod
    async def announce(cls, session: AsyncSession, company_id: int, *, expected_count: int) -> dict:
        company = await session.scalar(select(NatCompany).where(
            NatCompany.id == company_id
        ).with_for_update().execution_options(populate_existing=True))
        if company is None:
            raise ValueError("Компания не найдена")
        if int(company.rebirth_count or 0) != expected_count:
            raise ValueError("Этап перерождения изменился. Обновите экран")
        status = await cls.snapshot(session, company)
        if status["announcement_sent"]:
            raise ValueError("Объявление об этом перерождении уже отправлено")
        if not status["announcement_available"]:
            raise ValueError(f"Объявление откроется после предприятия «{status['announcement_gate_name']}»")

        recipient_ids = await cls._notice_recipients(session)
        company.rebirth_announcement_for_count = expected_count
        await session.commit()

        message = (
            f"📣 Компания «{company.name}» [{company.ticker}] готовится к перерождению.\n\n"
            "После перерождения её акции останутся у владельцев, но рыночная цена упадёт на 99%. "
            "Начисление дивидендов продолжится. Автоматического выкупа не будет: при желании "
            "продайте акции через обычную биржу до перерождения."
        )
        try:
            from backend.natbirzha.services.event_broadcaster import EventBroadcaster

            bot = EventBroadcaster._get_bot()
        except Exception:
            bot = None
            logger.exception("Could not resolve Telegram bot for rebirth announcement")

        if bot is None:
            delivered = 0
            failed = len(recipient_ids)
        else:
            semaphore = asyncio.Semaphore(15)

            async def send_one(telegram_id: int) -> bool:
                async with semaphore:
                    try:
                        await bot.send_message(chat_id=telegram_id, text=message, parse_mode=None)
                        return True
                    except Exception:
                        logger.warning("Could not send rebirth announcement to TG user %s", telegram_id, exc_info=True)
                        return False

            results = await asyncio.gather(*(send_one(telegram_id) for telegram_id in recipient_ids))
            delivered = sum(results)
            failed = len(results) - delivered

        return {
            "success": True,
            "announcement_sent": True,
            "recipient_count": len(recipient_ids),
            "delivered": delivered,
            "failed": failed,
        }

    @classmethod
    async def _rebase_stock(cls, session: AsyncSession, company: NatCompany, old_price: float, now: datetime) -> dict | None:
        from backend.natbirzha.models import NatStockOrder
        from backend.natbirzha.services.stock_orderbook_service import StockOrderbookService
        from backend.natbirzha.services.stock_service import StockService

        stock = await session.scalar(select(NatStock).where(
            NatStock.company_id == company.id
        ).with_for_update())
        if stock is None:
            return None

        new_price = max(0.01, round(max(0.01, old_price) * 0.01, 4))
        total_shares = max(1, int(stock.total_shares or 1))
        raw_valuation = await StockService.calculate_company_valuation(session, company)
        rebased_valuation = new_price * total_shares
        stock.rebirth_valuation_scale = rebased_valuation / max(1.0, raw_valuation)
        stock.current_price = new_price
        stock.last_valuation = rebased_valuation
        stock.valuation_updated_at = now

        orders = (await session.scalars(select(NatStockOrder).where(
            NatStockOrder.stock_id == stock.id,
            NatStockOrder.status == "ACTIVE",
            NatStockOrder.remaining_shares > 0,
        ).with_for_update())).all()
        for order in orders:
            if StockOrderbookService._is_ipo_order(stock, order):
                order.price = new_price

        await StockService.record_price_snapshot(session, stock, now)
        return {"price_before": round(old_price, 4), "price_after": new_price}

    @classmethod
    async def perform(cls, session: AsyncSession, company_id: int, *, expected_count: int, now: datetime | None = None) -> dict:
        from backend.natbirzha.services.idle_economy_service import IdleEconomyService
        from backend.natbirzha.services.company_bootstrap import bootstrap_company_state
        from backend.natbirzha.services.company_reset_v2 import delete_company_complete_state
        from backend.natbirzha.services.tax_service import TaxService
        from backend.natbirzha.services.state_treasury_service import StateTreasuryService

        current = normalize_dt(now or get_game_now())
        treasury = await StateTreasuryService.get_or_create(session, commit=False, for_update=True)
        await IdleEconomyService.settle_company(session, company_id, now=current)
        company = await session.scalar(select(NatCompany).where(
            NatCompany.id == company_id
        ).with_for_update().execution_options(populate_existing=True))
        if company is None:
            raise ValueError("Компания не найдена")
        if int(company.rebirth_count or 0) != expected_count:
            raise ValueError("Состояние перерождения изменилось. Обновите экран")
        status = await cls.snapshot(session, company)
        if not status["available"]:
            raise ValueError(" · ".join(status["reasons"]))

        stock_before = await session.scalar(select(NatStock).where(
            NatStock.company_id == company.id
        ).with_for_update())
        old_stock_price = float(stock_before.current_price or 0.01) if stock_before else None
        tax = await TaxService.summary(session, company.id, now=current)
        tax_paid = round(float(tax["total_due"]) + float(tax["current_period_estimated_tax"]), 2)
        if float(company.cash) < tax_paid:
            raise ValueError(f"Для закрытия налогов перед перерождением нужно {tax_paid} cash")

        session.add(NatCompanyRebirth(
            company_id=company.id,
            rank=expected_count + 1,
            cash_before=float(company.cash),
            tax_paid=tax_paid,
            created_at=current,
        ))
        treasury.cash = round(float(treasury.cash) + tax_paid, 2)
        await delete_company_complete_state(session, company.id, for_rebirth=True)
        await session.execute(update(NatCompanyAidRequest).where(
            NatCompanyAidRequest.company_id == company.id,
            NatCompanyAidRequest.status == "OPEN",
        ).values(status="CANCELLED"))
        company.level = 1
        company.xp = 0
        for field in ("mastery_xp", "mastery_rank", "mastery_points_spent", "mastery_industry", "mastery_logistics", "mastery_doctrine", "mastery_intelligence"):
            setattr(company, field, 0)
        company.cash = float(nat_settings.STARTING_CASH)
        company.territory_tiles = int(nat_settings.STARTING_TERRITORY_TILES)
        company.max_territory = 20
        company.business_slot_capacity = 10
        company.business_slot_upgrade_ready_at = None
        company.military_rating = 1000
        company.is_bankrupt = False
        company.licensed_foreign_spec = None
        company.last_respec_at = None
        company.rebirth_count = expected_count + 1
        company.last_rebirth_at = current
        company.updated_at = current
        await bootstrap_company_state(session, company, now=current)
        await session.flush()

        stock_rebase = None
        if old_stock_price is not None:
            stock_rebase = await cls._rebase_stock(session, company, old_stock_price, current)
        return {
            "success": True,
            "rebirth_count": company.rebirth_count,
            "production_bonus_pct": company.rebirth_count * 25,
            "tax_paid": tax_paid,
            "cash": company.cash,
            "next_factory": status["next_factory"],
            "stock_rebase": stock_rebase,
        }
