"""Creator-triggered bankruptcy with asset auction and State liquidation."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now, get_game_today, nat_settings
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import (
    NatBondListing, NatBondSettlement, NatCreatorAuditLog, NatStateBond,
    NatStateBondHolding, NatStateTreasury,
)
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.market import NatMarketOrder, NatMarketTrade
from backend.natbirzha.models.npc import NatNpcDailyVolume
from backend.natbirzha.models.restructuring import NatDailyFinancials
from backend.natbirzha.models.state_shares import NatStateShare, NatStateShareHolding
from backend.natbirzha.models.stocks import NatStockOrder
from backend.natbirzha.services.bankruptcy_market_service import BankruptcyMarketService
from backend.natbirzha.services.market_service import MarketService
from backend.natbirzha.services.state_share_service import StateShareService
from backend.natbirzha.services.state_treasury_service import StateTreasuryService
from backend.natbirzha.services.event_broadcaster import EventBroadcaster


SEIZED_FRACTION = 0.70
RETAINED_FRACTION = 1 - SEIZED_FRACTION


class ForcedBankruptcyService:
    @staticmethod
    async def _cancel_commodity_orders(session: AsyncSession, company: NatCompany) -> None:
        orders = (await session.execute(
            select(NatMarketOrder).where(
                NatMarketOrder.company_id == company.id,
                NatMarketOrder.status == "ACTIVE",
            ).order_by(NatMarketOrder.id.asc()).with_for_update()
        )).scalars().all()
        for order in orders:
            await MarketService.cancel_order(session, company, order.id, commit=False)

    @staticmethod
    async def _cancel_stock_orders(session: AsyncSession, company: NatCompany) -> None:
        orders = (await session.execute(
            select(NatStockOrder).where(
                NatStockOrder.trader_company_id == company.id,
                NatStockOrder.status == "ACTIVE",
            ).with_for_update()
        )).scalars().all()
        for order in orders:
            if order.order_type == "BUY":
                company.cash = round(
                    float(company.cash) + int(order.remaining_shares) * float(order.price), 2
                )
            order.remaining_shares = 0
            order.status = "CANCELLED"

    @classmethod
    async def _liquidate_inventory(
        cls, session: AsyncSession, company: NatCompany, treasury: NatStateTreasury,
        now: datetime,
    ) -> dict[str, float]:
        rows = (await session.execute(
            select(NatInventory).where(NatInventory.company_id == company.id)
            .order_by(NatInventory.item_id.asc()).with_for_update()
        )).scalars().all()
        sales: dict[str, float] = {}
        for inventory in rows:
            original_quantity = max(0.0, float(inventory.quantity))
            offered = round(original_quantity * SEIZED_FRACTION, 4)
            remaining_offer = offered
            if offered <= 0:
                inventory.reserved_quantity = 0.0
                continue
            bids = (await session.execute(
                select(NatMarketOrder).where(
                    NatMarketOrder.item_id == inventory.item_id,
                    NatMarketOrder.order_type == "BUY",
                    NatMarketOrder.status == "ACTIVE",
                    NatMarketOrder.remaining_qty > 0,
                    NatMarketOrder.company_id != company.id,
                ).order_by(NatMarketOrder.price.desc(), NatMarketOrder.created_at.asc(), NatMarketOrder.id.asc())
                .with_for_update()
            )).scalars().all()
            for bid in bids:
                if remaining_offer <= 0:
                    break
                buyer = await session.scalar(
                    select(NatCompany).where(NatCompany.id == bid.company_id).with_for_update()
                )
                if buyer is None or buyer.is_bankrupt:
                    continue
                buyer_inventory = await session.scalar(
                    select(NatInventory).where(
                        NatInventory.company_id == buyer.id,
                        NatInventory.item_id == inventory.item_id,
                    ).with_for_update()
                )
                current_quantity = float(buyer_inventory.quantity) if buyer_inventory else 0.0
                fill = min(remaining_offer, float(bid.remaining_qty))
                if current_quantity + fill > float(nat_settings.INVENTORY_MAX_QUANTITY_PER_ITEM):
                    buyer.cash = round(
                        float(buyer.cash) + float(bid.remaining_qty) * float(bid.price), 2
                    )
                    bid.remaining_qty = 0.0
                    bid.status = "CANCELLED"
                    bid.closed_at = now
                    continue
                amount = round(fill * float(bid.price), 2)
                if buyer_inventory is None:
                    buyer_inventory = NatInventory(
                        company_id=buyer.id, item_id=inventory.item_id,
                        quantity=fill, reserved_quantity=0.0,
                        avg_cost_basis=float(bid.price),
                    )
                    session.add(buyer_inventory)
                else:
                    new_quantity = current_quantity + fill
                    buyer_inventory.avg_cost_basis = round(
                        (current_quantity * float(buyer_inventory.avg_cost_basis) + amount) / new_quantity,
                        4,
                    )
                    buyer_inventory.quantity = round(new_quantity, 4)
                bid.remaining_qty = round(float(bid.remaining_qty) - fill, 4)
                if bid.remaining_qty <= 0:
                    bid.remaining_qty = 0.0
                    bid.status = "FILLED"
                    bid.closed_at = now
                treasury.cash = round(float(treasury.cash) + amount, 2)
                remaining_offer = round(remaining_offer - fill, 4)
                sales[inventory.item_id] = round(sales.get(inventory.item_id, 0.0) + amount, 2)
                session.add(NatMarketTrade(
                    buy_order_id=bid.id,
                    sell_order_id=None,
                    buyer_company_id=buyer.id,
                    seller_company_id=company.id,
                    item_id=inventory.item_id,
                    price=float(bid.price),
                    quantity=fill,
                    total_amount=amount,
                    fee_amount=0.0,
                    executed_at=now,
                ))
                financials = await session.scalar(select(NatDailyFinancials).where(
                    NatDailyFinancials.company_id == buyer.id,
                    NatDailyFinancials.calendar_date == get_game_today(),
                ).with_for_update())
                if financials is None:
                    financials = NatDailyFinancials(
                        company_id=buyer.id,
                        calendar_date=get_game_today(),
                        gross_revenue=0.0,
                        opex=amount,
                        closed_profit=-amount,
                        developer_fee_paid=0.0,
                    )
                    session.add(financials)
                else:
                    financials.opex = round(float(financials.opex) + amount, 2)
                    financials.closed_profit = round(
                        float(financials.gross_revenue) - float(financials.opex), 2
                    )
            # Unsold confiscated stock disappears. The unseized 30% remains with the bankrupt.
            inventory.quantity = round(original_quantity * RETAINED_FRACTION, 4)
            inventory.reserved_quantity = 0.0
        return sales

    @staticmethod
    async def _return_bonds_to_market(
        session: AsyncSession, company: NatCompany, now: datetime,
    ) -> int:
        listings = (await session.execute(
            select(NatBondListing).where(
                NatBondListing.seller_company_id == company.id,
                NatBondListing.status == "OPEN",
            ).with_for_update()
        )).scalars().all()
        for listing in listings:
            listing.status = "CANCELLED"
            listing.closed_at = now
        holdings = (await session.execute(
            select(NatStateBondHolding).where(
                NatStateBondHolding.company_id == company.id,
                NatStateBondHolding.quantity > 0,
            ).with_for_update()
        )).scalars().all()
        returned = 0
        for holding in holdings:
            bond = await session.scalar(
                select(NatStateBond).where(NatStateBond.id == holding.bond_id).with_for_update()
            )
            quantity = max(0, int(holding.quantity))
            if bond and bond.is_active and (bond.maturity_at is None or bond.maturity_at > now):
                bond.remaining_volume += quantity
                bond.status = "OFFERING"
                returned += quantity
            holding.quantity = 0
            holding.reserved_quantity = 0
        pending = (await session.execute(
            select(NatBondSettlement).where(
                NatBondSettlement.company_id == company.id,
                NatBondSettlement.status == "PENDING",
            ).with_for_update()
        )).scalars().all()
        for settlement in pending:
            settlement.status = "CANCELLED"
        return returned

    @staticmethod
    async def _return_state_shares(session: AsyncSession, company: NatCompany) -> int:
        holdings = (await session.execute(
            select(NatStateShareHolding).where(
                NatStateShareHolding.company_id == company.id,
                NatStateShareHolding.quantity > 0,
            ).with_for_update()
        )).scalars().all()
        returned = 0
        for holding in holdings:
            issue = await session.scalar(
                select(NatStateShare).where(NatStateShare.id == holding.share_id).with_for_update()
            )
            if issue is not None:
                issue.remaining_volume += int(holding.quantity)
                issue.is_active = True
                returned += int(holding.quantity)
            holding.quantity = 0
            holding.invested_cash = 0.0
        return returned

    @classmethod
    async def execute(
        cls,
        session: AsyncSession,
        *,
        company_id: int,
        actor_id: int,
        operation_key: str,
        now: datetime | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        key = operation_key.strip()
        if not key or len(key) > 120:
            raise ValueError("A valid idempotency key is required.")
        operation_key = f"creator-bankruptcy:{key}"
        payload = {"company_id": int(company_id), "actor_id": int(actor_id)}
        replay = await StateShareService._replay(session, operation_key, "BANKRUPTCY", payload)
        if replay is not None:
            return replay

        treasury = await StateTreasuryService.get_or_create(
            session, commit=False, for_update=True,
        )
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
            .execution_options(populate_existing=True)
        )
        if company is None:
            raise ValueError("Company not found.")
        replay = await StateShareService._replay(session, operation_key, "BANKRUPTCY", payload)
        if replay is not None:
            return replay
        prior = await session.scalar(select(NatCreatorAuditLog.id).where(
            NatCreatorAuditLog.action == "CREATOR_BANKRUPTCY_LIQUIDATION",
            NatCreatorAuditLog.target_type == "company",
            NatCreatorAuditLog.target_id == str(company.id),
        ).limit(1))
        if prior:
            raise ValueError("Company has already had a creator bankruptcy liquidation.")

        current = now or get_game_now()
        await cls._cancel_commodity_orders(session, company)
        await cls._cancel_stock_orders(session, company)
        await session.flush()
        lots = await BankruptcyMarketService.list_confiscated_assets(
            session, company, operation_key,
        )
        inventory_sales = await cls._liquidate_inventory(session, company, treasury, current)
        state_shares_returned = await cls._return_state_shares(session, company)
        bonds_returned = await cls._return_bonds_to_market(session, company, current)
        cash_transferred = round(float(company.cash), 2)
        treasury.cash = round(float(treasury.cash) + cash_transferred, 2)
        company.cash = 0.0
        company.is_bankrupt = True
        company.updated_at = current

        result = {
            "success": True,
            "company_id": company.id,
            "company_name": company.name,
            "cash_transferred": cash_transferred,
            "stock_lots_created": sum(lot.asset_kind == "STOCK" for lot in lots),
            "state_shares_returned": state_shares_returned,
            "inventory_sales": inventory_sales,
            "bonds_returned": bonds_returned,
            "lots_created": len(lots),
            "market": "банкротства",
        }
        session.add(NatCreatorAuditLog(
            actor_id=actor_id,
            action="CREATOR_BANKRUPTCY_LIQUIDATION",
            target_type="company",
            target_id=str(company.id),
            details=(
                f"Компания {company.name} обанкрочена: в рынок банкротов выставлено {len(lots)} активов; "
                f"казна получила {cash_transferred:.2f} cash и {sum(inventory_sales.values()):.2f} cash за сырьё; "
                f"акции банкрота выставлены на продажу; "
                f"в рынок возвращено {bonds_returned} облигаций."
            ),
            created_at=current,
        ))
        await StateShareService._record_operation(
            session, operation_key, "BANKRUPTCY", payload, result,
        )
        if commit:
            await session.commit()
        else:
            await session.flush()
        asyncio.create_task(
            EventBroadcaster.broadcast_bankruptcy(
                company_name=company.name,
                ticker=company.ticker,
                reason="Принудительная ликвидация государством",
                details=(
                    f"В рынок банкротов выставлено {len(lots)} активов. "
                    f"В казну переведено {cash_transferred:.2f} ₽ наличных. "
                    f"Возвращено {bonds_returned} облигаций и {state_shares_returned} госакций."
                ),
            )
        )
        return result


__all__ = ["ForcedBankruptcyService"]
