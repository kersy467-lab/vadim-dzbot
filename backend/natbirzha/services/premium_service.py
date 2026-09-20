"""Atomic Pivocoin wallet and time-limited license operations."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.premium import NatPremiumLedgerEntry, NatPremiumLicense
from backend.natbirzha.services.premium_catalog import PREMIUM_LICENSES, PremiumLicenseSpec


class PremiumError(ValueError):
    """Base premium-economy domain error."""


class InsufficientPvc(PremiumError):
    def __init__(self, *, required: int, available: int) -> None:
        self.required = required
        self.available = available
        super().__init__(f"Недостаточно PVC: нужно {required}, доступно {available}")


class PremiumOperationConflict(PremiumError):
    pass


class UnknownPremiumLicense(PremiumError):
    pass


class PremiumLicenseRequired(PremiumError):
    def __init__(self, license_code: str) -> None:
        self.license_code = license_code
        super().__init__(f"Active premium license required: {license_code}")


class PremiumService:
    @staticmethod
    async def _operation_by_key(
        session: AsyncSession, operation_key: str
    ) -> NatPremiumLedgerEntry | None:
        return await session.scalar(
            select(NatPremiumLedgerEntry).where(
                NatPremiumLedgerEntry.operation_key == operation_key
            )
        )

    @staticmethod
    def _validate_replay(
        entry: NatPremiumLedgerEntry,
        *,
        company_id: int,
        amount: int,
        operation_type: str,
    ) -> None:
        if (
            entry.company_id != company_id
            or entry.amount != amount
            or entry.operation_type != operation_type
        ):
            raise PremiumOperationConflict("PVC operation key reused with different parameters")

    @classmethod
    async def apply_pvc(
        cls,
        session: AsyncSession,
        company_id: int,
        amount: int,
        operation_type: str,
        operation_key: str,
        metadata: dict[str, Any] | None = None,
        actor_user_id: int | None = None,
    ) -> NatPremiumLedgerEntry:
        """Apply one idempotent wallet mutation without committing the transaction."""

        if not operation_key or len(operation_key) > 160:
            raise PremiumError("PVC operation key must contain 1-160 characters")
        if not operation_type or len(operation_type) > 40:
            raise PremiumError("PVC operation type must contain 1-40 characters")
        if isinstance(amount, bool) or not isinstance(amount, int) or amount == 0:
            raise PremiumError("PVC amount must be a non-zero integer")

        existing = await cls._operation_by_key(session, operation_key)
        if existing is not None:
            cls._validate_replay(
                existing,
                company_id=company_id,
                amount=amount,
                operation_type=operation_type,
            )
            return existing

        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id).with_for_update()
        )
        if company is None:
            raise PremiumError("Company not found")
        balance_before = int(company.pvc_balance)
        balance_after = balance_before + amount
        if balance_after < 0:
            raise InsufficientPvc(required=-amount, available=balance_before)

        entry = NatPremiumLedgerEntry(
            company_id=company_id,
            amount=amount,
            balance_before=balance_before,
            balance_after=balance_after,
            operation_type=operation_type,
            operation_key=operation_key,
            actor_user_id=actor_user_id,
            metadata_json=metadata or {},
        )
        company.pvc_balance = balance_after
        session.add(entry)
        await session.flush()
        return entry

    @classmethod
    async def purchase_license(
        cls,
        session: AsyncSession,
        company_id: int,
        license_code: str,
        operation_key: str,
        *,
        now: datetime | None = None,
        actor_user_id: int | None = None,
    ) -> NatPremiumLicense:
        """Buy or renew a license, extending it by exactly its catalog duration."""

        spec = PREMIUM_LICENSES.get(license_code)
        if spec is None:
            raise UnknownPremiumLicense(f"Unknown premium license: {license_code}")
        now = now or datetime.utcnow()
        debit_type = "license_purchase"

        existing_operation = await cls._operation_by_key(session, operation_key)
        if existing_operation is not None:
            cls._validate_replay(
                existing_operation,
                company_id=company_id,
                amount=-spec.price_pvc,
                operation_type=debit_type,
            )
            replayed = await session.scalar(
                select(NatPremiumLicense).where(
                    NatPremiumLicense.company_id == company_id,
                    NatPremiumLicense.license_code == license_code,
                )
            )
            if replayed is None:
                raise PremiumOperationConflict("License operation exists without its license")
            return replayed

        license_row = await session.scalar(
            select(NatPremiumLicense)
            .where(
                NatPremiumLicense.company_id == company_id,
                NatPremiumLicense.license_code == license_code,
            )
            .with_for_update()
        )
        ledger = await cls.apply_pvc(
            session,
            company_id,
            -spec.price_pvc,
            debit_type,
            operation_key,
            {"license_code": license_code, "duration_hours": spec.duration_hours},
            actor_user_id,
        )
        base_time = max(now, license_row.expires_at) if license_row is not None else now
        expires_at = base_time + timedelta(hours=spec.duration_hours)

        if license_row is None:
            license_row = NatPremiumLicense(
                company_id=company_id,
                license_code=license_code,
                starts_at=now,
                expires_at=expires_at,
                status="ACTIVE",
                purchase_ledger_id=ledger.id,
            )
            session.add(license_row)
        else:
            if license_row.expires_at <= now:
                license_row.starts_at = now
            license_row.expires_at = expires_at
            license_row.status = "ACTIVE"
            license_row.purchase_ledger_id = ledger.id
            license_row.updated_at = now
        await session.flush()
        return license_row

    @staticmethod
    async def is_license_active(
        session: AsyncSession,
        company_id: int,
        license_code: str,
        now: datetime | None = None,
    ) -> bool:
        now = now or datetime.utcnow()
        license_row = await session.scalar(
            select(NatPremiumLicense).where(
                NatPremiumLicense.company_id == company_id,
                NatPremiumLicense.license_code == license_code,
            )
        )
        return bool(
            license_row
            and license_row.status == "ACTIVE"
            and license_row.starts_at <= now < license_row.expires_at
        )

    @staticmethod
    async def require_active_license(
        session: AsyncSession,
        company_id: int,
        license_code: str,
        now: datetime | None = None,
    ) -> NatPremiumLicense:
        now = now or datetime.utcnow()
        license_row = await session.scalar(
            select(NatPremiumLicense).where(
                NatPremiumLicense.company_id == company_id,
                NatPremiumLicense.license_code == license_code,
            )
        )
        if not (
            license_row
            and license_row.status == "ACTIVE"
            and license_row.starts_at <= now < license_row.expires_at
        ):
            raise PremiumLicenseRequired(license_code)
        return license_row

    @staticmethod
    def catalog_entry(license_code: str) -> PremiumLicenseSpec:
        spec = PREMIUM_LICENSES.get(license_code)
        if spec is None:
            raise UnknownPremiumLicense(f"Unknown premium license: {license_code}")
        return spec
