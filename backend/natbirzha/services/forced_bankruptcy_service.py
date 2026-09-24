"""Creator-triggered company liquidation represented by a government share issue."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.creator import NatCreatorAuditLog
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.market import NatMarketOrder
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services.market_service import MarketService
from backend.natbirzha.services.state_share_service import StateShareService
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


SEIZED_ASSET_FRACTION = 0.70
REMAINING_ASSET_FRACTION = 1 - SEIZED_ASSET_FRACTION
LIQUIDATION_SHARE_VOLUME = 10_000


class ForcedBankruptcyService:
    @staticmethod
    async def _cancel_orders(session: AsyncSession, company: NatCompany) -> None:
        orders = (await session.execute(
            select(NatMarketOrder)
            .where(
                NatMarketOrder.company_id == company.id,
                NatMarketOrder.status == "ACTIVE",
            )
            .order_by(NatMarketOrder.id.asc())
            .with_for_update()
        )).scalars().all()
        for order in orders:
            await MarketService.cancel_order(session, company, order.id, commit=False)

    @staticmethod
    async def _reduce_assets(session: AsyncSession, company: NatCompany) -> None:
        company.cash = round(max(0.0, float(company.cash)) * REMAINING_ASSET_FRACTION, 2)
        company.territory_tiles = math.floor(
            max(0, int(company.territory_tiles)) * REMAINING_ASSET_FRACTION
        )

        factories = (await session.execute(
            select(NatFactory)
            .where(NatFactory.company_id == company.id)
            .order_by(NatFactory.id.asc())
            .with_for_update()
        )).scalars().all()
        level_total = sum(max(0, int(factory.level)) for factory in factories)
        levels_to_keep = math.floor(level_total * REMAINING_ASSET_FRACTION)
        for factory in factories:
            retained = min(max(0, int(factory.level)), levels_to_keep)
            levels_to_keep -= retained
            if retained == 0:
                await session.delete(factory)
            else:
                factory.level = retained

        businesses = (await session.execute(
            select(NatBusiness)
            .where(
                NatBusiness.company_id == company.id,
                NatBusiness.status != "BANKRUPT",
            )
            .with_for_update()
        )).scalars().all()
        from backend.natbirzha.catalogs.businesses import get_business_spec
        for business in businesses:
            spec = get_business_spec(business.business_type)
            if not spec or spec.get("legacy_hidden"):
                continue
            business.capital_invested = round(
                max(0.0, float(business.capital_invested)) * REMAINING_ASSET_FRACTION, 2
            )

        inventory = (await session.execute(
            select(NatInventory)
            .where(NatInventory.company_id == company.id)
            .with_for_update()
        )).scalars().all()
        for item in inventory:
            item.quantity = max(0.0, float(item.quantity)) * REMAINING_ASSET_FRACTION
            item.reserved_quantity = 0.0

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
        if not key or len(key) > 150:
            raise ValueError("A valid idempotency key is required.")
        operation_key = f"creator-bankruptcy:{key}"
        payload = {"company_id": int(company_id), "actor_id": int(actor_id)}
        replay = await StateShareService._replay(
            session, operation_key, "BANKRUPTCY", payload
        )
        if replay is not None:
            return replay

        await StateTreasuryService.get_or_create(session, commit=False, for_update=True)
        company = await session.scalar(
            select(NatCompany)
            .where(NatCompany.id == company_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if company is None:
            raise ValueError("Company not found.")
        replay = await StateShareService._replay(
            session, operation_key, "BANKRUPTCY", payload
        )
        if replay is not None:
            return replay
        previously_liquidated = await session.scalar(select(NatCreatorAuditLog.id).where(
            NatCreatorAuditLog.action == "CREATOR_BANKRUPTCY_LIQUIDATION",
            NatCreatorAuditLog.target_type == "company",
            NatCreatorAuditLog.target_id == str(company.id),
        ).limit(1))
        if previously_liquidated:
            raise ValueError("Company has already had a creator bankruptcy liquidation.")

        await cls._cancel_orders(session, company)
        await session.flush()
        nav_before = await CompanyService.calculate_audited_nav(session, company)
        if nav_before <= 0:
            raise ValueError("Company has no audited assets to liquidate.")
        await cls._reduce_assets(session, company)
        company.updated_at = now or get_game_now()
        await session.flush()
        nav_after = await CompanyService.calculate_audited_nav(session, company)
        seized_value = round(max(0.0, nav_before - nav_after), 2)
        issue_price = round(seized_value / LIQUIDATION_SHARE_VOLUME, 2)
        if issue_price <= 0:
            raise ValueError("Liquidated assets are too small to create a share issue.")

        company_name = company.name
        issue = await StateShareService.issue(
            session,
            actor_id=actor_id,
            title=f'Распродажа компании "{company_name}"',
            purpose=f"Государственная распродажа 70% активов компании {company_name}",
            volume=LIQUIDATION_SHARE_VOLUME,
            issue_price=issue_price,
            projected_annual_profit=0,
            dividend_rate_pct=0,
            operation_key=f"{operation_key}:shares",
            commit=False,
            now=company.updated_at,
        )
        result = {
            "success": True,
            "company_id": company.id,
            "company_name": company_name,
            "nav_before": nav_before,
            "nav_after": nav_after,
            "seized_value": seized_value,
            "share_id": issue["share_id"],
            "share_title": issue["title"],
            "share_volume": issue["total_volume"],
            "issue_price": issue["issue_price"],
            "represented_value": round(issue["issue_price"] * issue["total_volume"], 2),
        }
        session.add(NatCreatorAuditLog(
            actor_id=actor_id,
            action="CREATOR_BANKRUPTCY_LIQUIDATION",
            target_type="company",
            target_id=str(company.id),
            details=(
                f"Компания {company_name}: изъято активов на {seized_value} cash; "
                f"выпущено {LIQUIDATION_SHARE_VOLUME} гос.акций по {issue_price} cash."
            ),
            created_at=company.updated_at,
        ))
        await StateShareService._record_operation(
            session, operation_key, "BANKRUPTCY", payload, result
        )
        if commit:
            await session.commit()
        else:
            await session.flush()
        return result


__all__ = ["ForcedBankruptcyService"]
