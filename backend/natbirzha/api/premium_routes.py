"""HTTP contract for Pivocoin wallets and premium licenses."""

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.premium import NatPremiumLedgerEntry, NatPremiumLicense
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.premium_catalog import (
    MILITARY_UPGRADES,
    serialize_license_catalog,
    serialize_upgrade_catalog,
)
from backend.natbirzha.services.premium_service import PremiumError, PremiumService
from backend.natbirzha.services.premium_upgrade_service import PremiumUpgradeService


router = APIRouter(prefix="/premium", tags=["Natbirzha Premium"])


def _serialize_license(row: NatPremiumLicense) -> dict:
    return {
        "code": row.license_code,
        "starts_at": row.starts_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
        "status": row.status,
    }


@router.get("/wallet")
async def get_wallet(company: NatCompany = Depends(get_current_company)):
    return {"currency": "PVC", "balance": company.pvc_balance}


@router.get("/ledger")
async def get_ledger(
    limit: int = Query(50, ge=1, le=200),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    rows = (
        await session.execute(
            select(NatPremiumLedgerEntry)
            .where(NatPremiumLedgerEntry.company_id == company.id)
            .order_by(NatPremiumLedgerEntry.id.desc())
            .limit(limit)
        )
    ).scalars().all()
    return {
        "currency": "PVC",
        "balance": company.pvc_balance,
        "entries": [
            {
                "id": row.id,
                "amount": row.amount,
                "balance_before": row.balance_before,
                "balance_after": row.balance_after,
                "operation_type": row.operation_type,
                "metadata": row.metadata_json,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


@router.get("/licenses/catalog")
async def get_license_catalog():
    return {"currency": "PVC", "licenses": serialize_license_catalog()}


@router.get("/licenses")
async def get_owned_licenses(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    rows = (
        await session.execute(
            select(NatPremiumLicense)
            .where(NatPremiumLicense.company_id == company.id)
            .order_by(NatPremiumLicense.expires_at.desc())
        )
    ).scalars().all()
    return {"licenses": [_serialize_license(row) for row in rows]}


@router.get("/upgrades/catalog")
async def get_upgrade_catalog():
    return {"upgrades": serialize_upgrade_catalog()}


@router.get("/upgrades")
async def get_owned_upgrades(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    rows = await PremiumUpgradeService.owned(session, company.id)
    return {
        "upgrades": [
            {"code": row.upgrade_code, "level": row.level, "updated_at": row.updated_at.isoformat()}
            for row in rows
        ]
    }


@router.post("/upgrades/{upgrade_code}/purchase")
async def purchase_upgrade(
    upgrade_code: str,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    endpoint = f"/api/natbirzha/premium/upgrades/{upgrade_code}/purchase"
    payload = {"upgrade_code": upgrade_code}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    if upgrade_code not in MILITARY_UPGRADES:
        raise HTTPException(status_code=404, detail="Premium military upgrade not found")
    try:
        row = await PremiumUpgradeService.purchase_upgrade(
            session, company.id, upgrade_code
        )
        response = {
            "success": True,
            "upgrade": {"code": row.upgrade_code, "level": row.level},
            "next_level_cost": {
                item_id: quantity * (row.level + 1)
                for item_id, quantity in MILITARY_UPGRADES[upgrade_code].resource_cost.items()
            } if row.level < MILITARY_UPGRADES[upgrade_code].max_level else None,
        }
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload, response
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/licenses/{license_code}/purchase")
async def purchase_license(
    license_code: str,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    endpoint = f"/api/natbirzha/premium/licenses/{license_code}/purchase"
    payload = {"license_code": license_code}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        spec = PremiumService.catalog_entry(license_code)
        license_row = await PremiumService.purchase_license(
            session,
            company.id,
            license_code,
            f"license:{company.id}:{license_code}:{idempotency_key}",
            actor_user_id=company.user_id,
        )
        response = {
            "success": True,
            "currency": "PVC",
            "price_pvc": spec.price_pvc,
            "balance": company.pvc_balance,
            "license": _serialize_license(license_row),
        }
        return await IdempotencyService.commit_response(
            session, company.user_id, endpoint, idempotency_key, payload, response
        )
    except PremiumError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
