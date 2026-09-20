"""Reset one NATBIRZHA company for local/dev testing, preserving the main User."""
import asyncio, sys
from sqlalchemy import delete, select
from backend.db.session import async_session_factory
from backend.db.models import User
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.market import NatMarketOrder
from backend.natbirzha.models.stocks import NatStock, NatStockHolding
from backend.natbirzha.models.military import NatArmy
from backend.natbirzha.models.alliances import NatAllianceMember
from backend.natbirzha.models.restructuring import NatRestructuring, NatDailyFinancials

async def reset(tg_id: int) -> bool:
    async with async_session_factory() as session:
        user = (await session.execute(select(User).where(User.tg_id == tg_id))).scalar_one_or_none()
        if not user:
            print(f"No user found for tg_id={tg_id}"); return False
        company = (await session.execute(select(NatCompany).where(NatCompany.user_id == user.id))).scalar_one_or_none()
        if not company:
            print(f"No NATBIRZHA company found for tg_id={tg_id}"); return False
        cid = company.id
        for model in (NatMarketOrder, NatInventory, NatStockHolding, NatArmy, NatRestructuring, NatDailyFinancials):
            if hasattr(model, 'company_id'):
                await session.execute(delete(model).where(model.company_id == cid))
        if hasattr(NatAllianceMember, 'company_id'):
            await session.execute(delete(NatAllianceMember).where(NatAllianceMember.company_id == cid))
        await session.execute(delete(NatStock).where(NatStock.company_id == cid))
        await session.execute(delete(NatFactory).where(NatFactory.company_id == cid))
        await session.execute(delete(NatCompany).where(NatCompany.id == cid))
        await session.commit()
        print(f"NATBIRZHA reset: company={cid}, tg_id={tg_id}; main User preserved.")
        return True

if __name__ == '__main__':
    if len(sys.argv) != 2: raise SystemExit('Usage: python tools/reset_natbirzha.py <telegram_user_id>')
    asyncio.run(reset(int(sys.argv[1])))
