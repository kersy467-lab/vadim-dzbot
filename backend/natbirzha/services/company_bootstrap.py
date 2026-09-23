"""Creation-time NATBIRZHA company state for the active economy version."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import starter_business_spec
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.combat import NatArmyUnit
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.military import NatArmy
from backend.natbirzha.services.building_catalog import get_building_spec
from backend.natbirzha.services.company_constants import STARTER_FACTORIES, STARTER_INVENTORIES


async def bootstrap_company_state(
    session: AsyncSession,
    company: NatCompany,
    *,
    now,
) -> None:
    """Create starter production, supply and army without duplicating V1/V2 income."""
    starter_spec = starter_business_spec(company.specialization)
    if starter_spec is None:
        raise ValueError(f"No starter business configured for specialization: {company.specialization}")

    session.add(NatBusiness(
        company_id=company.id,
        business_type=starter_spec["id"],
        custom_name=starter_spec["name"],
        specialization=company.specialization,
        stage=1,
        status="ACTIVE",
        capital_invested=0.0,
        base_income_per_hour=float(starter_spec["base_income_per_hour"]),
        base_maintenance_per_hour=float(starter_spec["base_maintenance_per_hour"]),
        last_settled_at=now,
        slot_weight=int(starter_spec["slot_weight"]),
        metadata_json={"starter_grant": True, "sale_mode": "NPC"},
    ))

    # Keep the recipe-based factory layer available across V2 resets. V2
    # businesses do not replace the player's timed, inventory-backed factory.
    await _create_legacy_factory(session, company, now=now)

    await _create_starter_inventory(session, company, starter_spec)
    _create_starter_army(session, company, now=now)


async def _create_legacy_factory(session: AsyncSession, company: NatCompany, *, now) -> None:
    building_type = STARTER_FACTORIES.get(company.specialization)
    if not building_type:
        return
    building = get_building_spec(building_type) or {}
    session.add(NatFactory(
        company_id=company.id,
        building_type=building_type,
        specialization=company.specialization,
        level=1,
        efficiency=1.0,
        is_active=True,
        workers=int(building.get("workers_required", 10)),
        automation_level=0,
        technology_level=0,
        current_recipe=None,
        cycle_started_at=None,
        cycle_ready_at=None,
        last_produced_at=now,
        created_at=now,
    ))


async def _create_starter_inventory(
    session: AsyncSession,
    company: NatCompany,
    starter_spec: dict,
) -> None:
    starter_items = dict(STARTER_INVENTORIES.get(company.specialization, {}))
    for item_id, hourly_rate in starter_spec["inputs_per_hour"].items():
        starter_items[item_id] = max(
            float(starter_items.get(item_id, 0.0)),
            float(hourly_rate) * 4.0,
        )
    for item_id, quantity in starter_items.items():
        session.add(NatInventory(
            company_id=company.id,
            item_id=item_id,
            quantity=round(float(quantity), 6),
            reserved_quantity=0.0,
            avg_cost_basis=0.0,
        ))


def _create_starter_army(session: AsyncSession, company: NatCompany, *, now) -> None:
    session.add(NatArmy(
        company_id=company.id,
        infantry=10,
        tanks=0,
        drones=0,
        air_defense=0,
        army_strength=100,
        updated_at=now,
    ))
    session.add(NatArmyUnit(
        company_id=company.id,
        unit_type="infantry",
        quantity=10,
        level=1,
        readiness=10000,
        experience=0,
        updated_at=now,
    ))


__all__ = ["bootstrap_company_state"]
