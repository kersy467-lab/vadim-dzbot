import asyncio
from datetime import timedelta
from math import isclose

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.db.models import Base
import backend.natbirzha.models
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.progression_service import progress_snapshot, mastery_xp_required_for_rank
from backend.natbirzha.services.idle_economy_service import IdleEconomyService


def test_mastery_increases_actual_output_without_spending_more_inputs_or_creating_cash():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        now = get_game_now().replace(hour=14, minute=0, second=0, microsecond=0)
        spec = get_business_spec('coal_open_pit')
        async with sessions() as session:
            companies = []
            for index, (rank, rebirths) in enumerate(((0, 0), (5, 0), (0, 1))):
                company = NatCompany(user_id=991801+index, name=f'Output {rank} {rebirths}', specialization='miner', cash=100000, level=60, rebirth_count=rebirths, mastery_rank=rank, mastery_xp=mastery_xp_required_for_rank(rank))
                session.add(company)
                await session.flush()
                session.add(NatBusiness(company_id=company.id, business_type=spec['id'], specialization='miner', stage=1, status='ACTIVE', base_income_per_hour=spec['base_income_per_hour'], base_maintenance_per_hour=spec['base_maintenance_per_hour'], last_settled_at=now-timedelta(hours=1), health=100, efficiency=1, metadata_json={'sale_mode':'HOLD'}))
                for item in spec['inputs_per_hour']:
                    session.add(NatInventory(company_id=company.id,item_id=item,quantity=10000,avg_cost_basis=1))
                companies.append(company)
            await session.flush()
            for company in companies:
                await IdleEconomyService.settle_company(session,company.id,now=now,_process_deals=False)
            inventories = []
            for company in companies:
                rows = list((await session.scalars(select(NatInventory).where(NatInventory.company_id==company.id))).all())
                inventories.append({row.item_id:row for row in rows})
            for item in spec['outputs_per_hour']:
                assert isclose(inventories[1][item].quantity,inventories[0][item].quantity*1.05,abs_tol=0.001)
            for item in spec['inputs_per_hour']:
                assert inventories[1][item].quantity==inventories[0][item].quantity
                assert inventories[2][item].quantity==inventories[0][item].quantity
            for item in spec['outputs_per_hour']:
                assert isclose(inventories[2][item].quantity, inventories[0][item].quantity*1.25, abs_tol=0.001)
            assert companies[0].cash==companies[1].cash==companies[2].cash
            from backend.natbirzha.services.empire_summary_service import EmpireSummaryService
            summaries = [await EmpireSummaryService.build(session,c.id,now=now) for c in companies]
            for item in spec['outputs_per_hour']:
                assert isclose(summaries[1]['businesses'][0]['outputs_per_hour'][item],summaries[0]['businesses'][0]['outputs_per_hour'][item]*1.05,abs_tol=0.001)
            assert progress_snapshot(companies[1])['mastery']['production_bonus_pct']==5
        await engine.dispose()
    asyncio.run(check())


def test_rebirth_boosts_only_its_owners_joint_factory_share():
    from backend.natbirzha.models.joint_factories import NatJointFactory
    from backend.natbirzha.catalogs.businesses import JOINT_FACTORY_RECIPES
    from backend.natbirzha.services.joint_factory_settlement_service import JointFactorySettlementService
    async def check():
        engine=create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn: await conn.run_sync(Base.metadata.create_all)
        sessions=async_sessionmaker(engine,expire_on_commit=False)
        now=get_game_now().replace(hour=14,minute=0,second=0,microsecond=0)
        async with sessions() as session:
            a=NatCompany(user_id=991811,name='Renewed energy',specialization='power_engineer',rebirth_count=1)
            b=NatCompany(user_id=991812,name='Ordinary water',specialization='water')
            session.add_all([a,b]);await session.flush()
            factory=NatJointFactory(recipe_id='joint_power_engineer_water',company_a_id=a.id,company_b_id=b.id,level=1,status='ACTIVE',last_settled_at=now-timedelta(hours=1))
            session.add(factory);await session.flush()
            await JointFactorySettlementService.settle_factory(session,factory.id,now=now)
            rates=JOINT_FACTORY_RECIPES[factory.recipe_id]['levels'][0]['outputs_per_hour']
            for item,rate in rates.items():
                assert isclose(factory.stock_a_json[item],rate/2*1.25,abs_tol=0.0001)
                assert isclose(factory.stock_b_json[item],rate/2,abs_tol=0.0001)
        await engine.dispose()
    asyncio.run(check())
