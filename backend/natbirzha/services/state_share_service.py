"""Fixed-price state share issuance, Treasury redemption and daily dividends."""

import hashlib
import json
import math
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatCreatorAuditLog
from backend.natbirzha.models.state_shares import (
    NatStateShare,
    NatStateShareHolding,
    NatStateShareOperation,
)
from backend.natbirzha.services.state_share_settlement import StateShareSettlementMixin
from backend.natbirzha.services.state_treasury_service import StateTreasuryService


class StateShareIdempotencyConflict(ValueError):
    """A state-share operation key was reused for a different request."""


class StateShareService(StateShareSettlementMixin):
    """State share issues do not use or mutate company stock/IPO models."""

    @staticmethod
    def _payload_hash(payload: dict[str, Any]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @classmethod
    async def _replay(
        cls, session: AsyncSession, key: str, operation_type: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not key or len(key) > 180:
            raise ValueError("A valid operation key is required.")
        operation = await session.scalar(
            select(NatStateShareOperation).where(NatStateShareOperation.operation_key == key)
        )
        if operation is None:
            return None
        if operation.operation_type != operation_type or operation.request_hash != cls._payload_hash(payload):
            raise StateShareIdempotencyConflict(
                "Operation key was already used for a different state share request."
            )
        return operation.response_json

    @classmethod
    async def _record_operation(
        cls,
        session: AsyncSession,
        key: str,
        operation_type: str,
        payload: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        session.add(NatStateShareOperation(
            operation_key=key,
            operation_type=operation_type,
            request_hash=cls._payload_hash(payload),
            response_json=response,
        ))
        await session.flush()

    @classmethod
    async def issue(
        cls,
        session: AsyncSession,
        actor_id: int,
        title: str,
        purpose: str,
        volume: int,
        issue_price: float,
        projected_annual_profit: float,
        dividend_rate_pct: float,
        operation_key: str,
        *,
        commit: bool = True,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not all(math.isfinite(float(value)) for value in (
            issue_price, projected_annual_profit, dividend_rate_pct
        )):
            raise ValueError("Issue price, projected profit, and dividend rate must be finite numbers.")
        payload = {
            "actor_id": actor_id,
            "title": title.strip(),
            "purpose": purpose.strip(),
            "volume": volume,
            "issue_price": round(float(issue_price), 2),
            "projected_annual_profit": round(float(projected_annual_profit), 2),
            "dividend_rate_pct": round(float(dividend_rate_pct), 4),
        }
        replay = await cls._replay(session, operation_key, "ISSUE", payload)
        if replay is not None:
            return replay
        if (
            not payload["title"]
            or len(payload["title"]) > 100
            or volume <= 0
            or volume > 2_000_000_000
            or payload["issue_price"] <= 0
            or payload["issue_price"] > 1_000_000_000_000
            or payload["projected_annual_profit"] > 1_000_000_000_000_000
        ):
            raise ValueError("Title, volume, and issue price must be positive.")
        if len(payload["purpose"]) > 255:
            raise ValueError("Purpose must not exceed 255 characters.")
        if projected_annual_profit < 0 or not 0 <= dividend_rate_pct <= 100:
            raise ValueError("Projected profit must be nonnegative and dividend rate must be 0–100%.")

        # The Treasury row is ensured for later trades, but the unpurchased issue
        # itself has no cash flow and never increases Treasury reserves.
        treasury = await StateTreasuryService.get_or_create(
            session, commit=False, for_update=True
        )
        replay = await cls._replay(session, operation_key, "ISSUE", payload)
        if replay is not None:
            return replay
        now = now or get_game_now()
        share = NatStateShare(
            title=payload["title"],
            purpose=payload["purpose"],
            total_volume=volume,
            remaining_volume=volume,
            issue_price=payload["issue_price"],
            projected_annual_profit=payload["projected_annual_profit"],
            dividend_rate_pct=payload["dividend_rate_pct"],
            actor_id=actor_id,
            is_active=True,
            created_at=now,
        )
        session.add(share)
        await session.flush()
        session.add(NatCreatorAuditLog(
            actor_id=actor_id,
            action="STATE_SHARE_ISSUANCE",
            target_type="state_share",
            target_id=str(share.id),
            details=(
                f"Выпуск {volume} шт. по {payload['issue_price']} cash; "
                f"прогноз годовой прибыли {payload['projected_annual_profit']} cash, "
                f"ставка дивидендов {payload['dividend_rate_pct']}%."
            ),
            created_at=now,
        ))
        result = {
            "success": True,
            "share_id": share.id,
            "title": share.title,
            "purpose": share.purpose,
            "total_volume": share.total_volume,
            "remaining_volume": share.remaining_volume,
            "issue_price": share.issue_price,
            "projected_annual_profit": share.projected_annual_profit,
            "dividend_rate_pct": share.dividend_rate_pct,
            "treasury_cash": round(float(treasury.cash), 2),
        }
        await cls._record_operation(session, operation_key, "ISSUE", payload, result)
        if commit:
            await session.commit()
        return result

    @classmethod
    async def buy(
        cls,
        session: AsyncSession,
        company: NatCompany,
        share_id: int,
        quantity: int,
        *,
        operation_key: str,
        commit: bool = True,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        payload = {"company_id": company.id, "share_id": share_id, "quantity": quantity}
        replay = await cls._replay(session, operation_key, "BUY", payload)
        if replay is not None:
            return replay
        if quantity <= 0:
            raise ValueError("Share quantity must be positive.")
        now = now or get_game_now()
        treasury = await StateTreasuryService.get_or_create(session, commit=False, for_update=True)
        replay = await cls._replay(session, operation_key, "BUY", payload)
        if replay is not None:
            return replay
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
            .execution_options(populate_existing=True)
        )
        share = await session.scalar(select(NatStateShare).where(NatStateShare.id == share_id).with_for_update())
        if not company:
            raise ValueError("Company not found.")
        if not share or not share.is_active:
            raise ValueError("Active state share issue not found.")
        if share.remaining_volume < quantity:
            raise ValueError(f"Insufficient share supply. Remaining: {share.remaining_volume}.")
        total_cost = round(float(share.issue_price) * quantity, 2)
        if company.cash < total_cost:
            raise ValueError(f"Insufficient cash. Required: {total_cost}, available: {company.cash}.")

        holding = await session.scalar(select(NatStateShareHolding).where(
            NatStateShareHolding.share_id == share_id,
            NatStateShareHolding.company_id == company.id,
        ).with_for_update())
        if holding is None:
            holding = NatStateShareHolding(
                share_id=share_id,
                company_id=company.id,
                quantity=0,
                invested_cash=0.0,
                dividends_earned=0.0,
                updated_at=now,
            )
            session.add(holding)
        company.cash = round(float(company.cash) - total_cost, 2)
        treasury.cash = round(float(treasury.cash) + total_cost, 2)
        treasury.updated_at = now
        share.remaining_volume -= quantity
        holding.quantity += quantity
        holding.invested_cash = round(float(holding.invested_cash) + total_cost, 2)
        holding.updated_at = now
        await session.flush()
        result = {
            "success": True,
            "share_id": share.id,
            "quantity_bought": quantity,
            "total_cost": total_cost,
            "remaining_volume": share.remaining_volume,
            "remaining_cash": round(float(company.cash), 2),
            "treasury_cash": round(float(treasury.cash), 2),
        }
        await cls._record_operation(session, operation_key, "BUY", payload, result)
        if commit:
            await session.commit()
        return result

    @classmethod
    async def sell(
        cls,
        session: AsyncSession,
        company: NatCompany,
        share_id: int,
        quantity: int,
        *,
        operation_key: str,
        commit: bool = True,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        payload = {"company_id": company.id, "share_id": share_id, "quantity": quantity}
        replay = await cls._replay(session, operation_key, "SELL", payload)
        if replay is not None:
            return replay
        if quantity <= 0:
            raise ValueError("Share quantity must be positive.")
        now = now or get_game_now()
        treasury = await StateTreasuryService.get_or_create(session, commit=False, for_update=True)
        replay = await cls._replay(session, operation_key, "SELL", payload)
        if replay is not None:
            return replay
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company.id).with_for_update()
            .execution_options(populate_existing=True)
        )
        share = await session.scalar(select(NatStateShare).where(NatStateShare.id == share_id).with_for_update())
        if not company:
            raise ValueError("Company not found.")
        if not share:
            raise ValueError("State share issue not found.")
        holding = await session.scalar(select(NatStateShareHolding).where(
            NatStateShareHolding.share_id == share_id,
            NatStateShareHolding.company_id == company.id,
        ).with_for_update())
        if not holding or holding.quantity < quantity:
            raise ValueError("Insufficient shares held.")
        total_proceeds = round(float(share.issue_price) * quantity, 2)
        if float(treasury.cash) < total_proceeds:
            raise ValueError(
                f"Treasury cannot redeem this position. Required: {total_proceeds}, available: {treasury.cash}."
            )

        old_quantity = holding.quantity
        cost_basis = float(holding.invested_cash) * quantity / old_quantity
        company.cash = round(float(company.cash) + total_proceeds, 2)
        treasury.cash = round(float(treasury.cash) - total_proceeds, 2)
        treasury.updated_at = now
        holding.quantity -= quantity
        holding.invested_cash = round(max(0.0, float(holding.invested_cash) - cost_basis), 2)
        holding.updated_at = now
        share.remaining_volume = min(share.total_volume, share.remaining_volume + quantity)
        await session.flush()
        result = {
            "success": True,
            "share_id": share.id,
            "quantity_sold": quantity,
            "total_proceeds": total_proceeds,
            "remaining_shares": holding.quantity,
            "remaining_volume": share.remaining_volume,
            "remaining_cash": round(float(company.cash), 2),
            "treasury_cash": round(float(treasury.cash), 2),
        }
        await cls._record_operation(session, operation_key, "SELL", payload, result)
        if commit:
            await session.commit()
        return result

    @staticmethod
    async def list_shares(
        session: AsyncSession, company_id: int | None = None
    ) -> list[dict[str, Any]]:
        statement = select(NatStateShare).order_by(NatStateShare.created_at.desc(), NatStateShare.id.desc())
        shares = (await session.execute(statement)).scalars().all()
        quantities: dict[int, int] = {}
        if company_id is not None:
            rows = await session.execute(select(
                NatStateShareHolding.share_id, NatStateShareHolding.quantity
            ).where(NatStateShareHolding.company_id == company_id))
            quantities = {int(share_id): int(quantity) for share_id, quantity in rows.all()}
        return [{
            "id": share.id,
            "title": share.title,
            "purpose": share.purpose,
            "total_volume": share.total_volume,
            "remaining_volume": share.remaining_volume,
            "issue_price": round(float(share.issue_price), 2),
            "redemption_price": round(float(share.issue_price), 2),
            "projected_annual_profit": round(float(share.projected_annual_profit), 2),
            "dividend_rate_pct": share.dividend_rate_pct,
            "is_active": share.is_active,
            "shares_held": quantities.get(share.id, 0),
            "created_at": share.created_at.isoformat(),
        } for share in shares]

__all__ = ["StateShareIdempotencyConflict", "StateShareService"]
