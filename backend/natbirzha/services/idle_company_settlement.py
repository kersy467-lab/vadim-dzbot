"""Company-level orchestration for lazy V2 settlement and tax enforcement."""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_tz, normalize_dt
from backend.natbirzha.models.business import (
    NatBusiness, NatBusinessIncomeDaily, NatBusinessIncomePeriod,
)
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.premium import NatPremiumLicense
from backend.natbirzha.models.business_assets import NatBusinessSupplyPolicy
from backend.natbirzha.models.stocks import NatStock
from backend.natbirzha.models.tax import NatCompanyProfitPeriod
from backend.natbirzha.services.business_asset_service import BusinessAssetService
from backend.natbirzha.services.business_income_ledger_service import BusinessIncomeLedgerService
from backend.natbirzha.services.company_profit_ledger_service import CompanyProfitLedgerService
from backend.natbirzha.services.progression_service import apply_xp
from backend.natbirzha.services.supply_policy_service import SupplyPolicyService
from backend.natbirzha.services.inventory_capacity_service import InventoryCapacityService
from backend.natbirzha.services.tax_service import TaxService
from backend.natbirzha.services.industry_upgrade_service import IndustryUpgradeService
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.sabotage_service import SabotageService
from backend.natbirzha.tax_rules import get_period_bounds, period_production_deadline


def _empty_result(company: NatCompany, cap_hours: int, projects: list, tax: dict) -> dict[str, Any]:
    return {
        "company_id": company.id,
        "gross_cash": 0.0,
        "maintenance_cash": 0.0,
        "net_cash": 0.0,
        "dividend_withheld_cash": 0.0,
        "profit_share_paid_cash": 0.0,
        "settled_hours": 0.0,
        "offline_cap_hours": cap_hours,
        "skipped_offline_hours": 0.0,
        "completed_upgrades": [],
        "completed_projects": projects,
        "xp_gained": 0,
        "progression": None,
        "tax": tax,
        "tax_blocked": bool(tax.get("blocked")),
    }


async def settle_company(
    engine: Type,
    session: AsyncSession,
    company_id: int,
    *,
    current: datetime,
    process_deals: bool = True,
) -> dict[str, Any]:
    """Settle every enterprise atomically and enforce overdue daily tax."""
    from backend.natbirzha.services.supply_deal_service import SupplyDealService

    supplier_ids: list[int] = []
    if process_deals:
        supplier_ids = await SupplyDealService.partners_to_settle(session, company_id, now=current)
        from backend.natbirzha.services.joint_factory_settlement_service import (
            JointFactorySettlementService,
        )

        joint_participant_ids = await JointFactorySettlementService.participants_to_settle(
            session, company_id
        )
        participant_ids = sorted({int(company_id), *supplier_ids, *joint_participant_ids})
        # Lock all counterparties in one stable order before settling either
        # supply contracts or a shared factory, avoiding reciprocal lock cycles.
        await session.execute(
            select(NatCompany.id).where(NatCompany.id.in_(participant_ids))
            .order_by(NatCompany.id).with_for_update()
        )
        await JointFactorySettlementService.settle_for_company(
            session, company_id, now=current
        )
        for supplier_id in supplier_ids:
            await settle_company(engine, session, supplier_id, current=current, process_deals=False)

    company = await session.scalar(
        select(NatCompany).where(NatCompany.id == company_id)
        .with_for_update().execution_options(populate_existing=True)
    )
    if company is None:
        raise ValueError("Компания не найдена")

    completed_projects = await BusinessAssetService.settle_due_projects(session, company, now=current)
    businesses = list((await session.execute(
        select(NatBusiness)
        .where(NatBusiness.company_id == company.id)
        .order_by(NatBusiness.id)
        .with_for_update()
    )).scalars().all())
    visible = [
        business for business in businesses
        if not (get_business_spec(business.business_type) or {}).get("legacy_hidden")
    ]
    # PVC licenses are stored in UTC; settlement timestamps use the configured
    # game timezone. Compare the same instant and freeze leased businesses
    # without production back-pay when their contract expires.
    license_now = current.replace(tzinfo=get_game_tz()).astimezone(timezone.utc).replace(tzinfo=None)
    expired_contract_ids: set[int] = set()
    license_codes = {
        str((business.metadata_json or {}).get("contract_license"))
        for business in visible
        if (business.metadata_json or {}).get("contract_license")
    }
    active_license_codes = set()
    if license_codes:
        active_license_codes = set((await session.scalars(
            select(NatPremiumLicense.license_code).where(
                NatPremiumLicense.company_id == company.id,
                NatPremiumLicense.license_code.in_(license_codes),
                NatPremiumLicense.status == "ACTIVE",
                NatPremiumLicense.starts_at <= license_now,
                NatPremiumLicense.expires_at > license_now,
            )
        )).all())
    for business in visible:
        metadata = dict(business.metadata_json or {})
        license_code = metadata.get("contract_license")
        if not license_code:
            continue
        license_active = str(license_code) in active_license_codes
        spec = get_business_spec(business.business_type)
        ready_at = normalize_dt(business.upgrade_ready_at)
        if license_active:
            if metadata.pop("contract_expired", None):
                resume_status = metadata.pop("contract_resume_status", "ACTIVE")
                business.metadata_json = metadata
                if business.status == "PAUSED_MANUAL":
                    business.status = resume_status if resume_status in {
                        "ACTIVE", "PAUSED_MANUAL", "PAUSED_SUPPLY",
                        "PAUSED_MAINTENANCE", "PAUSED_STORAGE",
                    } else "ACTIVE"
            continue
        if not metadata.get("contract_expired"):
            metadata["contract_resume_status"] = (
                metadata.get("upgrade_resume_status", "ACTIVE")
                if business.status == "UPGRADING"
                else business.status
            )
        metadata["contract_expired"] = True
        business.metadata_json = metadata
        if spec and business.status == "UPGRADING" and ready_at and ready_at <= current:
            engine._finish_due_upgrade(business, spec)
        if business.status != "UPGRADING":
            business.status = "PAUSED_MANUAL"
        business.last_settled_at = current
        expired_contract_ids.add(business.id)

    cap_hours = engine.offline_cap_hours(company)
    storage_capacity_by_item = InventoryCapacityService.capacity_by_item(company, businesses)
    tax = await TaxService.summary(session, company.id, now=current)
    # Always settle only through the first unpaid tax deadline. If a company
    # returns after that deadline, the already-earned portion before the stop
    # time still counts; the final cursor advance below discards later hours.
    # This also covers the first offline window, before its income has created a
    # tax row: it cannot silently earn past its first possible tax-block date.
    effective_current = current
    unpaid_date = tax.get("oldest_unpaid_date")
    if unpaid_date:
        deadline = TaxService.production_deadline(datetime.fromisoformat(unpaid_date))
        effective_current = min(effective_current, deadline)
    elif visible:
        oldest_cursor = min(
            (normalize_dt(b.last_settled_at) or current for b in visible), default=current
        )
        _, current_period_end = get_period_bounds(oldest_cursor)
        prospective = period_production_deadline(current_period_end)
        if prospective < effective_current:
            effective_current = prospective

    deal_window_start = min(
        (normalize_dt(b.last_settled_at) or effective_current for b in visible),
        default=effective_current,
    )
    deal_window_start = max(
        deal_window_start,
        effective_current - timedelta(hours=max(1, int(cap_hours))),
    )
    active_deals = await SupplyDealService.active_for_buyer(
        session, company.id, start=deal_window_start, end=effective_current
    ) if process_deals else []

    resource_business_specs = {
        business.id: spec
        for business in businesses
        if (spec := get_business_spec(business.business_type))
        and spec.get("mechanic") == "resource_production"
        and business.id not in expired_contract_ids
    }
    inventory_item_ids = {
        item_id
        for spec in resource_business_specs.values()
        for item_id in (*spec.get("inputs_per_hour", {}), *spec.get("outputs_per_hour", {}))
    }
    inventory_cache: dict[str, NatInventory | None] = {}
    if inventory_item_ids:
        inventory_rows = (await session.execute(
            select(NatInventory)
            .where(
                NatInventory.company_id == company.id,
                NatInventory.item_id.in_(inventory_item_ids),
            )
            .order_by(NatInventory.item_id)
            .with_for_update()
        )).scalars().all()
        inventory_cache.update({item_id: None for item_id in inventory_item_ids})
        inventory_cache.update({row.item_id: row for row in inventory_rows})

    policies_by_business: dict[int, list[NatBusinessSupplyPolicy]] = defaultdict(list)
    resource_business_ids = list(resource_business_specs)
    if resource_business_ids:
        policies = (await session.execute(
            select(NatBusinessSupplyPolicy)
            .where(
                NatBusinessSupplyPolicy.business_id.in_(resource_business_ids),
                NatBusinessSupplyPolicy.mode != "MANUAL",
            )
            .order_by(NatBusinessSupplyPolicy.business_id, NatBusinessSupplyPolicy.item_id)
            .with_for_update()
        )).scalars().all()
        for policy in policies:
            policies_by_business[policy.business_id].append(policy)

    daily_ledger_keys: set[tuple[int, date]] = set()
    business_period_keys: set[tuple[int, datetime]] = set()
    for business in businesses:
        if business.id in expired_contract_ids:
            continue
        spec = get_business_spec(business.business_type)
        if not spec or spec.get("legacy_hidden") or spec.get("mechanic") not in {
            "cash_income", "resource_production"
        }:
            continue
        start = normalize_dt(business.last_settled_at) or effective_current
        end = min(
            effective_current,
            start + timedelta(hours=max(1, int(cap_hours))),
        )
        daily_cursor = start
        while daily_cursor < end:
            daily_ledger_keys.add((business.id, daily_cursor.date()))
            next_day = datetime.combine(daily_cursor.date() + timedelta(days=1), datetime.min.time())
            daily_cursor = min(end, next_day)
        period_cursor = start
        while period_cursor < end:
            period_start, period_end = get_period_bounds(period_cursor)
            business_period_keys.add((business.id, period_start))
            period_cursor = min(end, period_end)

    daily_ledger_cache: dict[tuple[int, date], NatBusinessIncomeDaily | None] = {
        key: None for key in daily_ledger_keys
    }
    if daily_ledger_keys:
        daily_rows = (await session.execute(
            select(NatBusinessIncomeDaily)
            .where(
                NatBusinessIncomeDaily.business_id.in_({key[0] for key in daily_ledger_keys}),
                NatBusinessIncomeDaily.date.in_({key[1] for key in daily_ledger_keys}),
            )
            .order_by(NatBusinessIncomeDaily.business_id, NatBusinessIncomeDaily.date)
            .with_for_update()
        )).scalars().all()
        daily_ledger_cache.update({
            (row.business_id, row.date): row for row in daily_rows
        })

    business_period_cache: dict[tuple[int, datetime], NatBusinessIncomePeriod | None] = {
        key: None for key in business_period_keys
    }
    if business_period_keys:
        period_rows = (await session.execute(
            select(NatBusinessIncomePeriod)
            .where(
                NatBusinessIncomePeriod.business_id.in_({key[0] for key in business_period_keys}),
                NatBusinessIncomePeriod.period_start.in_({key[1] for key in business_period_keys}),
            )
            .order_by(
                NatBusinessIncomePeriod.business_id,
                NatBusinessIncomePeriod.period_start,
            )
            .with_for_update()
        )).scalars().all()
        business_period_cache.update({
            (row.business_id, row.period_start): row for row in period_rows
        })

    company_profit_period_cache: dict[tuple[int, datetime], NatCompanyProfitPeriod | None] = {}

    gross = gross_cash = gross_value = maintenance = settled_hours = skipped_hours = 0.0
    hourly_cash_income: dict[datetime, float] = defaultdict(float)
    profit_slices: list[dict[str, Any]] = []
    listed_stock = await session.scalar(
        select(NatStock).where(NatStock.company_id == company.id, NatStock.is_listed == True)
    )
    dividend_eligible_after = None
    if listed_stock is not None:
        dividend_eligible_after = (
            normalize_dt(listed_stock.dividend_eligible_from)
            or normalize_dt(listed_stock.ipo_date)
            or normalize_dt(listed_stock.created_at)
        )
    completed_upgrades: list[int] = []
    xp_gain = 0
    for business in businesses:
        if business.id in expired_contract_ids:
            continue
        spec = get_business_spec(business.business_type)
        if not spec:
            continue
        if spec.get("legacy_hidden"):
            # Hidden legacy rows are inert compatibility state. Never move their
            # settlement cursor backwards if a client sends an older timestamp.
            previous = normalize_dt(business.last_settled_at)
            if previous is None or current > previous:
                business.last_settled_at = current
            continue
        work_started_at = normalize_dt(business.last_settled_at) or effective_current
        max_end = work_started_at + timedelta(hours=max(1, int(cap_hours)))
        planned_end = min(effective_current, max_end)
        business_skipped_hours = max(0.0, (effective_current - planned_end).total_seconds() / 3600)
        business_hours = 0.0
        business_gross = business_maintenance = business_resource_cost = 0.0
        industry_bonus = IndustryUpgradeService.bonus_multiplier(company, business.specialization)
        sabotage_income_mult = SabotageService.get_income_multiplier(business.specialization or company.specialization)
        industry_bonus = round(industry_bonus * sabotage_income_mult, 4)
        if spec["mechanic"] not in {"cash_income", "resource_production"}:
            continue
        if planned_end > work_started_at:
            boundaries = {work_started_at, planned_end}
            for deal in active_deals:
                deal_start, deal_end = normalize_dt(deal.starts_at), normalize_dt(deal.expires_at)
                if deal_start and work_started_at < deal_start < planned_end:
                    boundaries.add(deal_start)
                if deal_end and work_started_at < deal_end < planned_end:
                    boundaries.add(deal_end)
            points = sorted(boundaries)
            for segment_start, segment_end in zip(points, points[1:]):
                if segment_end <= segment_start:
                    continue
                if spec["mechanic"] == "resource_production":
                    if process_deals:
                        await SupplyDealService.fulfill_resource_interval(
                            session, company, business, spec,
                            start=segment_start, end=segment_end, now=current,
                            deals=active_deals, inventory_cache=inventory_cache,
                        )
                    # Contract stock is offered first; the established market/NPC
                    # policy remains the fallback for any unmet input requirement.
                    await SupplyPolicyService.auto_procure(
                        session, company, business, spec,
                        policies=policies_by_business.get(business.id, []),
                        inventory_cache=inventory_cache,
                    )
                    result = await engine._settle_resource_business(
                        session, business, spec, now=segment_end, cap_hours=cap_hours,
                        industry_bonus_multiplier=industry_bonus,
                        storage_capacity_by_item=storage_capacity_by_item,
                        inventory_cache=inventory_cache,
                    )
                else:
                    result = engine._settle_business(
                        business, now=segment_end, cap_hours=cap_hours,
                        industry_bonus_multiplier=industry_bonus,
                    )

                segment_worked = max(0.0, float(result.get("worked_hours", 0.0)))
                segment_end_worked = segment_start + timedelta(hours=segment_worked)
                biz_gross_cash = float(result.get("gross_cash", result["gross"]))
                segment_gross = float(result["gross"])
                segment_maintenance = float(result["maintenance"])
                segment_resource_cost = float(result.get("resource_cost", 0.0))
                business_gross += segment_gross
                business_maintenance += segment_maintenance
                business_resource_cost += segment_resource_cost
                business_hours += float(result.get("hours", 0.0))
                gross += segment_gross
                gross_cash += biz_gross_cash
                gross_value += segment_gross
                maintenance += segment_maintenance
                # Each sub-interval is intentionally shorter than the engine's
                # offline cap, so report the company-level amount skipped by
                # the original cursor-to-current window.
                skipped_hours = max(skipped_hours, business_skipped_hours)
                xp_gain += engine._accrue_work_xp(business, segment_worked)
                await BusinessAssetService.apply_vehicle_wear(session, business, segment_worked)
                await BusinessIncomeLedgerService.record_interval(
                    session, business.id, segment_start, segment_worked,
                    gross=segment_gross,
                    maintenance=segment_maintenance,
                    resource_cost=segment_resource_cost,
                    daily_row_cache=daily_ledger_cache,
                    period_row_cache=business_period_cache,
                    flush=False,
                )
                # Cash businesses realize their income as it is earned. Legacy
                # NPC-sale resource businesses do too; HOLD production remains
                # inventory and capitalizes these costs until an actual sale.
                if spec["mechanic"] == "cash_income" or biz_gross_cash > 0:
                    await CompanyProfitLedgerService.record_interval(
                        session,
                        company.id,
                        segment_start,
                        segment_worked,
                        revenue=biz_gross_cash,
                        cost_of_goods_sold=segment_resource_cost,
                        maintenance=segment_maintenance,
                        row_cache=company_profit_period_cache,
                        flush=False,
                    )
                for hour_start, cash_income in BusinessIncomeLedgerService.split_interval_by_hour(
                    segment_start, segment_worked, biz_gross_cash,
                    eligible_after=dividend_eligible_after,
                ).items():
                    hourly_cash_income[hour_start] += cash_income
                if segment_worked > 1e-9:
                    profit_slices.append({
                        "business_id": business.id,
                        "start": segment_start,
                        "end": segment_end_worked,
                        "net_profit": biz_gross_cash - segment_maintenance - segment_resource_cost,
                    })
                if result.get("upgrade_completed"):
                    completed_upgrades.append(business.id)
                    xp_gain += 50 + int(business.stage) * 10
        if business_skipped_hours > 0:
            # Keep the existing offline cap semantics: skipped time is never
            # back-paid on a later request.
            business.last_settled_at = effective_current
        settled_hours = max(settled_hours, business_hours)

    progression = apply_xp(company, xp_gain) if xp_gain > 0 else None
    dividend_withheld = await DividendService.accrue_hourly_income(
        session, company, dict(hourly_cash_income), now=current
    )
    cash_room_for_shares = max(
        0.0,
        float(company.cash) + gross_cash - maintenance - dividend_withheld,
    )
    profit_share_paid = await SupplyDealService.settle_profit_share(
        session, company, profit_slices,
        cash_available=cash_room_for_shares,
        now=current,
    ) if process_deals else 0.0
    net_cash = round(gross_cash - maintenance - dividend_withheld - profit_share_paid, 2)
    if net_cash:
        company.cash = round(float(company.cash) + net_cash, 2)
    if process_deals:
        await SupplyDealService.advance_buyer_cursor(
            session, company.id, through=effective_current
        )
    tax = await TaxService.summary(session, company.id, now=current)
    await SupplyDealService.settle_expired(session, company.id, now=current)
    if tax["blocked"] and effective_current < current:
        # The tax became overdue inside this offline window. Discard future
        # back-pay by advancing cursors from the statutory stop timestamp.
        for business in visible:
            business.last_settled_at = current
    await session.flush()
    return {
        "company_id": company.id,
        "gross_cash": round(gross_cash, 2),
        "gross_value": round(gross_value, 2),
        "maintenance_cash": round(maintenance, 2),
        "net_cash": net_cash,
        "dividend_withheld_cash": round(dividend_withheld, 8),
        "profit_share_paid_cash": round(profit_share_paid, 6),
        "settled_hours": round(settled_hours, 4),
        "offline_cap_hours": cap_hours,
        "skipped_offline_hours": round(skipped_hours, 4),
        "completed_upgrades": completed_upgrades,
        "completed_projects": completed_projects,
        "xp_gained": xp_gain,
        "progression": progression,
        "tax": tax,
        "tax_blocked": bool(tax.get("blocked")),
    }


__all__ = ["settle_company"]
