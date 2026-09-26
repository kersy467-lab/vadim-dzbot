"""Authenticated endpoints for bilateral joint-factory projects."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.catalogs.businesses import INDUSTRIES, JOINT_FACTORY_RECIPES
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.models.joint_factories import NatJointFactory, NatJointFactoryProposal
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.joint_factory_service import JointFactoryService


router = APIRouter(prefix="/joint-factories", tags=["Natbirzha Joint Factories"])


class CreateProposalRequest(BaseModel):
    partner_company_id: int = Field(gt=0)
    recipe_id: str = Field(min_length=4, max_length=80)


def _item_row(item_id: str, quantity: float) -> dict:
    spec = CANONICAL_ITEMS.get(item_id, {})
    return {
        "item_id": item_id,
        "name": spec.get("name", item_id),
        "unit": spec.get("unit", "ед."),
        "quantity": round(float(quantity), 8),
    }


def _contribution_rows(recipe: dict, level: int, specialization: str | None = None) -> tuple[float, list[dict]]:
    contributions = recipe["levels"][level - 1]["contributions"]
    groups = [contributions[specialization]] if specialization else list(contributions.values())
    cash = float(groups[0]["cash"]) if groups else 0.0
    materials = [
        _item_row(item_id, quantity)
        for group in groups
        for item_id, quantity in group["resources"].items()
    ]
    return round(cash, 2), materials


def _contribution_sides(recipe: dict, level: int, companies: list[dict]) -> list[dict]:
    sides = []
    for company in companies:
        specialization = company.get("specialization")
        if specialization not in recipe["specializations"]:
            continue
        cash, materials = _contribution_rows(recipe, level, specialization)
        sides.append({
            "company_id": company.get("company_id"),
            "company_name": company.get("company_name", "Компания"),
            "specialization": specialization,
            "cash_contribution": cash,
            "materials": materials,
        })
    return sides


def _factory_row(
    factory: NatJointFactory,
    companies: dict[int, NatCompany],
    viewer_company_id: int,
) -> dict:
    recipe = JOINT_FACTORY_RECIPES.get(factory.recipe_id, {})
    spec_a, spec_b = tuple(recipe.get("specializations", (None, None)))
    owner_a = int(viewer_company_id) == factory.company_a_id
    partner_id = factory.company_b_id if owner_a else factory.company_a_id
    level_index = max(1, min(4, int(factory.level))) - 1
    level = recipe.get("levels", [{}] * 4)[level_index]
    stock_a = dict(factory.stock_a_json or {})
    stock_b = dict(factory.stock_b_json or {})
    my_stock = stock_a if owner_a else stock_b
    total_stock = {}
    for item_id in set(stock_a) | set(stock_b):
        total_stock[item_id] = float(stock_a.get(item_id, 0)) + float(stock_b.get(item_id, 0))
    outputs = [
        {**_item_row(item_id, quantity), "quantity_per_hour": float(quantity)}
        for item_id, quantity in level.get("outputs_per_hour", {}).items()
    ]
    claimable = [_item_row(item_id, quantity) for item_id, quantity in my_stock.items() if quantity > 1e-8]
    warehouse = [_item_row(item_id, quantity) for item_id, quantity in total_stock.items() if quantity > 1e-8]
    return {
        "id": factory.id,
        "factory_id": factory.id,
        "recipe_id": factory.recipe_id,
        "project_name": " × ".join(INDUSTRIES.get(key, {}).get("name", key or "") for key in (spec_a, spec_b)),
        "name": "Совместный завод",
        "company_a_id": factory.company_a_id,
        "company_b_id": factory.company_b_id,
        "company_a_name": companies.get(factory.company_a_id).name if companies.get(factory.company_a_id) else "Компания",
        "company_b_name": companies.get(factory.company_b_id).name if companies.get(factory.company_b_id) else "Компания",
        "partner_company_id": partner_id,
        "partner_company_name": companies.get(partner_id).name if companies.get(partner_id) else "Партнёр",
        "level": int(factory.level),
        "status": factory.status,
        "warehouse": warehouse,
        "outputs": outputs,
        "claimable": claimable,
        "claimable_quantity": round(sum(float(row["quantity"]) for row in claimable), 8),
        "total_produced": dict(factory.total_produced_json or {}),
        "total_cash_contributed": round(float(factory.total_cash_contributed), 2),
        "total_resource_contributed": round(float(factory.total_resource_contributed), 2),
        "last_settled_at": factory.last_settled_at.isoformat() if factory.last_settled_at else None,
        "created_at": factory.created_at.isoformat() if factory.created_at else None,
        "slot": "Совместный завод · отдельная мощность",
        "owner_share_reference_value": float(level.get("owner_share_reference_value", 0)),
        "maintenance_per_hour": 0,
        "inputs_per_hour": {},
    }


async def _proposal_rows(session: AsyncSession, company: NatCompany, view: str) -> list[dict]:
    if view == "inbox":
        predicate = NatJointFactoryProposal.partner_company_id == company.id
    elif view == "outbox":
        predicate = NatJointFactoryProposal.proposer_company_id == company.id
    elif view == "history":
        predicate = or_(
            NatJointFactoryProposal.partner_company_id == company.id,
            NatJointFactoryProposal.proposer_company_id == company.id,
        )
    else:
        raise ValueError("Неизвестный раздел предложений")
    rows = list((await session.execute(
        select(NatJointFactoryProposal).where(predicate)
        .order_by(NatJointFactoryProposal.created_at.desc(), NatJointFactoryProposal.id.desc())
        .limit(100)
    )).scalars().all())
    company_ids = {row.proposer_company_id for row in rows} | {row.partner_company_id for row in rows}
    companies = {
        row.id: row for row in (await session.execute(
            select(NatCompany).where(NatCompany.id.in_(company_ids))
        )).scalars().all()
    } if company_ids else {}
    result = []
    for proposal in rows:
        recipe = JOINT_FACTORY_RECIPES.get(proposal.recipe_id, {})
        proposer = companies.get(proposal.proposer_company_id)
        partner = companies.get(proposal.partner_company_id)
        contribution_level = max(1, min(4, int(proposal.target_level)))
        cash, materials = _contribution_rows(recipe, contribution_level)
        contribution_sides = _contribution_sides(recipe, contribution_level, [
            {"company_id": proposal.proposer_company_id, "company_name": proposer.name if proposer else "Компания",
             "specialization": proposer.specialization if proposer else None},
            {"company_id": proposal.partner_company_id, "company_name": partner.name if partner else "Компания",
             "specialization": partner.specialization if partner else None},
        ])
        result.append({
            "id": proposal.id,
            "proposal_id": proposal.id,
            "factory_id": proposal.factory_id,
            "recipe_id": proposal.recipe_id,
            "project_name": " × ".join(
                INDUSTRIES.get(key, {}).get("name", key)
                for key in recipe.get("specializations", ())
            ),
            "operation": proposal.operation,
            "target_level": int(proposal.target_level),
            "status": proposal.status,
            "proposer_company_id": proposal.proposer_company_id,
            "partner_company_id": proposal.partner_company_id,
            "proposer_company_name": proposer.name if proposer else "Компания",
            "partner_company_name": partner.name if partner else "Компания",
            "cash_contribution": cash,
            "materials": materials,
            "contribution_sides": contribution_sides,
            "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
            "responded_at": proposal.responded_at.isoformat() if proposal.responded_at else None,
        })
    return result


async def _mutate(session, company, endpoint: str, key: str | None, payload: dict, operation) -> dict:
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, key, payload
    )
    if cached:
        return cached[1]
    if not key:
        raise HTTPException(status_code=400, detail="Нужен ключ идемпотентности")
    try:
        response = await operation()
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, key, payload, response
    )


@router.get("")
async def list_joint_factories(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await IdleEconomyService.settle_company(session, company.id)
    rows = list((await session.execute(select(NatJointFactory).where(
        or_(NatJointFactory.company_a_id == company.id, NatJointFactory.company_b_id == company.id)
    ).order_by(NatJointFactory.created_at.desc(), NatJointFactory.id.desc()))).scalars().all())
    other_ids = {row.company_a_id for row in rows} | {row.company_b_id for row in rows}
    companies = {row.id: row for row in (await session.execute(
        select(NatCompany).where(NatCompany.id.in_(other_ids))
    )).scalars().all()} if other_ids else {}
    await session.commit()
    items = [_factory_row(row, companies, company.id) for row in rows]
    occupied = any(row.status == "ACTIVE" for row in rows)
    return {
        "items": items,
        "slot": {"capacity": 1, "occupied": occupied, "used": occupied},
        "has_active_factory": occupied,
        "slot_label": "Совместный завод",
    }


@router.get("/partners")
async def joint_factory_partners(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    rows = await JointFactoryService.partners(session, company)
    if rows:
        user_ids = {
            row.id: row.user_id for row in (await session.execute(
                select(NatCompany).where(NatCompany.id.in_([item["company_id"] for item in rows]))
            )).scalars().all()
        }
        partner_companies = {
            row.id: row for row in (await session.execute(
                select(NatCompany).where(NatCompany.id.in_(user_ids))
            )).scalars().all()
        }
        users = {row.id: row for row in (await session.execute(
            select(User).where(User.id.in_(set(user_ids.values())))
        )).scalars().all()} if user_ids else {}
        for item in rows:
            partner = item["specialization"]
            recipe = JOINT_FACTORY_RECIPES[item["recipe_id"]]
            cash, materials = _contribution_rows(recipe, 1, company.specialization)
            output_rows = [
                {**_item_row(item_id, qty), "quantity_per_hour": qty}
                for item_id, qty in recipe["levels"][0]["outputs_per_hour"].items()
            ]
            item["partner_company_id"] = item["company_id"]
            item["partner_company_name"] = item["company_name"]
            item["partner_industry_name"] = INDUSTRIES[partner]["name"]
            item["project_name"] = item["recipe_name"]
            item["cash_contribution"] = cash
            item["materials"] = materials
            item["contributions"] = materials
            item["outputs"] = output_rows
            partner_company = partner_companies.get(item["company_id"])
            item["contribution_sides"] = _contribution_sides(recipe, 1, [
                {"company_id": company.id, "company_name": company.name,
                 "specialization": company.specialization},
                {"company_id": item["company_id"], "company_name": item["company_name"],
                 "specialization": partner_company.specialization if partner_company else partner},
            ])
            user = users.get(user_ids.get(item["company_id"]))
            item["player_name"] = user.display_name if user else None
    return {"items": rows, "slot": {"capacity": 1, "occupied": False}}


@router.post("/proposals")
async def create_joint_factory_proposal(
    request: CreateProposalRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = request.model_dump()
    return await _mutate(
        session, company, f"/api/natbirzha/joint-factories/proposals/company/{company.id}",
        idempotency_key, payload,
        lambda: JointFactoryService.create_build_proposal(
            session, company.id, request.partner_company_id, request.recipe_id
        ),
    )


@router.get("/proposals/{view}")
async def joint_factory_proposals(
    view: Literal["inbox", "outbox", "history"],
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    items = await _proposal_rows(session, company, view)
    return {"items": items}


@router.post("/proposals/{proposal_id}/accept")
async def accept_joint_factory_proposal(
    proposal_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = {"proposal_id": proposal_id}
    return await _mutate(
        session, company,
        f"/api/natbirzha/joint-factories/proposals/{proposal_id}/accept/company/{company.id}",
        idempotency_key, payload,
        lambda: JointFactoryService.accept_proposal(session, company.id, proposal_id),
    )


@router.post("/proposals/{proposal_id}/reject")
async def reject_joint_factory_proposal(
    proposal_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = {"proposal_id": proposal_id}
    return await _mutate(
        session, company,
        f"/api/natbirzha/joint-factories/proposals/{proposal_id}/reject/company/{company.id}",
        idempotency_key, payload,
        lambda: JointFactoryService.reject_proposal(session, company.id, proposal_id),
    )


@router.post("/proposals/{proposal_id}/cancel")
async def cancel_joint_factory_proposal(
    proposal_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = {"proposal_id": proposal_id}
    return await _mutate(
        session, company,
        f"/api/natbirzha/joint-factories/proposals/{proposal_id}/cancel/company/{company.id}",
        idempotency_key, payload,
        lambda: JointFactoryService.cancel_proposal(session, company.id, proposal_id),
    )


@router.get("/{factory_id}")
async def joint_factory_detail(
    factory_id: int,
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await IdleEconomyService.settle_company(session, company.id)
    row = await session.scalar(select(NatJointFactory).where(
        NatJointFactory.id == int(factory_id),
        or_(NatJointFactory.company_a_id == company.id, NatJointFactory.company_b_id == company.id),
    ))
    if row is None:
        raise HTTPException(status_code=404, detail="Совместный завод не найден")
    companies = {item.id: item for item in (await session.execute(
        select(NatCompany).where(NatCompany.id.in_((row.company_a_id, row.company_b_id)))
    )).scalars().all()}
    await session.commit()
    return _factory_row(row, companies, company.id)


@router.post("/{factory_id}/upgrade")
async def request_joint_factory_upgrade(
    factory_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = {"factory_id": factory_id}
    return await _mutate(
        session, company,
        f"/api/natbirzha/joint-factories/{factory_id}/upgrade/company/{company.id}",
        idempotency_key, payload,
        lambda: JointFactoryService.create_upgrade_proposal(session, company.id, factory_id),
    )


@router.post("/{factory_id}/claim")
async def claim_joint_factory_output(
    factory_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    payload = {"factory_id": factory_id}
    return await _mutate(
        session, company,
        f"/api/natbirzha/joint-factories/{factory_id}/claim/company/{company.id}",
        idempotency_key, payload,
        lambda: JointFactoryService.claim_output(session, company.id, factory_id),
    )


__all__ = ["router"]
