"""Safe starter-factory repair for companies created during the V2 rollout."""

from sqlalchemy import inspect, select

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.services.building_catalog import get_building_spec
from backend.natbirzha.services.company_constants import (
    SPECIALIZATION_ALIASES,
    STARTER_FACTORIES,
)


async def backfill_missing_starter_factories(connection) -> int:
    """Add one valid starter factory only to known companies with none."""
    has_required_tables = await connection.run_sync(
        lambda sync_connection: all(
            inspect(sync_connection).has_table(table)
            for table in ("nat_companies", "nat_factories")
        )
    )
    if not has_required_tables:
        return 0

    companies = (await connection.execute(
        select(NatCompany.id, NatCompany.specialization)
    )).all()
    existing_company_ids = set((await connection.execute(
        select(NatFactory.company_id).distinct()
    )).scalars())
    now = get_game_now()
    rows = []
    for company_id, raw_specialization in companies:
        if company_id in existing_company_ids:
            continue
        raw = str(raw_specialization or "").strip().lower()
        specialization = SPECIALIZATION_ALIASES.get(raw, raw)
        building_type = STARTER_FACTORIES.get(specialization)
        building = get_building_spec(building_type) if building_type else None
        if not building:
            continue
        rows.append({
            "company_id": company_id,
            "building_type": building_type,
            "specialization": specialization,
            "level": 1,
            "efficiency": 1.0,
            "is_active": True,
            "workers": int(building["workers_required"]),
            "automation_level": 0,
            "automation_enabled": False,
            "automation_status": "MANUAL",
            "technology_level": 0,
            "current_recipe": None,
            "cycle_started_at": None,
            "cycle_ready_at": None,
            "cycle_input_cost": 0.0,
            "last_produced_at": now,
            "created_at": now,
        })

    if rows:
        await connection.execute(NatFactory.__table__.insert(), rows)
    return len(rows)


__all__ = ["backfill_missing_starter_factories"]
