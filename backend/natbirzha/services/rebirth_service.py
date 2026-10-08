"""Atomic company renewal with permanent yield bonuses and protected obligations."""
from datetime import datetime
from sqlalchemy import select, or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.natbirzha.catalogs.businesses import visible_business_specs
from backend.natbirzha.config import get_game_now, normalize_dt, nat_settings
from backend.natbirzha.models import (
    NatCompany, NatBusiness, NatLoan, NatStateCreditLoan, NatMarketOrder,
    NatStock, NatStockHolding, NatStockOrder, NatStateBondHolding,
    NatStateShareHolding, NatInstrumentPosition, NatSupplyDeal, NatContract,
    NatJointFactory, NatJointFactoryProposal,
    NatDividend, NatHourlyDividendAccrual,
)
from backend.natbirzha.models.rebirth import NatCompanyRebirth
from backend.natbirzha.models.company_aid import NatCompanyAidRequest

MAX_REBIRTHS = 10


class RebirthService:
    @staticmethod
    def terminal_spec(company: NatCompany) -> dict:
        rank = max(0, int(company.rebirth_count or 0))
        specs = [s for s in visible_business_specs(specialization=company.specialization)
                 if int(s.get('rebirth_required', 0)) == rank]
        if not specs:
            raise ValueError('Для этой отрасли не настроено перерождение')
        return max(specs, key=lambda s: (s['industry_order'], s['id']))

    @classmethod
    async def blockers(cls, session: AsyncSession, company: NatCompany) -> list[str]:
        cid = company.id
        reasons = []
        checks = (
            (NatLoan, (NatLoan.company_id == cid, NatLoan.remaining_debt > 0.001, NatLoan.status.in_(('ACTIVE', 'DEFAULTED'))), 'Погасите кредит'),
            (NatStateCreditLoan, (NatStateCreditLoan.company_id == cid, NatStateCreditLoan.status.in_(('PENDING', 'ACTIVE', 'DEFAULTED'))), 'Закройте заявку или долг по государственному кредиту'),
            (NatMarketOrder, (NatMarketOrder.company_id == cid, or_(NatMarketOrder.state_advance_remaining_amount > 0.001, NatMarketOrder.state_advance_remaining_quantity > 1e-9)), 'Верните аванс государству через продажу профинансированного товара'),
            (NatSupplyDeal, (or_(NatSupplyDeal.buyer_company_id == cid, NatSupplyDeal.supplier_company_id == cid), NatSupplyDeal.status.in_(('PENDING', 'ACTIVE'))), 'Завершите активные сделки и предложения'),
            (NatContract, (or_(NatContract.issuer_company_id == cid, NatContract.target_company_id == cid), NatContract.status.in_(('OPEN', 'ACTIVE'))), 'Завершите действующий контракт'),
            (NatJointFactoryProposal, (or_(NatJointFactoryProposal.proposer_company_id == cid, NatJointFactoryProposal.partner_company_id == cid), NatJointFactoryProposal.status == 'PENDING'), 'Закройте предложения совместных заводов'),
            (NatStateBondHolding, (NatStateBondHolding.company_id == cid, NatStateBondHolding.quantity > 0), 'Продайте облигации'),
            (NatStateShareHolding, (NatStateShareHolding.company_id == cid, NatStateShareHolding.quantity > 0), 'Продайте акции государства'),
            (NatInstrumentPosition, (NatInstrumentPosition.company_id == cid, NatInstrumentPosition.quantity > 0), 'Закройте финансовые позиции'),
        )
        for model, clauses, message in checks:
            if await session.scalar(select(model.id).where(*clauses).limit(1)):
                reasons.append(message)
        stocks = list((await session.scalars(select(NatStock).where(NatStock.company_id == cid))).all())
        own_ids = [s.id for s in stocks]
        foreign = select(NatStockHolding.id).where(NatStockHolding.holder_company_id == cid, NatStockHolding.shares_count > 0)
        if own_ids:
            pending_dividends = await session.scalar(select(NatHourlyDividendAccrual.id).where(
                NatHourlyDividendAccrual.stock_id.in_(own_ids),
                NatHourlyDividendAccrual.status == 'OPEN',
                NatHourlyDividendAccrual.dividend_pool > 0.001,
            ).limit(1))
            pending_legacy = await session.scalar(select(NatDividend.id).where(
                NatDividend.stock_id.in_(own_ids), NatDividend.is_settled.is_(False),
                NatDividend.dividend_pool > 0.001,
            ).limit(1))
            if pending_dividends or pending_legacy:
                reasons.append('Дождитесь выплаты накопленных дивидендов')
            foreign = foreign.where(NatStockHolding.stock_id.not_in(own_ids))
            if await session.scalar(select(NatStockHolding.id).where(NatStockHolding.stock_id.in_(own_ids), NatStockHolding.holder_company_id != cid, NatStockHolding.shares_count > 0).limit(1)):
                reasons.append('Выкупите акции своей компании у других владельцев')
            if await session.scalar(select(NatStockOrder.id).where(NatStockOrder.stock_id.in_(own_ids), NatStockOrder.trader_company_id != cid, NatStockOrder.status == 'ACTIVE').limit(1)):
                reasons.append('Урегулируйте чужие заявки на акции своей компании')
        if await session.scalar(foreign.limit(1)):
            reasons.append('Продайте акции других компаний')
        factories = list((await session.scalars(select(NatJointFactory).where(or_(NatJointFactory.company_a_id == cid, NatJointFactory.company_b_id == cid)))).all())
        for factory in factories:
            own_stock = factory.stock_a_json if factory.company_a_id == cid else factory.stock_b_json
            if factory.status == 'ACTIVE' or any(float(v) > 0.000001 for v in (own_stock or {}).values()):
                reasons.append('Закройте совместный завод и заберите свою продукцию')
                break
        return reasons

    @classmethod
    async def snapshot(cls, session: AsyncSession, company: NatCompany) -> dict:
        rank = max(0, int(company.rebirth_count or 0))
        terminal = cls.terminal_spec(company)
        owned = await session.scalar(select(NatBusiness.id).where(NatBusiness.company_id == company.id, NatBusiness.business_type == terminal['id'], NatBusiness.status.not_in(('BANKRUPT', 'MERGING'))).limit(1))
        reasons = await cls.blockers(session, company)
        if not owned:
            reasons.insert(0, f"Откройте «{terminal['name']}»")
        if rank >= MAX_REBIRTHS:
            reasons.insert(0, 'Все десять перерождений завершены')
        if company.is_bankrupt:
            reasons.append('Завершите банкротство')
        return {'count': rank, 'max_count': MAX_REBIRTHS, 'bonus_pct': rank * 25,
                'next_bonus_pct': (rank + 1) * 25, 'available': not reasons,
                'reasons': reasons, 'terminal_name': terminal['name'],
                'next_factory': next((s['name'] for s in visible_business_specs(specialization=company.specialization) if s.get('rebirth_required') == rank + 1), None),
                'preserved': 'Название, отрасль, PVC-баланс, купленная PVC-прокачка и премиальные улучшения',
                'reset': 'Cash, склад, заводы, уровни, мастерство, армия, территория и обычные улучшения'}

    @classmethod
    async def perform(cls, session: AsyncSession, company_id: int, *, expected_count: int, now: datetime | None = None) -> dict:
        from backend.natbirzha.services.idle_economy_service import IdleEconomyService
        from backend.natbirzha.services.company_bootstrap import bootstrap_company_state
        from backend.natbirzha.services.company_reset_v2 import delete_company_complete_state
        from backend.natbirzha.services.tax_service import TaxService
        from backend.natbirzha.services.state_treasury_service import StateTreasuryService
        current = normalize_dt(now or get_game_now())
        # Match settlement's treasury -> company lock ordering.
        treasury = await StateTreasuryService.get_or_create(session, commit=False, for_update=True)
        await IdleEconomyService.settle_company(session, company_id, now=current)
        company = await session.scalar(select(NatCompany).where(NatCompany.id == company_id).with_for_update().execution_options(populate_existing=True))
        if company is None:
            raise ValueError('Компания не найдена')
        if int(company.rebirth_count or 0) != expected_count:
            raise ValueError('Состояние перерождения изменилось. Обновите экран')
        status = await cls.snapshot(session, company)
        if not status['available']:
            raise ValueError(' · '.join(status['reasons']))
        tax = await TaxService.summary(session, company.id, now=current)
        tax_paid = round(float(tax['total_due']) + float(tax['current_period_estimated_tax']), 2)
        if float(company.cash) < tax_paid:
            raise ValueError(f'Для закрытия налогов перед перерождением нужно {tax_paid} cash')
        session.add(NatCompanyRebirth(company_id=company.id, rank=expected_count + 1, cash_before=float(company.cash), tax_paid=tax_paid, created_at=current))
        treasury.cash = round(float(treasury.cash) + tax_paid, 2)
        await delete_company_complete_state(session, company.id, for_rebirth=True)
        await session.execute(update(NatCompanyAidRequest).where(NatCompanyAidRequest.company_id == company.id, NatCompanyAidRequest.status == 'OPEN').values(status='CANCELLED'))
        company.level = 1
        company.xp = 0
        for field in ('mastery_xp', 'mastery_rank', 'mastery_points_spent', 'mastery_industry', 'mastery_logistics', 'mastery_doctrine', 'mastery_intelligence'):
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
        return {'success': True, 'rebirth_count': company.rebirth_count, 'production_bonus_pct': company.rebirth_count * 25, 'tax_paid': tax_paid, 'cash': company.cash, 'next_factory': status['next_factory']}
