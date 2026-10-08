"""Response shaping for joint-factory API screens."""

from backend.natbirzha.services.progression_service import company_production_multiplier


from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import INDUSTRIES, get_joint_factory_recipe
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.models.joint_factories import NatJointFactory, NatJointFactoryProposal


def item_row(item_id: str, quantity: float) -> dict:
    spec = CANONICAL_ITEMS.get(item_id, {})
    return {
        "item_id": item_id,
        "name": spec.get("name", item_id),
        "unit": spec.get("unit", "ед."),
        "quantity": round(float(quantity), 8),
    }


def contribution_rows(
    recipe: dict, level: int, specialization: str | None = None
) -> tuple[float, list[dict]]:
    contributions = recipe["levels"][level - 1]["contributions"]
    groups = [contributions[specialization]] if specialization else list(contributions.values())
    cash = float(groups[0]["cash"]) if groups else 0.0
    materials = [
        item_row(item_id, quantity)
        for group in groups
        for item_id, quantity in group["resources"].items()
    ]
    return round(cash, 2), materials


def contribution_sides(recipe: dict, level: int, companies: list[dict]) -> list[dict]:
    sides = []
    for company in companies:
        specialization = company.get("specialization")
        if specialization not in recipe["specializations"]:
            continue
        cash, materials = contribution_rows(recipe, level, specialization)
        sides.append({
            "company_id": company.get("company_id"),
            "company_name": company.get("company_name", "Компания"),
            "specialization": specialization,
            "cash_contribution": cash,
            "materials": materials,
        })
    return sides


def factory_row(
    factory: NatJointFactory,
    companies: dict[int, NatCompany],
    viewer_company_id: int,
) -> dict:
    recipe = get_joint_factory_recipe(factory.recipe_id) or {}
    spec_a, spec_b = tuple(recipe.get("specializations", (None, None)))
    owner_a = int(viewer_company_id) == factory.company_a_id
    partner_id = factory.company_b_id if owner_a else factory.company_a_id
    level_index = max(1, min(4, int(factory.level))) - 1
    level = recipe.get("levels", [{}] * 4)[level_index]
    stock_a = dict(factory.stock_a_json or {})
    stock_b = dict(factory.stock_b_json or {})
    my_stock = stock_a if owner_a else stock_b
    total_stock = {
        item_id: float(stock_a.get(item_id, 0)) + float(stock_b.get(item_id, 0))
        for item_id in set(stock_a) | set(stock_b)
    }
    bonuses = {cid: company_production_multiplier(owner) for cid, owner in companies.items()}
    total_bonus = (bonuses.get(factory.company_a_id, 1) + bonuses.get(factory.company_b_id, 1)) / 2
    owner_bonus = bonuses.get(viewer_company_id, 1)
    outputs = [
        {**item_row(item_id, quantity * total_bonus), "quantity_per_hour": float(quantity) * total_bonus, "owner_quantity_per_hour": float(quantity) * owner_bonus / 2}
        for item_id, quantity in level.get("outputs_per_hour", {}).items()
    ]
    claimable = [item_row(item_id, quantity) for item_id, quantity in my_stock.items() if quantity > 1e-8]
    warehouse = [item_row(item_id, quantity) for item_id, quantity in total_stock.items() if quantity > 1e-8]
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
        "owner_share_reference_value": float(level.get("owner_share_reference_value", 0)) * owner_bonus,
        "maintenance_per_hour": 0,
        "inputs_per_hour": {},
    }


async def proposal_rows(session: AsyncSession, company: NatCompany, view: str) -> list[dict]:
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
        recipe = get_joint_factory_recipe(proposal.recipe_id) or {}
        proposer = companies.get(proposal.proposer_company_id)
        partner = companies.get(proposal.partner_company_id)
        contribution_level = max(1, min(4, int(proposal.target_level)))
        cash, materials = contribution_rows(recipe, contribution_level)
        sides = contribution_sides(recipe, contribution_level, [
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
            "contribution_sides": sides,
            "created_at": proposal.created_at.isoformat() if proposal.created_at else None,
            "responded_at": proposal.responded_at.isoformat() if proposal.responded_at else None,
        })
    return result


__all__ = ["item_row", "contribution_rows", "contribution_sides", "factory_row", "proposal_rows"]
