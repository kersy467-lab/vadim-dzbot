"""Authenticated API for requests and gifts between companies."""

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.company_aid import NatCompanyAidRequest
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.company_aid_service import CompanyAidService
from backend.natbirzha.services.idempotency_service import IdempotencyService


router = APIRouter(prefix="/aid", tags=["Natbirzha Company Aid"])


class AidRequestBody(BaseModel):
    kind: Literal["cash", "item"]
    amount_cash: Optional[float] = Field(default=None, gt=0, le=100_000)
    item_id: Optional[str] = Field(default=None, min_length=1, max_length=50)
    item_quantity: Optional[float] = Field(default=None, gt=0, le=1_000_000_000)
    message: Optional[str] = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_payload(self):
        if self.kind == "cash" and (self.amount_cash is None or self.item_id or self.item_quantity is not None):
            raise ValueError("Для денежного запроса укажите только amount_cash")
        if self.kind == "item" and (not self.item_id or self.item_quantity is None or self.amount_cash is not None):
            raise ValueError("Для запроса товара укажите item_id и item_quantity")
        return self


class AidTransferBody(BaseModel):
    recipient_company_id: int = Field(gt=0)
    request_id: int = Field(gt=0)
    amount_cash: Optional[float] = Field(default=None, gt=0, le=100_000)
    item_id: Optional[str] = Field(default=None, min_length=1, max_length=50)
    quantity: Optional[float] = Field(default=None, gt=0, le=1_000_000_000)

    @model_validator(mode="after")
    def validate_payload(self):
        cash = self.amount_cash is not None
        item = self.item_id is not None or self.quantity is not None
        if cash == item:
            raise ValueError("Переведите либо деньги, либо один вид товара")
        if item and (not self.item_id or self.quantity is None):
            raise ValueError("Для товара укажите item_id и quantity")
        return self


def _require_idempotency_key(value: Optional[str]) -> str:
    if not value or not value.strip():
        raise HTTPException(status_code=400, detail="Нужен ключ идемпотентности")
    return value.strip()[:128]


def _raise_service_error(exc: ValueError) -> None:
    raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/requests")
async def list_aid_requests(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return {"requests": await CompanyAidService.list_requests(
        session, exclude_company_id=company.id,
    )}


@router.get("/my-request")
async def get_my_aid_request(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    request = await session.scalar(select(NatCompanyAidRequest).where(
        NatCompanyAidRequest.company_id == company.id,
        NatCompanyAidRequest.status == "OPEN",
    ).order_by(NatCompanyAidRequest.created_at.desc()).limit(1))
    return {"request": CompanyAidService._request_view(request) if request else None}


@router.get("/summary")
async def get_aid_summary(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return {"summary": await CompanyAidService.summary(session, company.id)}


@router.post("/requests")
async def create_aid_request(
    req: AidRequestBody,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_idempotency_key(idempotency_key)
    endpoint = f"/api/natbirzha/aid/requests/company/{company.id}"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, key, payload,
    )
    if cached:
        return cached[1]
    try:
        response = {"request": await CompanyAidService.create_request(
            session, company.id, **payload,
        )}
    except ValueError as exc:
        _raise_service_error(exc)
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, key, payload, response,
    )


@router.post("/requests/{request_id}/cancel")
async def cancel_aid_request(
    request_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_idempotency_key(idempotency_key)
    endpoint = f"/api/natbirzha/aid/requests/{request_id}/cancel/company/{company.id}"
    payload = {"request_id": request_id}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, key, payload,
    )
    if cached:
        return cached[1]
    try:
        response = {"request": await CompanyAidService.cancel_request(
            session, company.id, request_id,
        )}
    except ValueError as exc:
        _raise_service_error(exc)
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, key, payload, response,
    )


@router.post("/transfer")
async def transfer_aid(
    req: AidTransferBody,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    key = _require_idempotency_key(idempotency_key)
    endpoint = f"/api/natbirzha/aid/transfer/company/{company.id}"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, key, payload,
    )
    if cached:
        return cached[1]
    try:
        response = await CompanyAidService.transfer(
            session,
            company.id,
            req.recipient_company_id,
            amount_cash=req.amount_cash,
            item_id=req.item_id,
            quantity=req.quantity,
            request_id=req.request_id,
        )
    except ValueError as exc:
        _raise_service_error(exc)
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, key, payload, response,
    )


__all__ = ["router"]
