"""Authenticated endpoints for bilateral joint-factory projects."""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session
from backend.natbirzha.catalogs.businesses import INDUSTRIES, JOINT_FACTORY_RECIPES
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.joint_factories import NatJointFactory
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.idle_economy_service import IdleEconomyService
from backend.natbirzha.services.joint_factory_service import JointFactoryService
from .joint_factory_notifications import notify_joint_proposal as _notify_joint_proposal
from .joint_factory_presenters import (
    contribution_rows as _contribution_rows,
    contribution_sides as _contribution_sides,
    factory_row as _factory_row,
    item_row as _item_row,
    proposal_rows as _proposal_rows,
)


router = APIRouter(prefix="/joint-factories", tags=["Natbirzha Joint Factories"])
logger = logging.getLogger(__name__)


class CreateProposalRequest(BaseModel):
    partner_company_id: int = Field(gt=0)
    recipe_id: str = Field(min_length=4, max_length=80)


async def _mutate(
    session,
    company,
    endpoint: str,
    key: str | None,
    payload: dict,
    operation,
    notification_event: str | None = None,
) -> dict:
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
    committed, created = await IdempotencyService.commit_response_once(
        session, company.user_id, endpoint, key, payload, response
    )
    if notification_event and created and committed.get("proposal_id"):
        try:
            await _notify_joint_proposal(
                session, company.id, int(committed["proposal_id"]), notification_event
            )
        except Exception:
            logger.warning("Could not deliver joint-factory DM after commit", exc_info=True)
    return committed


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
        notification_event="created",
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
        notification_event="accepted",
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
        notification_event="rejected",
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
        notification_event="cancelled",
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
        notification_event="created",
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
