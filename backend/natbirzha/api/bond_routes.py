from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.creator_service import CreatorService
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.state_bond_service import StateBondService

router = APIRouter(prefix="/bonds", tags=["Natbirzha State Bonds"])


class BuyBondRequest(BaseModel):
    quantity: int = Field(gt=0)


class CreateBondListingRequest(BaseModel):
    bond_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    unit_price: float = Field(gt=0)


@router.get("")
async def list_state_bonds(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    return {
        "bonds": await CreatorService.get_bonds(session),
        "holdings": await CreatorService.get_company_bond_holdings(session, company.id),
        "listings": await StateBondService.listings(session),
    }


@router.post("/listings")
async def create_bond_listing(
    req: CreateBondListingRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required.")
    endpoint = "/api/natbirzha/bonds/listings"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(session, company.user_id, endpoint, idempotency_key, payload)
    if cached:
        return cached[1]
    try:
        result = await StateBondService.create_listing(
            session, company.id, req.bond_id, req.quantity, req.unit_price,
            f"api:list:{company.id}:{idempotency_key}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, result
    )


@router.post("/listings/{listing_id}/buy")
async def buy_bond_listing(
    listing_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required.")
    endpoint = f"/api/natbirzha/bonds/listings/{listing_id}/buy"
    payload = {"listing_id": listing_id}
    cached = await IdempotencyService.check_or_conflict(session, company.user_id, endpoint, idempotency_key, payload)
    if cached:
        return cached[1]
    try:
        result = await StateBondService.buy_listing(
            session, company.id, listing_id, f"api:list-buy:{company.id}:{idempotency_key}"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, result
    )


@router.delete("/listings/{listing_id}")
async def cancel_bond_listing(
    listing_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required.")
    endpoint = f"/api/natbirzha/bonds/listings/{listing_id}"
    payload = {"listing_id": listing_id}
    cached = await IdempotencyService.check_or_conflict(session, company.user_id, endpoint, idempotency_key, payload)
    if cached:
        return cached[1]
    try:
        result = await StateBondService.cancel_listing(session, company.id, listing_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, result
    )


@router.post("/{bond_id}/buy")
async def buy_state_bonds(
    bond_id: int,
    req: BuyBondRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = f"/api/natbirzha/bonds/{bond_id}/buy"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]

    try:
        result = await CreatorService.buy_state_bonds(
            session, company, bond_id, req.quantity, commit=False
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return await IdempotencyService.commit_response(
        session,
        company.user_id,
        endpoint,
        idempotency_key,
        payload,
        result,
    )


__all__ = ["router"]
