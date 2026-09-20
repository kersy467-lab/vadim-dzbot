from datetime import timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from backend.db.models import User
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany, NatFactory
from backend.natbirzha.models.market import NatMarketOrder
from backend.natbirzha.models.inventory import CANONICAL_ITEMS
from backend.natbirzha.models.military import NatTournament
from backend.natbirzha.models.premium import NatPremiumLedgerEntry
from backend.natbirzha.models.creator import (
    NatStateTreasury,
    NatCreatorAuditLog,
    NatMarketRestriction,
    NatMarketWarning,
    NatStateBond
)
from backend.natbirzha.services.military_service import MilitaryService
from backend.natbirzha.services.tournament_service import TournamentService
from backend.natbirzha.services.state_bond_service import StateBondService
from backend.natbirzha.services.state_treasury_service import StateTreasuryService

class CreatorService:
    @staticmethod
    async def get_or_create_treasury(
        session: AsyncSession, commit: bool = True
    ) -> NatStateTreasury:
        return await StateTreasuryService.get_or_create(session, commit=commit)

    @classmethod
    async def get_overview(cls, session: AsyncSession) -> Dict[str, Any]:
        treasury = await cls.get_or_create_treasury(session)
        comp_count = (await session.execute(select(func.count(NatCompany.id)))).scalar() or 0
        factory_count = (await session.execute(select(func.count(NatFactory.id)))).scalar() or 0
        active_orders = (await session.execute(
            select(func.count(NatMarketOrder.id)).where(NatMarketOrder.status == "ACTIVE")
        )).scalar() or 0
        active_restr = (await session.execute(
            select(func.count(NatMarketRestriction.id)).where(NatMarketRestriction.is_active == True)
        )).scalar() or 0
        active_bonds = (await session.execute(
            select(func.count(NatStateBond.id)).where(NatStateBond.is_active == True)
        )).scalar() or 0
        total_cash_circ = (await session.execute(select(func.sum(NatCompany.cash)))).scalar() or 0.0

        return {
            "treasury_cash": treasury.cash,
            "total_companies": comp_count,
            "total_factories": factory_count,
            "active_orders": active_orders,
            "active_restrictions": active_restr,
            "active_bonds": active_bonds,
            "cash_in_circulation": round(float(total_cash_circ), 2),
            "game_time": get_game_now().isoformat()
        }

    @staticmethod
    async def get_market_snapshot(session: AsyncSession) -> Dict[str, Any]:
        orders_res = await session.execute(
            select(NatMarketOrder)
            .where(NatMarketOrder.status == "ACTIVE")
            .order_by(NatMarketOrder.created_at.desc())
            .limit(50)
        )
        orders = [
            {
                "id": o.id, "company_id": o.company_id, "order_type": o.order_type,
                "item_id": o.item_id, "price": o.price, "remaining_qty": o.remaining_qty,
                "created_at": o.created_at.isoformat()
            }
            for o in orders_res.scalars().all()
        ]

        now = get_game_now()
        restr_res = await session.execute(
            select(NatMarketRestriction)
            .where(
                NatMarketRestriction.is_active == True,
                or_(NatMarketRestriction.expires_at == None, NatMarketRestriction.expires_at > now)
            )
            .order_by(NatMarketRestriction.created_at.desc())
        )
        restrictions = [
            {
                "id": r.id, "company_id": r.company_id, "item_id": r.item_id,
                "min_price": r.min_price, "max_price": r.max_price,
                "reason": r.reason, "actor_id": r.actor_id, "is_active": r.is_active,
                "expires_at": r.expires_at.isoformat() if r.expires_at else None,
                "created_at": r.created_at.isoformat()
            }
            for r in restr_res.scalars().all()
        ]

        warn_res = await session.execute(
            select(NatMarketWarning).order_by(NatMarketWarning.created_at.desc()).limit(20)
        )
        warnings = [
            {"id": w.id, "company_id": w.company_id, "reason": w.reason, "created_at": w.created_at.isoformat()}
            for w in warn_res.scalars().all()
        ]

        return {"orders": orders, "restrictions": restrictions, "warnings": warnings}

    @staticmethod
    async def add_warning(
        session: AsyncSession, actor_id: int, company_id: int, reason: str, commit: bool = True
    ) -> Dict[str, Any]:
        comp = await session.get(NatCompany, company_id)
        if not comp:
            raise ValueError("Company not found.")
        now = get_game_now()
        warning = NatMarketWarning(company_id=company_id, reason=reason, actor_id=actor_id, created_at=now)
        session.add(warning)

        log = NatCreatorAuditLog(
            actor_id=actor_id, action="WARNING_ISSUED", target_type="company",
            target_id=str(company_id), details=f"Причина: {reason}", created_at=now
        )
        session.add(log)
        if commit:
            await session.commit()
        else:
            await session.flush()
        return {"success": True, "warning_id": warning.id, "company_id": company_id}

    @staticmethod
    async def set_restriction(
        session: AsyncSession,
        actor_id: int,
        company_id: Optional[int],
        item_id: Optional[str],
        min_price: Optional[float],
        max_price: Optional[float],
        reason: str,
        duration_minutes: Optional[int] = None,
        commit: bool = True,
    ) -> Dict[str, Any]:
        if company_id is not None and not await session.get(NatCompany, company_id):
            raise ValueError("Company not found.")
        if item_id is not None and item_id not in CANONICAL_ITEMS:
            raise ValueError(f"Unknown item: {item_id}")
        if min_price is not None and min_price < 0:
            raise ValueError("Minimum price cannot be negative.")
        if max_price is not None and max_price < 0:
            raise ValueError("Maximum price cannot be negative.")
        if min_price is not None and max_price is not None and min_price > max_price:
            raise ValueError("Minimum price cannot exceed maximum price.")
        if duration_minutes is not None and duration_minutes <= 0:
            raise ValueError("Restriction duration must be positive.")

        now = get_game_now()
        expires_at = (now + timedelta(minutes=duration_minutes)) if duration_minutes else None

        restr = NatMarketRestriction(
            company_id=company_id,
            item_id=item_id,
            min_price=min_price,
            max_price=max_price,
            reason=reason,
            actor_id=actor_id,
            is_active=True,
            expires_at=expires_at,
            created_at=now
        )
        session.add(restr)

        log = NatCreatorAuditLog(
            actor_id=actor_id, action="RESTRICTION_SET", target_type="market",
            target_id=f"item:{item_id}|comp:{company_id}",
            details=f"Диапазон: [{min_price}, {max_price}] ₽. Причина: {reason}",
            created_at=now
        )
        session.add(log)
        if commit:
            await session.commit()
            await session.refresh(restr)
        else:
            await session.flush()
        return {
            "success": True, "restriction_id": restr.id, "min_price": min_price,
            "max_price": max_price, "expires_at": expires_at.isoformat() if expires_at else None
        }

    @staticmethod
    async def remove_restriction(
        session: AsyncSession, actor_id: int, restriction_id: int, commit: bool = True
    ) -> Dict[str, Any]:
        restr = await session.get(NatMarketRestriction, restriction_id)
        if not restr or not restr.is_active:
            raise ValueError("Active restriction not found.")
        restr.is_active = False

        log = NatCreatorAuditLog(
            actor_id=actor_id, action="RESTRICTION_REMOVED", target_type="restriction",
            target_id=str(restriction_id), details=f"Снято ограничение {restr.reason}", created_at=get_game_now()
        )
        session.add(log)
        if commit:
            await session.commit()
        else:
            await session.flush()
        return {"success": True, "removed_id": restriction_id}

    @staticmethod
    async def check_market_restriction(
        session: AsyncSession, company_id: int, item_id: str, price: float
    ) -> Tuple[bool, Optional[str]]:
        now = get_game_now()
        restr_res = await session.execute(
            select(NatMarketRestriction).where(
                NatMarketRestriction.is_active == True,
                or_(NatMarketRestriction.expires_at == None, NatMarketRestriction.expires_at > now),
                or_(NatMarketRestriction.company_id == None, NatMarketRestriction.company_id == company_id),
                or_(NatMarketRestriction.item_id == None, NatMarketRestriction.item_id == item_id)
            )
        )
        for r in restr_res.scalars().all():
            if r.min_price is not None and price < r.min_price:
                return False, f"Цена {price} ₽ ниже установленного государством минимума {r.min_price} ₽ ({r.reason})"
            if r.max_price is not None and price > r.max_price:
                return False, f"Цена {price} ₽ выше установленного государством максимума {r.max_price} ₽ ({r.reason})"
        return True, None

    @classmethod
    async def issue_bonds(
        cls, session: AsyncSession, actor_id: int, title: str, volume: int,
        face_value: float, coupon_rate: float, maturity_days: int, purpose: str,
        coupon_interval_days: int | None = None,
        commit: bool = True,
    ) -> Dict[str, Any]:
        return await StateBondService.issue(
            session, actor_id, title, volume, face_value, coupon_rate,
            maturity_days, purpose, commit=commit,
            coupon_interval_days=coupon_interval_days,
        )

    @classmethod
    async def buy_state_bonds(
        cls, session: AsyncSession, company: NatCompany, bond_id: int,
        quantity: int, commit: bool = True,
    ) -> Dict[str, Any]:
        return await StateBondService.buy(
            session, company, bond_id, quantity, commit=commit
        )

    @staticmethod
    async def get_company_bond_holdings(
        session: AsyncSession, company_id: int
    ) -> List[Dict[str, Any]]:
        return await StateBondService.holdings(session, company_id)

    @staticmethod
    async def get_bonds(session: AsyncSession) -> List[Dict[str, Any]]:
        return await StateBondService.list_bonds(session)

    @staticmethod
    async def launch_early_tournament(
        session: AsyncSession,
        actor_id: int,
        rewards: tuple[int, int, int] = (150, 100, 70),
        commit: bool = True,
    ) -> Dict[str, Any]:
        now = get_game_now()
        current = await session.scalar(
            select(NatTournament)
            .where(NatTournament.status == "ACTIVE")
            .order_by(NatTournament.id.desc())
            .limit(1)
        )
        if current is not None:
            raise ValueError("An active tournament already exists")
        new_tourn = await TournamentService.create_custom(
            session,
            now=now,
            created_by_user_id=actor_id,
            rewards=rewards,
        )
        res = {
            "status": "created",
            "tournament_id": new_tourn.id,
            "tournament_number": new_tourn.tournament_number,
            "finish_time": new_tourn.finish_time.isoformat(),
            "rewards_pvc": list(rewards),
        }
        log_detail = (
            f"Запущен пользовательский турнир #{new_tourn.tournament_number}; "
            f"награды {rewards[0]}/{rewards[1]}/{rewards[2]} PVC"
        )

        log = NatCreatorAuditLog(
            actor_id=actor_id, action="EARLY_TOURNAMENT_LAUNCH", target_type="tournament",
            target_id=str(res.get("tournament_id", "")), details=log_detail, created_at=now
        )
        session.add(log)
        if commit:
            await session.commit()
        else:
            await session.flush()
        return {"success": True, "result": res}

    @staticmethod
    async def get_audit_log(session: AsyncSession, limit: int = 50) -> List[Dict[str, Any]]:
        res = await session.execute(
            select(NatCreatorAuditLog).order_by(NatCreatorAuditLog.created_at.desc()).limit(limit)
        )
        return [
            {
                "id": l.id, "actor_id": l.actor_id, "action": l.action,
                "target_type": l.target_type, "target_id": l.target_id,
                "details": l.details, "created_at": l.created_at.isoformat()
            }
            for l in res.scalars().all()
        ]

    @staticmethod
    async def get_premium_ledger(
        session: AsyncSession,
        *,
        limit: int = 100,
        company_id: int | None = None,
    ) -> List[Dict[str, Any]]:
        """Creator-only transparent PVC journal; wallet mutations remain server-side."""
        query = (
            select(NatPremiumLedgerEntry, NatCompany, User)
            .join(NatCompany, NatCompany.id == NatPremiumLedgerEntry.company_id)
            .outerjoin(User, User.id == NatCompany.user_id)
            .order_by(NatPremiumLedgerEntry.id.desc())
            .limit(limit)
        )
        if company_id is not None:
            query = query.where(NatPremiumLedgerEntry.company_id == company_id)
        rows = (await session.execute(query)).all()
        reasons = {
            "tournament_reward": "Награда за турнир",
            "license_purchase": "Покупка или продление лицензии",
            "payment_confirmed": "Подтверждённый платёж",
        }
        return [
            {
                "id": entry.id,
                "company_id": company.id,
                "company_name": company.name,
                "telegram_name": user.display_name if user else None,
                "telegram_username": user.username if user else None,
                "amount": entry.amount,
                "balance_before": entry.balance_before,
                "balance_after": entry.balance_after,
                "operation_type": entry.operation_type,
                "reason": reasons.get(entry.operation_type, entry.operation_type.replace("_", " ")),
                "metadata": entry.metadata_json,
                "actor_user_id": entry.actor_user_id,
                "created_at": entry.created_at.isoformat(),
            }
            for entry, company, user in rows
        ]
