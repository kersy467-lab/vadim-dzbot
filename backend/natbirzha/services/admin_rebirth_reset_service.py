"""Repeat a first rebirth for the two authorized admins without raising its rank."""

from __future__ import annotations

import json

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.natbirzha.config import get_game_now, nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatCreatorAuditLog
from backend.natbirzha.models.rebirth import NatCompanyRebirth
from backend.natbirzha.models.company_aid import NatCompanyAidRequest
from backend.natbirzha.models.stocks import NatStock
from backend.natbirzha.services.access_control import get_creator_tg_ids
from backend.natbirzha.services.admin_rebirth_schedule_service import _close_joint_factories
from backend.natbirzha.services.rebirth_service import RebirthService


class AdminRebirthResetService:
    TARGET_TG_IDS = frozenset({1053722876, 7755842535})

    @classmethod
    async def reset_to_first_rebirth(
        cls,
        session: AsyncSession,
        target_tg_ids: list[int],
        *,
        actor_tg_id: int,
        operation_key: str,
    ) -> dict:
        targets = sorted({int(value) for value in target_tg_ids})
        creators = get_creator_tg_ids()
        if set(targets) != cls.TARGET_TG_IDS or len(target_tg_ids) != 2:
            raise ValueError("Сброс разрешён только для двух согласованных администраторов")
        if int(actor_tg_id) not in creators or not cls.TARGET_TG_IDS.issubset(creators):
            raise ValueError("Операция доступна только администраторам игры")

        previous = await session.scalar(select(NatCreatorAuditLog).where(
            NatCreatorAuditLog.action == "ADMIN_REBIRTH_PROGRESS_RESET",
            NatCreatorAuditLog.target_id == operation_key,
        ))
        if previous is not None:
            details = json.loads(previous.details or "{}")
            return {"success": True, "replayed": True, **details}

        users = list((await session.scalars(
            select(User).where(User.tg_id.in_(targets)).order_by(User.tg_id)
        )).all())
        if len(users) != 2:
            raise ValueError("Не удалось найти оба аккаунта администраторов")
        companies = list((await session.scalars(
            select(NatCompany).where(NatCompany.user_id.in_([user.id for user in users]))
            .order_by(NatCompany.id).with_for_update()
        )).all())
        if len(companies) != 2 or any(int(company.rebirth_count or 0) != 1 for company in companies):
            raise ValueError("У обеих компаний уже должен быть ровно один завершённый ребитх")
        for company in companies:
            existing_rank = await session.scalar(select(NatCompanyRebirth.id).where(
                NatCompanyRebirth.company_id == company.id,
                NatCompanyRebirth.rank == 1,
            ))
            if existing_rank is None:
                raise ValueError(f"Не найдена запись первого перерождения компании «{company.name}»")

        from backend.natbirzha.services.company_bootstrap import bootstrap_company_state
        from backend.natbirzha.services.company_reset_v2 import delete_company_complete_state
        from backend.natbirzha.services.idle_economy_service import IdleEconomyService
        from backend.natbirzha.services.state_treasury_service import StateTreasuryService
        from backend.natbirzha.services.tax_service import TaxService

        now = get_game_now()
        company_ids = {int(company.id) for company in companies}
        treasury = await StateTreasuryService.get_or_create(session, commit=False, for_update=True)
        await _close_joint_factories(session, company_ids, now)
        reset_results = []
        for company in companies:
            await IdleEconomyService.settle_company(session, company.id, now=now)
            company = await session.scalar(select(NatCompany).where(
                NatCompany.id == company.id
            ).with_for_update().execution_options(populate_existing=True))
            stock = await session.scalar(select(NatStock).where(
                NatStock.company_id == company.id
            ).with_for_update())
            stock_price = float(stock.current_price or 0.01) if stock else None
            tax = await TaxService.summary(session, company.id, now=now)
            tax_paid = round(float(tax["total_due"]) + float(tax["current_period_estimated_tax"]), 2)
            if float(company.cash) < tax_paid:
                raise ValueError(f"Для сброса компании «{company.name}» не хватает cash на налоги")

            await delete_company_complete_state(session, company.id, for_rebirth=True)
            await session.execute(update(NatCompanyAidRequest).where(
                NatCompanyAidRequest.company_id == company.id,
                NatCompanyAidRequest.status == "OPEN",
            ).values(status="CANCELLED"))
            company.level = 1
            company.xp = 0
            for field in (
                "mastery_xp", "mastery_rank", "mastery_points_spent", "mastery_industry",
                "mastery_logistics", "mastery_doctrine", "mastery_intelligence",
            ):
                setattr(company, field, 0)
            company.cash = float(nat_settings.STARTING_CASH)
            company.territory_tiles = int(nat_settings.STARTING_TERRITORY_TILES)
            company.max_territory = 20
            company.business_slot_capacity = 10
            company.business_slot_upgrade_ready_at = None
            company.military_rating = 1000
            company.is_bankrupt = False
            company.licensed_foreign_spec = None
            company.last_respec_at = None
            company.rebirth_count = 1
            company.last_rebirth_at = now
            company.rebirth_announcement_for_count = None
            company.updated_at = now
            treasury.cash = round(float(treasury.cash) + tax_paid, 2)
            await bootstrap_company_state(session, company, now=now)
            await session.flush()
            stock_reset = None
            if stock_price is not None:
                stock_reset = await RebirthService._rebase_stock(session, company, stock_price, now)
            reset_results.append({
                "company_id": company.id,
                "company_name": company.name,
                "rebirth_count": 1,
                "cash": company.cash,
                "tax_paid": tax_paid,
                "stock_rebase": stock_reset,
            })

        response = {"companies": reset_results, "operation_key": operation_key}
        session.add(NatCreatorAuditLog(
            actor_id=int(actor_tg_id),
            action="ADMIN_REBIRTH_PROGRESS_RESET",
            target_type="companies",
            target_id=operation_key,
            details=json.dumps(response, ensure_ascii=False, separators=(",", ":")),
            created_at=now,
        ))
        await session.commit()
        return {"success": True, **response}


__all__ = ["AdminRebirthResetService"]
