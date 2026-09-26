"""Cross-industry purchase and valuation for confiscated enterprise lots."""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.bankruptcy_market import NatBankruptcyMarketLot
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.creator import NatStateTreasury
from backend.natbirzha.models.stocks import NatStock, NatStockHolding
from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.services.building_catalog import get_building_spec
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


class BankruptcyMarketService:
    LOT_MODEL = NatBankruptcyMarketLot
    SEIZED_FRACTION = 0.70
    STATE_PREMIUM = 0.30

    @staticmethod
    def _seize_count(asset_count: int) -> int:
        if asset_count <= 0:
            return 0
        target = asset_count * BankruptcyMarketService.SEIZED_FRACTION
        return max(1, int(target + 0.5))

    @staticmethod
    def _factory_cost_basis(factory: NatFactory) -> float:
        spec = get_building_spec(factory.building_type) or {}
        basis = max(1.0, float(spec.get("build_cost", 10_000.0)))
        level = max(1, int(factory.level))
        basis += sum(8_000.0 * upgrade_level for upgrade_level in range(1, level))
        base_workers = int(spec.get("workers_required", 10))
        workers_level = max(0, (int(factory.workers) - base_workers) // 10)
        basis += sum(1_800.0 * upgrade_level * level for upgrade_level in range(1, workers_level + 1))
        basis += sum(3_500.0 * upgrade_level * level for upgrade_level in range(1, int(factory.automation_level) + 1))
        basis += sum(5_000.0 * upgrade_level * level for upgrade_level in range(1, int(factory.technology_level) + 1))
        return round(basis, 2)

    @staticmethod
    def _make_lot(
        *, operation_key: str, former_company: NatCompany, asset_kind: str,
        asset_id: int, asset_type: str, title: str, industry: str,
        level: int, cost_basis: float, quantity: float = 0.0,
        premium_rate: float = STATE_PREMIUM, ask_price: float | None = None,
    ) -> NatBankruptcyMarketLot:
        basis = round(max(1.0, float(cost_basis)), 2)
        return NatBankruptcyMarketLot(
            operation_key=operation_key,
            former_company_id=former_company.id,
            former_company_name=former_company.name,
            asset_kind=asset_kind,
            asset_id=asset_id,
            asset_type=asset_type,
            title=title[:180],
            industry=industry or "unknown",
            asset_level=max(1, int(level)),
            cost_basis=basis,
            ask_price=round(
                max(0.01, float(ask_price)) if ask_price is not None
                else basis * (1 + premium_rate), 2,
            ),
            quantity=max(0.0, float(quantity)),
            status="ACTIVE",
            created_at=get_game_now(),
        )

    @classmethod
    async def list_confiscated_assets(
        cls, session: AsyncSession, company: NatCompany, operation_key: str,
    ) -> list[NatBankruptcyMarketLot]:
        factories = list((await session.execute(
            select(NatFactory).where(NatFactory.company_id == company.id)
            .order_by(NatFactory.id.asc()).with_for_update()
        )).scalars().all())
        businesses = list((await session.execute(
            select(NatBusiness).where(
                NatBusiness.company_id == company.id, NatBusiness.status != "BANKRUPT",
            ).order_by(NatBusiness.id.asc()).with_for_update()
        )).scalars().all())
        businesses = [
            business for business in businesses
            if not (get_business_spec(business.business_type) or {}).get("legacy_hidden", False)
        ]
        factory_count = cls._seize_count(len(factories))
        business_count = cls._seize_count(len(businesses))
        selected_factories = sorted(
            factories, key=lambda row: (-cls._factory_cost_basis(row), row.id)
        )[:factory_count]
        selected_businesses = sorted(
            businesses, key=lambda row: (-max(1.0, float(row.capital_invested)), row.id)
        )[:business_count]
        lots: list[NatBankruptcyMarketLot] = []

        for factory in selected_factories:
            spec = get_building_spec(factory.building_type) or {}
            title = f"{spec.get('name', factory.building_type)} · уровень {factory.level}"
            factory.is_active = False
            if factory.cycle_started_at is not None or factory.cycle_ready_at is not None:
                factory.cycle_started_at = None
                factory.cycle_ready_at = None
                factory.cycle_input_cost = 0.0
                factory.cycle_output_multiplier = None
            lots.append(cls._make_lot(
                operation_key=f"{operation_key}:factory:{factory.id}",
                former_company=company, asset_kind="FACTORY", asset_id=factory.id,
                asset_type=factory.building_type, title=title,
                industry=factory.specialization, level=factory.level,
                cost_basis=cls._factory_cost_basis(factory),
            ))

        for business in selected_businesses:
            spec = get_business_spec(business.business_type) or {}
            title = f"{business.custom_name or spec.get('name', business.business_type)} · уровень {business.stage}"
            business.status = "BANKRUPT"
            business.upgrade_started_at = None
            business.upgrade_ready_at = None
            business.upgrade_target_stage = None
            lots.append(cls._make_lot(
                operation_key=f"{operation_key}:business:{business.id}",
                former_company=company, asset_kind="BUSINESS", asset_id=business.id,
                asset_type=business.business_type, title=title,
                industry=business.specialization or company.specialization,
                level=business.stage, cost_basis=business.capital_invested,
            ))

        stock_holdings = (await session.execute(
            select(NatStockHolding).where(
                NatStockHolding.holder_company_id == company.id,
                NatStockHolding.shares_count > 0,
            ).order_by(NatStockHolding.stock_id.asc()).with_for_update()
        )).scalars().all()
        for holding in stock_holdings:
            stock = await session.scalar(
                select(NatStock).where(NatStock.id == holding.stock_id).with_for_update()
            )
            if stock is None:
                holding.shares_count = 0
                continue
            issuer = await session.scalar(select(NatCompany).where(NatCompany.id == stock.company_id))
            quantity = max(0, int(holding.shares_count))
            stock_price = max(0.01, float(stock.current_price))
            title = f"Акции компании «{issuer.name if issuer else stock.company_id}» × {quantity:,}".replace(",", " ")
            lots.append(cls._make_lot(
                operation_key=f"{operation_key}:stock:{stock.id}:{holding.id}",
                former_company=company, asset_kind="STOCK", asset_id=stock.id,
                asset_type="company_stock", title=title,
                industry=issuer.specialization if issuer else "stocks", level=1,
                cost_basis=float(holding.avg_price) * quantity,
                quantity=quantity, premium_rate=0.0,
                ask_price=stock_price * quantity,
            ))
            holding.shares_count = 0
        session.add_all(lots)
        await session.flush()
        return lots

    @staticmethod
    async def get_active_lots(session: AsyncSession) -> list[dict[str, Any]]:
        rows = (await session.execute(
            select(NatBankruptcyMarketLot).where(NatBankruptcyMarketLot.status == "ACTIVE")
            .order_by(NatBankruptcyMarketLot.created_at.desc(), NatBankruptcyMarketLot.id.desc())
        )).scalars().all()
        return [{
            "id": row.id,
            "former_company_name": row.former_company_name,
            "asset_kind": row.asset_kind,
            "asset_type": row.asset_type,
            "title": row.title,
            "industry": row.industry,
            "level": row.asset_level,
            "quantity": row.quantity,
            "cost_basis": row.cost_basis,
            "ask_price": row.ask_price,
            "state_premium": round(row.ask_price - row.cost_basis, 2),
            "created_at": row.created_at.isoformat(),
        } for row in rows]

    @classmethod
    async def purchase_lot(
        cls, session: AsyncSession, *, company_id: int, lot_id: int,
        now: datetime | None = None, commit: bool = True,
    ) -> dict[str, Any]:
        treasury = await StateTreasuryService.get_or_create(
            session, commit=False, for_update=True,
        )
        lot = await session.scalar(
            select(NatBankruptcyMarketLot).where(
                NatBankruptcyMarketLot.id == lot_id,
                NatBankruptcyMarketLot.status == "ACTIVE",
            ).with_for_update()
        )
        if lot is None:
            raise ValueError("Завод больше не доступен на рынке банкротов")
        buyer = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if buyer is None or buyer.is_bankrupt:
            raise ValueError("Покупателем может быть только действующая компания")
        if buyer.id == lot.former_company_id:
            raise ValueError("Нельзя выкупить собственный завод из ликвидации")
        if float(buyer.cash) < float(lot.ask_price):
            raise ValueError(f"Недостаточно cash: нужно {lot.ask_price:.2f}")

        asset = await cls._load_asset(session, lot)
        if asset is None or (lot.asset_kind != "STOCK" and asset.company_id != lot.former_company_id):
            lot.status = "CANCELLED"
            if commit:
                await session.commit()
            else:
                await session.flush()
            return {
                "success": False,
                "reason": "stale_asset",
                "message": "Актив больше не принадлежит банкроту; лот снят с торгов.",
            }

        if lot.asset_kind == "BUSINESS":
            from backend.natbirzha.services.business_capacity_service import BusinessCapacityService
            from backend.natbirzha.services.business_service import BusinessService

            spec = get_business_spec(asset.business_type) or {}
            owned = await BusinessService._company_businesses(session, buyer.id)
            if spec.get("unique", True) and owned.get(asset.business_type):
                raise ValueError("Это предприятие уже есть у вашей компании")
            used = await BusinessService._used_slots(session, buyer.id)
            capacity = BusinessCapacityService.effective_capacity(buyer, now=now or get_game_now())
            if used + int(asset.slot_weight) > capacity:
                raise ValueError("Недостаточно корпоративной мощности для покупки предприятия")

        buyer.cash = round(float(buyer.cash) - float(lot.ask_price), 2)
        treasury.cash = round(float(treasury.cash) + float(lot.ask_price), 2)
        if lot.asset_kind == "STOCK":
            await cls._credit_stock_holding(session, buyer.id, lot.asset_id, int(lot.quantity), float(lot.ask_price))
        else:
            asset.company_id = buyer.id
        if lot.asset_kind == "BUSINESS":
            asset.last_settled_at = now or get_game_now()
            asset.status = "ACTIVE"
        elif lot.asset_kind == "FACTORY":
            asset.bankruptcy_acquired = True
            asset.is_active = True
            asset.last_produced_at = now or get_game_now()
        lot.status = "SOLD"
        lot.buyer_company_id = buyer.id
        lot.sold_at = now or get_game_now()
        result = {
            "success": True,
            "lot_id": lot.id,
            "title": lot.title,
            "asset_kind": lot.asset_kind,
            "asset_id": lot.asset_id,
            "paid": lot.ask_price,
            "state_premium": round(lot.ask_price - lot.cost_basis, 2),
            "cross_industry": lot.asset_kind != "STOCK" and buyer.specialization != lot.industry,
            "remaining_cash": buyer.cash,
        }
        if commit:
            await session.commit()
        else:
            await session.flush()
        return result

    @staticmethod
    async def _load_asset(session: AsyncSession, lot: NatBankruptcyMarketLot):
        model = {"FACTORY": NatFactory, "BUSINESS": NatBusiness, "STOCK": NatStock}.get(lot.asset_kind)
        if model is None:
            return None
        return await session.scalar(
            select(model).where(model.id == lot.asset_id).with_for_update()
        )

    @staticmethod
    async def _credit_stock_holding(
        session: AsyncSession, buyer_id: int, stock_id: int, quantity: int, total_cost: float,
    ) -> None:
        holding = await session.scalar(select(NatStockHolding).where(
            NatStockHolding.stock_id == stock_id,
            NatStockHolding.holder_company_id == buyer_id,
        ).with_for_update())
        unit_price = round(total_cost / max(1, quantity), 2)
        if holding is None:
            session.add(NatStockHolding(
                stock_id=stock_id, holder_company_id=buyer_id,
                shares_count=quantity, avg_price=unit_price,
            ))
            return
        combined = int(holding.shares_count) + quantity
        holding.avg_price = round(
            (int(holding.shares_count) * float(holding.avg_price) + total_cost) / max(1, combined), 2,
        )
        holding.shares_count = combined


__all__ = ["BankruptcyMarketService"]
