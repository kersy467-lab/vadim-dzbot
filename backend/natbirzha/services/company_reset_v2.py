"""Explicit cleanup for NATBIRZHA 2.0 company-owned rows during a user reset."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models import (
    NatArmyTraining,
    NatBusiness,
    NatBusinessEmployee,
    NatBusinessIncomeDaily,
    NatBusinessProject,
    NatBusinessSupplyPolicy,
    NatBusinessVehicle,
    NatCompanyEconomyState,
    NatMilitaryInfrastructure,
    NatTaxDaily,
    NatTaxPeriod,
    NatBusinessIncomePeriod,
)


async def delete_v2_company_state(session: AsyncSession, company_id: int) -> None:
    """Delete V2 rows without relying on DB-level cascade enforcement."""
    business_ids = select(NatBusiness.id).where(NatBusiness.company_id == company_id)

    await session.execute(
        delete(NatBusinessSupplyPolicy).where(NatBusinessSupplyPolicy.business_id.in_(business_ids))
    )
    await session.execute(
        delete(NatBusinessVehicle).where(NatBusinessVehicle.business_id.in_(business_ids))
    )
    await session.execute(
        delete(NatBusinessEmployee).where(NatBusinessEmployee.business_id.in_(business_ids))
    )
    await session.execute(
        delete(NatBusinessProject).where(NatBusinessProject.business_id.in_(business_ids))
    )
    await session.execute(
        delete(NatBusinessIncomeDaily).where(NatBusinessIncomeDaily.business_id.in_(business_ids))
    )
    await session.execute(
        delete(NatBusinessIncomePeriod).where(NatBusinessIncomePeriod.business_id.in_(business_ids))
    )
    await session.execute(delete(NatBusiness).where(NatBusiness.company_id == company_id))

    await session.execute(
        delete(NatCompanyEconomyState).where(NatCompanyEconomyState.company_id == company_id)
    )
    await session.execute(delete(NatTaxDaily).where(NatTaxDaily.company_id == company_id))
    await session.execute(delete(NatTaxPeriod).where(NatTaxPeriod.company_id == company_id))
    await session.execute(
        delete(NatMilitaryInfrastructure).where(NatMilitaryInfrastructure.company_id == company_id)
    )
    await session.execute(delete(NatArmyTraining).where(NatArmyTraining.company_id == company_id))


__all__ = ["delete_v2_company_state"]
