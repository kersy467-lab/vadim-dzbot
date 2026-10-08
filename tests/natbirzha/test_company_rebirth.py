import asyncio
from datetime import timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models
from backend.natbirzha.models import NatCompany, NatBusiness, NatInventory, NatLoan
from backend.natbirzha.catalogs.businesses import visible_business_specs
from backend.natbirzha.config import get_game_now, nat_settings


def test_rebirth_resets_assets_preserves_paid_progress_and_rejects_repeat():
    assert hasattr(NatCompany, 'rebirth_count')
    from backend.natbirzha.services.rebirth_service import RebirthService
    async def check():
        engine=create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.execute(text("PRAGMA foreign_keys=ON"))
            await conn.run_sync(Base.metadata.create_all)
        sessions=async_sessionmaker(engine,expire_on_commit=False)
        now=get_game_now()
        async with sessions() as session:
            session.add(User(id=997901,tg_id=997901,full_name='Renewal User'))
            await session.flush()
            company=NatCompany(user_id=997901,name='Renewal',specialization='miner',level=60,xp=1000000,mastery_rank=5,mastery_xp=0,cash=1000000,pvc_balance=123,nat_balance=123,industry_upgrade_levels_json={'miner':2},territory_tiles=18)
            session.add(company);await session.flush()
            final=max((s for s in visible_business_specs(specialization='miner') if not s.get('rebirth_required')),key=lambda s:s['industry_order'])
            session.add(NatBusiness(company_id=company.id,business_type=final['id'],specialization='miner',stage=1,status='PAUSED_MANUAL',last_settled_at=now))
            session.add(NatInventory(company_id=company.id,item_id='coal',quantity=9999))
            from backend.natbirzha.models.tax import NatCompanyProfitPeriod
            from backend.natbirzha.tax_rules import get_period_bounds
            start,end=get_period_bounds(now)
            session.add(NatCompanyProfitPeriod(company_id=company.id,period_start=start,period_end=end,realized_revenue=10000,cost_of_goods_sold=2000))
            await session.flush()
            from backend.natbirzha.models.premium import NatPremiumLedgerEntry, NatPremiumLicense, NatMilitaryUpgrade
            ledger=NatPremiumLedgerEntry(company_id=company.id,amount=-80,balance_before=203,balance_after=123,operation_type='industry_upgrade',operation_key='renewal-paid-upgrade')
            session.add(ledger);await session.flush()
            session.add(NatPremiumLicense(company_id=company.id,license_code='rare_mining',starts_at=now,expires_at=now+timedelta(days=2),purchase_ledger_id=ledger.id))
            session.add(NatMilitaryUpgrade(company_id=company.id,upgrade_code='precision_guidance',level=2))
            await session.flush()
            before_id=company.id
            result=await RebirthService.perform(session,company.id,expected_count=0,now=now)
            assert result['rebirth_count']==1
            assert result['tax_paid']==1040
            assert company.id==before_id and company.level==1 and company.xp==0
            assert company.mastery_rank==0 and company.cash==nat_settings.STARTING_CASH
            assert company.industry_upgrade_levels_json=={'miner':2}
            assert company.pvc_balance==123
            assert await session.scalar(select(NatPremiumLicense.id).where(NatPremiumLicense.company_id==company.id))
            assert await session.scalar(select(NatMilitaryUpgrade.level).where(NatMilitaryUpgrade.company_id==company.id))==2
            assert await session.scalar(select(NatPremiumLedgerEntry.id).where(NatPremiumLedgerEntry.company_id==company.id))
            businesses=list((await session.scalars(select(NatBusiness).where(NatBusiness.company_id==company.id))).all())
            assert len(businesses)==1 and businesses[0].stage==1
            coal=await session.scalar(select(NatInventory).where(NatInventory.company_id==company.id,NatInventory.item_id=='coal'))
            assert not coal or coal.quantity<9999
            try:
                await RebirthService.perform(session,company.id,expected_count=0,now=now)
                assert False,'repeat reset must be rejected'
            except ValueError:
                pass
        await engine.dispose()
    asyncio.run(check())


def test_rebirth_protects_external_shareholders():
    from backend.natbirzha.services.rebirth_service import RebirthService
    from backend.natbirzha.models import NatStock, NatStockHolding
    async def check():
        engine=create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
        sessions=async_sessionmaker(engine,expire_on_commit=False)
        now=get_game_now()
        async with sessions() as session:
            company=NatCompany(user_id=997911,name='Issuer renewal',specialization='miner',level=60,cash=1000000)
            investor=NatCompany(user_id=997912,name='Protected investor',specialization='water')
            session.add_all([company,investor]);await session.flush()
            final=max((s for s in visible_business_specs(specialization='miner') if not s.get('rebirth_required')),key=lambda s:s['industry_order'])
            session.add(NatBusiness(company_id=company.id,business_type=final['id'],specialization='miner',stage=1,status='PAUSED_MANUAL',last_settled_at=now))
            stock=NatStock(company_id=company.id)
            session.add(stock);await session.flush()
            holding=NatStockHolding(stock_id=stock.id,holder_company_id=investor.id,shares_count=100)
            session.add(holding);await session.flush()
            try:
                await RebirthService.perform(session,company.id,expected_count=0,now=now)
                assert False,'external shareholders must not lose their shares'
            except ValueError as exc:
                assert 'акции' in str(exc).lower()
            assert holding.shares_count==100 and company.rebirth_count==0
        await engine.dispose()
    asyncio.run(check())


def test_rebirth_cannot_erase_an_outstanding_loan():
    assert hasattr(NatCompany, 'rebirth_count')
    from backend.natbirzha.services.rebirth_service import RebirthService
    async def check():
        engine=create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
        sessions=async_sessionmaker(engine,expire_on_commit=False)
        now=get_game_now()
        async with sessions() as session:
            company=NatCompany(user_id=997902,name='Loan renewal',specialization='miner',level=60,cash=1000000)
            session.add(company);await session.flush()
            final=max((s for s in visible_business_specs(specialization='miner') if not s.get('rebirth_required')),key=lambda s:s['industry_order'])
            session.add(NatBusiness(company_id=company.id,business_type=final['id'],specialization='miner',stage=1,status='PAUSED_MANUAL',last_settled_at=now))
            loan=NatLoan(company_id=company.id,principal=100,remaining_debt=100,due_date=(now+timedelta(days=1)).date(),status='ACTIVE')
            session.add(loan);await session.flush()
            try:
                await RebirthService.perform(session,company.id,expected_count=0,now=now)
                assert False,'loan must not vanish'
            except ValueError as exc:
                assert 'кредит' in str(exc).lower()
            assert loan.remaining_debt==100 and company.rebirth_count==0
            loan.remaining_debt=0
            loan.status='PAID'
            from backend.natbirzha.models import NatMarketOrder
            order=NatMarketOrder(company_id=company.id,order_type='SELL',item_id='coal',price=10,quantity=1,remaining_qty=0,status='FILLED',state_advance_remaining_amount=0,state_advance_remaining_quantity=0.0001)
            session.add(order);await session.flush()
            try:
                await RebirthService.perform(session,company.id,expected_count=0,now=now)
                assert False,'funded quantity must not disappear when rounded cash is zero'
            except ValueError as exc:
                assert 'аванс' in str(exc).lower()
            assert company.rebirth_count==0
        await engine.dispose()
    asyncio.run(check())
