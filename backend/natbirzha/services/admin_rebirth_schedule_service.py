"""Creator-only delayed rebirths with a stock warning and an audit trail."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from html import escape

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.natbirzha.config import get_game_now
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.creator import NatCreatorAuditLog
from backend.natbirzha.models.inventory import NatInventory
from backend.natbirzha.models.joint_factories import (
    NatJointFactory,
    NatJointFactoryProposal,
    NatJointFactorySettlement,
)
from backend.natbirzha.models.admin_rebirth import NatAdminRebirthSchedule
from backend.natbirzha.services.access_control import get_creator_tg_ids
from backend.natbirzha.services.event_broadcaster import EventBroadcaster
from backend.natbirzha.services.rebirth_service import RebirthService
from backend.natbirzha.services.progression_service import MAX_REBIRTHS

logger = logging.getLogger(__name__)
WARNING_TEXT = (
    "После перерождения акции останутся у владельцев, их цена снизится на 99%, "
    "а дивиденды продолжат начисляться. Автоматического выкупа не будет. "
    "Акции можно продать через обычную биржу до указанного времени."
)


def _warning_message(companies: list[NatCompany], execute_at: datetime) -> str:
    names = " и ".join(
        f"<b>{escape(company.name)}</b> [{escape(company.ticker or '')}]"
        for company in companies
    )
    time_text = execute_at.strftime("%H:%M:%S %d.%m.%Y")
    return (
        "⚠️ <b>Предупреждение акционерам</b>\n\n"
        f"Через 10 минут перерождение совершат компании {names}.\n"
        f"Ориентировочное время: {time_text} (MSK+2).\n\n"
        f"{escape(WARNING_TEXT)}"
    )


async def _move_stock_to_inventory(
    session: AsyncSession, company_id: int, stock: dict[str, float]
) -> None:
    for item_id, raw_quantity in (stock or {}).items():
        quantity = max(0.0, float(raw_quantity or 0.0))
        if quantity <= 0:
            continue
        inventory = await session.scalar(select(NatInventory).where(
            NatInventory.company_id == company_id,
            NatInventory.item_id == item_id,
        ).with_for_update())
        if inventory is None:
            session.add(NatInventory(
                company_id=company_id, item_id=item_id, quantity=quantity,
                reserved_quantity=0.0, avg_cost_basis=0.0,
            ))
            continue
        before = max(0.0, float(inventory.quantity or 0.0))
        after = before + quantity
        inventory.avg_cost_basis = round(
            before * float(inventory.avg_cost_basis or 0.0) / max(after, 1e-9), 6
        )
        inventory.quantity = round(after, 8)


async def _close_joint_factories(
    session: AsyncSession, company_ids: set[int], now: datetime
) -> None:
    from backend.natbirzha.services.joint_factory_settlement_service import (
        JointFactorySettlementService,
    )

    factory_filter = or_(
        NatJointFactory.company_a_id.in_(company_ids),
        NatJointFactory.company_b_id.in_(company_ids),
    )
    factory_ids = list((await session.scalars(
        select(NatJointFactory.id).where(factory_filter)
    )).all())
    if not factory_ids:
        return

    for factory_id in factory_ids:
        factory = await session.get(NatJointFactory, factory_id)
        if factory and factory.status == "ACTIVE":
            await JointFactorySettlementService.settle_factory(session, factory_id, now=now)

    factories = list((await session.scalars(
        select(NatJointFactory).where(NatJointFactory.id.in_(factory_ids))
        .order_by(NatJointFactory.id).with_for_update()
    )).all())
    proposals = list((await session.scalars(select(NatJointFactoryProposal).where(
        or_(
            NatJointFactoryProposal.factory_id.in_(factory_ids),
            NatJointFactoryProposal.proposer_company_id.in_(company_ids),
            NatJointFactoryProposal.partner_company_id.in_(company_ids),
        ),
        NatJointFactoryProposal.status == "PENDING",
    ).with_for_update())).all())
    for proposal in proposals:
        proposal.status = "CANCELLED"
        proposal.responded_at = now

    for factory in factories:
        if int(factory.company_a_id) not in company_ids:
            await _move_stock_to_inventory(session, factory.company_a_id, factory.stock_a_json)
        if int(factory.company_b_id) not in company_ids:
            await _move_stock_to_inventory(session, factory.company_b_id, factory.stock_b_json)
        factory.status = "BREACHED"
        factory.closed_at = now
        factory.last_settled_at = now
        factory.stock_a_json = {}
        factory.stock_b_json = {}


class AdminRebirthScheduleService:
    DELAY = timedelta(minutes=10)
    TARGET_TG_IDS = frozenset({1053722876, 7755842535})

    @classmethod
    async def schedule(
        cls,
        session: AsyncSession,
        target_tg_ids: list[int],
        *,
        actor_tg_id: int,
        operation_key: str,
    ) -> dict:
        targets = sorted({int(value) for value in target_tg_ids})
        if len(target_tg_ids) != 2 or len(targets) != 2:
            raise ValueError("Нужно указать ровно двух разных администраторов")
        if set(targets) != cls.TARGET_TG_IDS:
            raise ValueError("Эта отложенная операция настроена только для двух согласованных администраторов")
        if not set(targets).issubset(get_creator_tg_ids()):
            raise ValueError("Перерождение через администратора разрешено только админам игры")

        users = list((await session.scalars(
            select(User).where(User.tg_id.in_(targets)).order_by(User.tg_id)
        )).all())
        if len(users) != 2:
            raise ValueError("Не удалось найти оба аккаунта администраторов")
        companies = list((await session.scalars(
            select(NatCompany).where(NatCompany.user_id.in_([user.id for user in users]))
            .order_by(NatCompany.id).with_for_update()
        )).all())
        if len(companies) != 2:
            raise ValueError("У каждого администратора должна быть компания")
        user_by_id = {int(user.id): user for user in users}
        tg_by_company = {int(company.id): int(user_by_id[company.user_id].tg_id) for company in companies}

        existing = await session.scalar(select(NatAdminRebirthSchedule).where(
            NatAdminRebirthSchedule.operation_key == operation_key
        ))
        if existing is not None:
            if set(map(int, existing.company_ids_json or [])) != {int(c.id) for c in companies}:
                raise ValueError("Ключ идемпотентности уже использован для других компаний")
            return {
                "success": existing.status in ("PENDING", "COMPLETED"),
                "operation_key": existing.operation_key,
                "status": existing.status,
                "warning_sent_at": existing.warning_sent_at.isoformat() if existing.warning_sent_at else None,
                "execute_at": existing.execute_at.isoformat() if existing.execute_at else None,
                "companies": [
                    {"company_id": company.id, "telegram_id": tg_by_id,
                     "name": company.name}
                    for company in companies
                    for tg_by_id in [tg_by_company.get(int(company.id))]
                ],
                "dm_recipient_count": 0,
                "dm_delivered": 0,
            }

        expected_counts: dict[str, int] = {}
        for company in companies:
            rank = int(company.rebirth_count or 0)
            if rank >= MAX_REBIRTHS:
                raise ValueError(f"У компании «{company.name}» уже завершены все перерождения")
            if company.is_bankrupt:
                raise ValueError(f"Компания «{company.name}» находится в банкротстве")
            status = await RebirthService.snapshot(session, company)
            allowed = {
                f"Откройте «{status['terminal_name']}»",
                "Закройте совместный завод и заберите свою продукцию",
            }
            unexpected = [reason for reason in status["reasons"] if reason not in allowed]
            if unexpected:
                raise ValueError(f"«{company.name}»: " + " · ".join(unexpected))
            expected_counts[str(company.id)] = rank

        active = list((await session.scalars(select(NatAdminRebirthSchedule).where(
            NatAdminRebirthSchedule.status.in_(("AWAITING_WARNING", "PENDING")),
        ).with_for_update())).all())
        target_company_ids = {int(company.id) for company in companies}
        if any(target_company_ids.intersection(map(int, row.company_ids_json or [])) for row in active):
            raise ValueError("Для одной из компаний уже назначено перерождение")

        operation = NatAdminRebirthSchedule(
            operation_key=operation_key,
            company_ids_json=sorted(target_company_ids),
            expected_counts_json=expected_counts,
            created_by_tg_id=int(actor_tg_id),
            status="AWAITING_WARNING",
            created_at=get_game_now(),
        )
        session.add(operation)
        await session.flush()
        session.add(NatCreatorAuditLog(
            actor_id=int(actor_tg_id), action="ADMIN_REBIRTH_SCHEDULED",
            target_type="companies", target_id=operation.operation_key,
            details=f"telegram_ids={targets}; warning required; 10-minute delay",
            created_at=get_game_now(),
        ))
        await session.commit()

        if not await EventBroadcaster.send_message(_warning_message(companies, get_game_now() + cls.DELAY)):
            operation.status = "FAILED"
            operation.failure_reason = "Не удалось отправить предупреждение в общий чат"
            await session.commit()
            raise RuntimeError(operation.failure_reason)

        sent_at = get_game_now()
        operation.warning_sent_at = sent_at
        operation.execute_at = sent_at + cls.DELAY
        operation.status = "PENDING"
        await session.commit()

        recipient_ids = await RebirthService._notice_recipients(session)
        bot = EventBroadcaster._get_bot()
        delivered = 0
        if bot is not None:
            direct_text = (
                "⚠️ Предупреждение акционерам\n\n"
                + " и ".join(f"{company.name} [{company.ticker}]" for company in companies)
                + " переродятся через 10 минут. Акции останутся у владельцев, цена снизится на 99%, "
                "дивиденды продолжат начисляться. Автоматического выкупа нет; до перерождения "
                "продать акции можно через обычную биржу."
            )
            semaphore = asyncio.Semaphore(15)

            async def send_one(telegram_id: int) -> bool:
                async with semaphore:
                    try:
                        await bot.send_message(chat_id=telegram_id, text=direct_text, parse_mode=None)
                        return True
                    except Exception:
                        return False

            delivered = sum(await asyncio.gather(*(send_one(tg_id) for tg_id in recipient_ids)))

        return {
            "success": True,
            "operation_key": operation.operation_key,
            "status": operation.status,
            "warning_sent_at": sent_at.isoformat(),
            "execute_at": operation.execute_at.isoformat(),
            "companies": [
                {"company_id": company.id, "telegram_id": tg_by_company[company.id], "name": company.name}
                for company in companies
            ],
            "dm_recipient_count": len(recipient_ids),
            "dm_delivered": delivered,
        }

    @classmethod
    async def process_due(cls, session: AsyncSession, *, now: datetime | None = None) -> dict:
        current = now or get_game_now()
        due = list((await session.scalars(select(NatAdminRebirthSchedule).where(
            NatAdminRebirthSchedule.status == "PENDING",
            NatAdminRebirthSchedule.warning_sent_at.is_not(None),
            NatAdminRebirthSchedule.execute_at <= current,
        ).order_by(NatAdminRebirthSchedule.execute_at, NatAdminRebirthSchedule.id)
            .limit(10).with_for_update(skip_locked=True))).all())
        completed = failed = 0
        for operation in due:
            operation_id = operation.id
            try:
                result = await cls._execute(session, operation, current)
                operation.status = "COMPLETED"
                operation.result_json = result
                operation.completed_at = current
                session.add(NatCreatorAuditLog(
                    actor_id=int(operation.created_by_tg_id), action="ADMIN_REBIRTH_COMPLETED",
                    target_type="companies", target_id=operation.operation_key,
                    details=f"companies={operation.company_ids_json}; result={result}",
                    created_at=current,
                ))
                await session.commit()
                completed += 1
                await EventBroadcaster.send_message(
                    "✅ Перерождение завершено для компаний: "
                    + ", ".join(item["company_name"] for item in result["companies"])
                    + ". Акции и начисление дивидендов сохранены; цены обновлены."
                )
            except Exception as exc:
                logger.exception("Admin rebirth schedule %s failed", operation_id)
                await session.rollback()
                failed_operation = await session.get(NatAdminRebirthSchedule, operation_id)
                if failed_operation and failed_operation.status == "PENDING":
                    failed_operation.status = "FAILED"
                    failed_operation.failure_reason = str(exc)[:2000]
                    failed_operation.completed_at = current
                    await session.commit()
                failed += 1
        return {"due": len(due), "completed": completed, "failed": failed}

    @staticmethod
    async def _execute(
        session: AsyncSession,
        operation: NatAdminRebirthSchedule,
        current: datetime,
    ) -> dict:
        companies = list((await session.scalars(select(NatCompany).where(
            NatCompany.id.in_(operation.company_ids_json)
        ).order_by(NatCompany.id).with_for_update())).all())
        if len(companies) != len(operation.company_ids_json):
            raise ValueError("Компания из запланированного перерождения больше не найдена")
        for company in companies:
            expected = int(operation.expected_counts_json[str(company.id)])
            if int(company.rebirth_count or 0) != expected:
                raise ValueError(f"У компании «{company.name}» изменился ранг перерождения")

        await _close_joint_factories(session, {int(c.id) for c in companies}, current)
        results = []
        for company in companies:
            rebirth = await RebirthService.perform(
                session,
                company.id,
                expected_count=int(operation.expected_counts_json[str(company.id)]),
                now=current,
                creator_override=True,
            )
            results.append({"company_id": company.id, "company_name": company.name, **rebirth})
        return {"companies": results}


__all__ = ["AdminRebirthScheduleService"]
