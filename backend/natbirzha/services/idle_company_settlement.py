"""Company-level orchestration for lazy V2 settlement and tax enforcement."""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import get_business_spec
from backend.natbirzha.config import get_game_tz, normalize_dt
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.stocks import NatStock
from backend.natbirzha.services.business_asset_service import BusinessAssetService
from backend.natbirzha.services.business_income_ledger_service import BusinessIncomeLedgerService
from backend.natbirzha.services.progression_service import apply_xp
from backend.natbirzha.services.supply_policy_service import SupplyPolicyService
from backend.natbirzha.services.tax_service import TaxService
from backend.natbirzha.services.industry_upgrade_service import IndustryUpgradeService
from backend.natbirzha.services.dividend_service import DividendService


def _empty_result(company: NatCompany, cap_hours: int, projects: list, tax: dict) -> dict[str, Any]:
    return {
        "company_id": company.id,
        "gross_cash": 0.0,
        "maintenance_cash": 0.0,
        "net_cash": 0.0,
        "dividend_withheld_cash": 0.0,
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
) -> dict[str, Any]:
    """Settle every enterprise atomically and enforce overdue daily tax."""
    company = await session.scalar(
        select(NatCompany).where(NatCompany.id == company_id).with_for_update()
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
    for business in visible:
        metadata = dict(business.metadata_json or {})
        license_code = metadata.get("contract_license")
        if not license_code:
            continue
        from backend.natbirzha.services.premium_service import PremiumService

        license_active = await PremiumService.is_license_active(
            session, company.id, str(license_code), now=license_now
        )
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
    tax = await TaxService.summary(session, company.id, today=current.date())
    if tax["blocked"]:
        for business in visible:
            spec = get_business_spec(business.business_type)
            ready_at = normalize_dt(business.upgrade_ready_at)
            if spec and business.status == "UPGRADING" and ready_at and ready_at <= current:
                engine._finish_due_upgrade(business, spec)
            business.last_settled_at = current
        await session.flush()
        return _empty_result(company, cap_hours, completed_projects, tax)

    # When no tax row exists yet, a very long first offline settlement may not
    # silently earn past the first possible tax-block date. If that first window
    # produced no positive profit, a later request can continue normally.
    effective_current = current
    unpaid_date = tax.get("oldest_unpaid_date")
    if unpaid_date:
        deadline = TaxService.production_deadline(datetime.fromisoformat(unpaid_date).date())
        effective_current = min(effective_current, deadline)
    elif visible:
        oldest_cursor = min(
            (normalize_dt(b.last_settled_at) or current for b in visible), default=current
        )
        prospective = TaxService.production_deadline(oldest_cursor.date())
        if prospective < effective_current:
            effective_current = prospective

    gross = maintenance = settled_hours = skipped_hours = 0.0
    hourly_net_profit: dict[datetime, float] = defaultdict(float)
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
        industry_bonus = IndustryUpgradeService.bonus_multiplier(company, business.specialization)
        if spec["mechanic"] == "cash_income":
            result = engine._settle_business(
                business, now=effective_current, cap_hours=cap_hours,
                industry_bonus_multiplier=industry_bonus,
            )
        elif spec["mechanic"] == "resource_production":
            await SupplyPolicyService.auto_procure(session, company, business, spec)
            result = await engine._settle_resource_business(
                session, business, spec, now=effective_current, cap_hours=cap_hours,
                industry_bonus_multiplier=industry_bonus,
            )
        else:
            continue

        gross += result["gross"]
        maintenance += result["maintenance"]
        settled_hours = max(settled_hours, result["hours"])
        skipped_hours = max(skipped_hours, float(result.get("skipped_hours", 0.0)))
        worked_hours = float(result.get("worked_hours", 0.0))
        xp_gain += engine._accrue_work_xp(business, worked_hours)
        await BusinessAssetService.apply_vehicle_wear(session, business, worked_hours)
        await BusinessIncomeLedgerService.record_interval(
            session,
            business.id,
            work_started_at,
            worked_hours,
            gross=result["gross"],
            maintenance=result["maintenance"],
            resource_cost=float(result.get("resource_cost", 0.0)),
        )
        business_net = (
            float(result["gross"])
            - float(result["maintenance"])
            - float(result.get("resource_cost", 0.0))
        )
        for hour_start, profit in BusinessIncomeLedgerService.split_interval_by_hour(
            work_started_at,
            worked_hours,
            business_net,
            eligible_after=dividend_eligible_after,
        ).items():
            hourly_net_profit[hour_start] += profit
        if result["upgrade_completed"]:
            completed_upgrades.append(business.id)
            xp_gain += 50 + int(business.stage) * 10

    progression = apply_xp(company, xp_gain) if xp_gain > 0 else None
    dividend_withheld = await DividendService.accrue_hourly_profit(
        session, company, dict(hourly_net_profit), now=current
    )
    net_cash = round(gross - maintenance - dividend_withheld, 2)
    if net_cash:
        company.cash = round(float(company.cash) + net_cash, 2)
    tax = await TaxService.summary(session, company.id, today=current.date())
    if tax["blocked"] and effective_current < current:
        # The tax became overdue inside this offline window. Discard future
        # back-pay by advancing cursors from the statutory stop timestamp.
        for business in visible:
            business.last_settled_at = current
    await session.flush()
    return {
        "company_id": company.id,
        "gross_cash": round(gross, 2),
        "maintenance_cash": round(maintenance, 2),
        "net_cash": net_cash,
        "dividend_withheld_cash": round(dividend_withheld, 8),
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
