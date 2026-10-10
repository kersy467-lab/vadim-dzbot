"""Opt-in early-factory upgrades, limited to one pass per minute and level 9."""
from datetime import timedelta
from sqlalchemy import select
from backend.natbirzha.models.next_game import NatNextGameFacility
from backend.natbirzha.services.next_game_community_service import profile


async def auto_upgrade_company(session, service, company, current):
    settings = await profile(session, company.id)
    if not settings.auto_upgrade:
        return
    if settings.last_auto_upgrade_at and current - settings.last_auto_upgrade_at < timedelta(minutes=1):
        return
    settings.last_auto_upgrade_at = current
    facilities = (await session.scalars(select(NatNextGameFacility).where(
        NatNextGameFacility.company_id == company.id, NatNextGameFacility.level < 9)
        .order_by(NatNextGameFacility.id))).all()
    for facility in facilities:
        if int(company.level) < facility.level + 1:
            continue
        from backend.natbirzha.services.next_game_service.common import facility_upgrade_cost
        if company.cash < facility_upgrade_cost(facility.level):
            continue
        await service.upgrade_facility(session, company.owner_tg_id, facility.branch_id)
