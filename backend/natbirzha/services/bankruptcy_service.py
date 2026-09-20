from datetime import date, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.natbirzha.config import nat_settings, get_game_today, get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.restructuring import NatRestructuring, NatDailyFinancials
from backend.natbirzha.models.stocks import NatStock, NatStockOrder
from backend.natbirzha.models.market import NatMarketOrder
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.services.company_service import CompanyService

class BankruptcyService:
    @staticmethod
    async def file_restructuring(session: AsyncSession, company: NatCompany) -> NatRestructuring:
        if company.is_bankrupt:
            raise ValueError("Company is already undergoing restructuring.")

        now = get_game_now()
        today = get_game_today()

        # Immutable snapshot of audited NAV
        nav = await CompanyService.calculate_audited_nav(session, company)
        liquidation_pool = round(nav * nat_settings.BANKRUPTCY_LIQUIDATION_POOL_PCT, 2)  # 40%

        # Strictly next 2 real calendar dates in GAME_TIMEZONE
        start_date = today + timedelta(days=1)
        end_date = today + timedelta(days=nat_settings.BANKRUPTCY_FEE_CALENDAR_DAYS)

        restructuring = NatRestructuring(
            company_id=company.id,
            snapshot_nav=nav,
            liquidation_pool=liquidation_pool,
            fee_start_date=start_date,
            fee_end_date=end_date,
            fee_rate=nat_settings.BANKRUPTCY_FEE_RATE,
            status="ACTIVE",
            created_at=now
        )
        session.add(restructuring)
        company.is_bankrupt = True

        # Credit liquidation emergency pool to company cash for recovery (guaranteed 5,000 cash recovery floor)
        emergency_grant = max(5000.0, liquidation_pool)
        company.cash = round(company.cash + emergency_grant, 2)

        # Grant emergency water ration so primary resource extraction never deadlocks
        water_res = await session.execute(
            select(NatInventory).where(
                NatInventory.company_id == company.id,
                NatInventory.item_id == "water"
            )
        )
        water_inv = water_res.scalar_one_or_none()
        if not water_inv:
            water_inv = NatInventory(company_id=company.id, item_id="water", quantity=10.0)
            session.add(water_inv)
        elif water_inv.quantity < 5.0:
            water_inv.quantity = 10.0

        # Delist public stocks during bankruptcy & cancel active orders
        stock_res = await session.execute(
            select(NatStock).where(NatStock.company_id == company.id)
        )
        stock = stock_res.scalar_one_or_none()
        if stock:
            stock.is_listed = False
            orders_res = await session.execute(
                select(NatStockOrder).where(
                    NatStockOrder.stock_id == stock.id,
                    NatStockOrder.status == "ACTIVE"
                )
            )
            for ord_item in orders_res.scalars().all():
                ord_item.status = "CANCELLED"

        # Cancel active commodity market orders & unreserve inventory
        market_orders_res = await session.execute(
            select(NatMarketOrder).where(
                NatMarketOrder.company_id == company.id,
                NatMarketOrder.status == "ACTIVE"
            )
        )
        for m_ord in market_orders_res.scalars().all():
            m_ord.status = "CANCELLED"
            m_ord.closed_at = now
            if m_ord.order_type == "SELL":
                m_inv_res = await session.execute(
                    select(NatInventory).where(
                        NatInventory.company_id == company.id,
                        NatInventory.item_id == m_ord.item_id
                    )
                )
                m_inv = m_inv_res.scalar_one_or_none()
                if m_inv:
                    m_inv.reserved_quantity = max(0.0, m_inv.reserved_quantity - m_ord.remaining_qty)
            elif m_ord.order_type == "BUY":
                company.cash = round(company.cash + (m_ord.price * m_ord.remaining_qty), 2)

        await session.commit()
        await session.refresh(restructuring)
        return restructuring

    @staticmethod
    async def process_daily_restructuring_fee(
        session: AsyncSession,
        company: NatCompany,
        calendar_date: Optional[date] = None
    ) -> Dict[str, Any]:
        calendar_date = calendar_date or get_game_today()

        res = await session.execute(
            select(NatRestructuring).where(
                NatRestructuring.company_id == company.id,
                NatRestructuring.status == "ACTIVE"
            )
        )
        restruct = res.scalar_one_or_none()
        if not restruct:
            return {"status": "not_in_restructuring"}

        end_d = restruct.fee_end_date if isinstance(restruct.fee_end_date, date) else date.fromisoformat(str(restruct.fee_end_date))
        start_d = restruct.fee_start_date if isinstance(restruct.fee_start_date, date) else date.fromisoformat(str(restruct.fee_start_date))

        # Check if calendar window passed -> complete restructuring
        if calendar_date > end_d:
            restruct.status = "COMPLETED"
            company.is_bankrupt = False
            await session.commit()
            return {"status": "restructuring_completed", "company_id": company.id}

        # Check if currently inside fee calendar window
        if start_d <= calendar_date <= end_d:
            fin_res = await session.execute(
                select(NatDailyFinancials).where(
                    NatDailyFinancials.company_id == company.id,
                    NatDailyFinancials.calendar_date == calendar_date
                )
            )
            fin = fin_res.scalar_one_or_none()
            closed_profit = fin.closed_profit if fin else 0.0

            fee = 0.0
            if closed_profit > 0:
                fee = round(closed_profit * restruct.fee_rate, 2)  # 30%
                if company.cash >= fee:
                    company.cash = round(company.cash - fee, 2)
                    if fin:
                        fin.developer_fee_paid = fee

            await session.commit()
            return {
                "status": "fee_processed",
                "calendar_date": str(calendar_date),
                "closed_profit": closed_profit,
                "fee_deducted": fee
            }

        return {"status": "outside_fee_window"}

    @classmethod
    async def process_daily_liquidations(cls, session: AsyncSession) -> int:
        """
        Global daily scheduler handler for bankruptcies & restructuring fees.
        Called at 00:01 GAME_TIMEZONE.
        """
        active_restruct_res = await session.execute(
            select(NatRestructuring, NatCompany)
            .join(NatCompany, NatRestructuring.company_id == NatCompany.id)
            .where(NatRestructuring.status == "ACTIVE")
        )
        records = active_restruct_res.all()
        processed_count = 0
        yesterday = get_game_today() - timedelta(days=1)

        for restruct, company in records:
            await cls.process_daily_restructuring_fee(session, company, yesterday)
            processed_count += 1

        return processed_count

