"""Private Telegram notifications for joint-factory proposal events."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.catalogs.businesses import INDUSTRIES, JOINT_FACTORY_RECIPES
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.joint_factories import NatJointFactoryProposal
from backend.natbirzha.services.player_dm_service import send_company_dm


async def notify_joint_proposal(
    session: AsyncSession,
    actor_company_id: int,
    proposal_id: int,
    event: str,
) -> None:
    proposal = await session.get(NatJointFactoryProposal, proposal_id)
    if proposal is None:
        return
    recipient_id = (
        proposal.partner_company_id
        if actor_company_id == proposal.proposer_company_id
        else proposal.proposer_company_id
    )
    company_ids = (proposal.proposer_company_id, proposal.partner_company_id)
    companies = {
        row.id: row for row in (await session.execute(
            select(NatCompany).where(NatCompany.id.in_(company_ids))
        )).scalars().all()
    }
    proposer = companies.get(proposal.proposer_company_id)
    actor = companies.get(actor_company_id)
    recipe = JOINT_FACTORY_RECIPES.get(proposal.recipe_id, {})
    project_name = " × ".join(
        INDUSTRIES.get(industry, {}).get("name", industry)
        for industry in recipe.get("specializations", ())
    ) or "Совместный завод"
    operation_name = "строительство" if proposal.operation == "BUILD" else "улучшение"
    if event == "created":
        heading = f"Компания {proposer.name if proposer else 'Партнёр'} предлагает совместное предприятие"
    elif event == "accepted":
        heading = f"Компания {actor.name if actor else 'Партнёр'} приняла предложение"
    elif event == "rejected":
        heading = f"Компания {actor.name if actor else 'Партнёр'} отклонила предложение"
    else:
        heading = f"Компания {actor.name if actor else 'Партнёр'} отменила предложение"
    await send_company_dm(
        session,
        recipient_id,
        f"🤝 {heading}.\n"
        f"Проект: {project_name}.\n"
        f"Действие: {operation_name}, целевой уровень {proposal.target_level}.\n"
        f"Статус: {proposal.status}.",
    )


__all__ = ["notify_joint_proposal"]
