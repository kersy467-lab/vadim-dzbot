"""Authenticated API for industry hybrid formation and sale."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.catalogs.businesses import HYBRID_RECIPES, get_business_spec
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.business import NatBusiness
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.hybrid_mergers import NatHybridMerger
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, NatInventory
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.hybrid_merger_service import HybridMergerService
from backend.natbirzha.services.idempotency_service import IdempotencyService


router = APIRouter(prefix="/businesses/hybrids", tags=["Natbirzha Business Hybrids"])


class OpenHybridRequest(BaseModel):
    recipe_id: str = Field(min_length=2, max_length=64)
    source_business_a_id: int = Field(gt=0)
    source_business_b_id: int = Field(gt=0)


def _require_tycoon_v2() -> None:
    if not nat_settings.TYCOON_V2_ENABLED:
        raise HTTPException(status_code=409, detail="НАТБИРЖА 2.0 пока отключена.")


@router.get("")
async def hybrid_catalog(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_tycoon_v2()
    businesses = (await session.execute(
        select(NatBusiness)
        .where(NatBusiness.company_id == company.id)
        .order_by(NatBusiness.id)
    )).scalars().all()
    inventories = (await session.execute(
        select(NatInventory).where(NatInventory.company_id == company.id)
    )).scalars().all()
    active_hybrids = (await session.execute(
        select(NatHybridMerger)
        .where(NatHybridMerger.company_id == company.id, NatHybridMerger.status == "ACTIVE")
        .order_by(NatHybridMerger.created_at, NatHybridMerger.id)
    )).scalars().all()
    active_global = int(await session.scalar(
        select(func.count(NatHybridMerger.id)).where(NatHybridMerger.status == "ACTIVE")
    ) or 0)

    business_by_id = {row.id: row for row in businesses}
    business_rows = []
    for row in businesses:
        spec = get_business_spec(row.business_type)
        if not spec or spec.get("hybrid_only"):
            continue
        business_rows.append({
            "id": row.id,
            "business_type": row.business_type,
            "name": row.custom_name or spec["name"],
            "stage": int(row.stage),
            "status": str(row.status),
            "slot_weight": int(row.slot_weight),
        })

    recipe_rows = []
    for recipe in HYBRID_RECIPES.values():
        if recipe["specialization"] != company.specialization:
            continue
        source_types = tuple(recipe["source_business_types"])
        source_specs = [get_business_spec(business_type) or {} for business_type in source_types]
        source_options = []
        for business_type in source_types:
            source_options.append({
                "business_type": business_type,
                "name": (get_business_spec(business_type) or {}).get("name", business_type),
                "businesses": [row for row in business_rows if row["business_type"] == business_type],
            })
        business_spec = get_business_spec(recipe["business_type"]) or {}
        recipe_rows.append({
            **recipe,
            "name": business_spec.get("name", recipe["id"]),
            "description": business_spec.get("description", ""),
            "additional_capital_cost": float(recipe["additional_capital_cost"]),
            "source_options": source_options,
            "source_names": [spec.get("name", "Предприятие") for spec in source_specs],
        })

    active_rows = []
    for merger in active_hybrids:
        hybrid = business_by_id.get(merger.hybrid_business_id)
        hybrid_spec = get_business_spec(hybrid.business_type) if hybrid is not None else None
        active_rows.append({
            "id": merger.id,
            "recipe_id": merger.recipe_id,
            "name": (hybrid_spec or {}).get("name", "Гибридный комплекс"),
            "hybrid_business_id": merger.hybrid_business_id,
            "stage": int(hybrid.stage) if hybrid is not None else None,
            "status": hybrid.status if hybrid is not None else "MISSING",
            "source_business_ids": [merger.source_business_a_id, merger.source_business_b_id],
            "source_business_names": [
                (business_by_id.get(source_id).custom_name
                 if business_by_id.get(source_id) is not None else None)
                or (get_business_spec(business_by_id[source_id].business_type) or {}).get("name", "Предприятие")
                if source_id in business_by_id else "Предприятие"
                for source_id in (merger.source_business_a_id, merger.source_business_b_id)
            ],
            "additional_capital_invested": float(merger.additional_capital_invested),
            "created_at": merger.created_at.isoformat() if merger.created_at else None,
        })

    inventory = {
        row.item_id: round(float(row.available_quantity), 6)
        for row in inventories
    }
    resource_names = {
        item_id: CANONICAL_ITEMS.get(item_id, {}).get("name", item_id)
        for recipe in recipe_rows
        for item_id in recipe["resource_requirements"]
    }
    return {
        "specialization": company.specialization,
        "company_cash": round(float(company.cash), 2),
        "active_hybrids": active_global,
        "active_hybrid_limit": 4,
        "global_slots_available": max(0, 4 - active_global),
        "company_hybrids": active_rows,
        "businesses": business_rows,
        "recipes": recipe_rows,
        "inventory": inventory,
        "resource_names": resource_names,
    }


@router.post("/open")
async def open_hybrid(
    request: OpenHybridRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_tycoon_v2()
    endpoint = f"/api/natbirzha/businesses/hybrids/open/company/{company.id}"
    payload = {
        "recipe_id": request.recipe_id,
        "source_business_a_id": request.source_business_a_id,
        "source_business_b_id": request.source_business_b_id,
    }
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Нужен ключ идемпотентности")
    try:
        response = await HybridMergerService.open_hybrid(
            session,
            company.id,
            request.recipe_id,
            request.source_business_a_id,
            request.source_business_b_id,
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, response
    )


@router.post("/{hybrid_id}/sell")
async def sell_hybrid(
    hybrid_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    _require_tycoon_v2()
    endpoint = f"/api/natbirzha/businesses/hybrids/{hybrid_id}/sell/company/{company.id}"
    payload = {"hybrid_id": int(hybrid_id)}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Нужен ключ идемпотентности")
    try:
        response = await HybridMergerService.sell_hybrid(session, company.id, hybrid_id)
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, response
    )


__all__ = ["router"]
