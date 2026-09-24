"""Automation and scheduled orchestration mixed into the production state machine."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.config import get_game_now, normalize_dt
from backend.natbirzha.models.company import NatCompany, NatFactory

MAX_AUTOMATION_CATCH_UP_CYCLES = 500


class ProductionAutomationMixin:
    @classmethod
    async def set_automation(
        cls,
        session: AsyncSession,
        company: NatCompany,
        factory_id: int,
        enabled: bool,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        async with cls._get_lock(factory_id):
            locked_company = (await session.execute(
                select(NatCompany).where(NatCompany.id == company.id)
                .with_for_update().execution_options(populate_existing=True)
            )).scalar_one_or_none()
            if not locked_company:
                return {"success": False, "reason": "company_not_found"}
            factory = (await session.execute(
                select(NatFactory).where(
                    NatFactory.id == factory_id,
                    NatFactory.company_id == company.id,
                ).with_for_update().execution_options(populate_existing=True)
            )).scalar_one_or_none()
            if not factory:
                return {"success": False, "reason": "factory_not_found"}
            if enabled:
                if factory.automation_level < 1:
                    return {
                        "success": False,
                        "reason": "automation_upgrade_required",
                        "required_automation_level": 1,
                    }
                if locked_company.level < 6:
                    return {
                        "success": False,
                        "reason": "company_level_required",
                        "required_level": 6,
                    }
                current = normalize_dt(now or get_game_now())
                factory.automation_enabled = True
                factory.automation_pause_reason = None
                if factory.cycle_ready_at and current < normalize_dt(factory.cycle_ready_at):
                    factory.automation_status = "RUNNING"
                elif factory.cycle_ready_at:
                    factory.automation_status = "WAITING_COLLECTION"
                else:
                    factory.automation_status = "IDLE"
            else:
                factory.automation_enabled = False
                factory.automation_status = "MANUAL"
                factory.automation_pause_reason = None
            await session.flush()
            return {
                "success": True,
                "factory_id": factory.id,
                "automation_enabled": factory.automation_enabled,
                "automation_level": factory.automation_level,
                "automation_status": factory.automation_status,
                "automation_pause_reason": factory.automation_pause_reason,
            }

    @classmethod
    async def _catch_up_automation_locked(
        cls,
        session: AsyncSession,
        company: NatCompany,
        factory: NatFactory,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Advance automated cycles against their saved deadlines, within a bound."""
        current = normalize_dt(now or get_game_now())
        if not factory.automation_enabled:
            factory.automation_status = "MANUAL"
            factory.automation_pause_reason = None
            return {"success": True, "completed_cycles": 0, "started_cycles": 0}

        if factory.automation_level < 1 or company.level < 6:
            reason = "automation_upgrade_required" if factory.automation_level < 1 else "company_level_required"
            factory.automation_status = "WAITING_INPUTS"
            factory.automation_pause_reason = reason
            return {
                "success": False,
                "completed_cycles": 0,
                "started_cycles": 0,
                "reason": reason,
            }

        completed = 0
        started = 0
        if not factory.cycle_ready_at:
            first_start = await cls._start_cycle_locked(
                session, company, factory, None, current
            )
            if not first_start.get("success"):
                reason = str(first_start.get("reason", "automation_start_failed"))
                factory.automation_status = "WAITING_INPUTS"
                factory.automation_pause_reason = reason
                await session.flush()
                return {
                    "success": False,
                    "completed_cycles": 0,
                    "started_cycles": 0,
                    "reason": reason,
                }
            started += 1

        for _ in range(MAX_AUTOMATION_CATCH_UP_CYCLES):
            if not factory.cycle_ready_at or not factory.current_recipe:
                break
            ready_at = normalize_dt(factory.cycle_ready_at)
            if current < ready_at:
                break

            result = await cls._complete_cycle_locked(
                session, company, factory, ready_at
            )
            if not result.get("success"):
                reason = str(result.get("reason", "automation_completion_failed"))
                factory.automation_status = (
                    "WAITING_COLLECTION" if reason == "inventory_overflow" else "WAITING_INPUTS"
                )
                factory.automation_pause_reason = reason
                await session.flush()
                return {
                    "success": False,
                    "completed_cycles": completed,
                    "started_cycles": started,
                    "reason": reason,
                }
            completed += 1

            # Backdate the next start to the previous deadline. This keeps
            # short-cycle factories from losing production to scheduler drift.
            next_start = await cls._start_cycle_locked(
                session, company, factory, None, ready_at
            )
            if not next_start.get("success"):
                reason = str(next_start.get("reason", "automation_start_failed"))
                factory.automation_status = (
                    "WAITING_COLLECTION"
                    if reason == "inventory_overflow"
                    else "WAITING_INPUTS"
                )
                factory.automation_pause_reason = reason
                await session.flush()
                return {
                    "success": True,
                    "completed_cycles": completed,
                    "started_cycles": started,
                    "reason": reason,
                }
            started += 1

        if factory.cycle_ready_at:
            factory.automation_status = "RUNNING"
            factory.automation_pause_reason = None
        await session.flush()
        return {
            "success": True,
            "completed_cycles": completed,
            "started_cycles": started,
        }

    @classmethod
    async def execute_manual_produce(
        cls,
        session: AsyncSession,
        company_id: int,
        factory_id: int,
        recipe_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        async with cls._get_lock(factory_id):
            company = await session.scalar(
                select(NatCompany).where(NatCompany.id == company_id)
                .with_for_update().execution_options(populate_existing=True)
            )
            factory = await session.scalar(
                select(NatFactory).where(
                    NatFactory.id == factory_id,
                    NatFactory.company_id == company_id,
                    NatFactory.is_active == True,
                ).with_for_update().execution_options(populate_existing=True)
            )
            if not company or not factory or company.is_bankrupt:
                return {"success": False, "reason": "factory_not_found"}
            now = normalize_dt(get_game_now())
            if factory.cycle_ready_at:
                if now >= normalize_dt(factory.cycle_ready_at):
                    return await cls._complete_cycle_locked(session, company, factory, now)
                return {
                    "success": False,
                    "reason": "cycle_in_progress",
                    "remaining_seconds": max(1, int((normalize_dt(factory.cycle_ready_at) - now).total_seconds())),
                }
            return await cls._start_cycle_locked(session, company, factory, recipe_id, now)

    @classmethod
    async def catch_up_company(
        cls,
        session: AsyncSession,
        company_id: int,
        now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Settle elapsed cycles one factory transaction at a time."""
        current = normalize_dt(now or get_game_now())
        result = await session.execute(
            select(NatFactory.id).where(
                NatFactory.company_id == company_id,
                NatFactory.is_active == True,
            )
        )
        completed: List[Dict[str, Any]] = []
        for factory_id in result.scalars().all():
            async with cls._get_lock(factory_id):
                company = await session.scalar(
                    select(NatCompany).where(NatCompany.id == company_id)
                    .with_for_update().execution_options(populate_existing=True)
                )
                if not company or company.is_bankrupt:
                    await session.rollback()
                    break
                locked_factory = await session.scalar(
                    select(NatFactory).where(
                        NatFactory.id == factory_id,
                        NatFactory.company_id == company_id,
                        NatFactory.is_active == True,
                    ).with_for_update().execution_options(populate_existing=True)
                )
                if locked_factory and not locked_factory.automation_enabled:
                    if locked_factory.cycle_ready_at and current >= normalize_dt(locked_factory.cycle_ready_at):
                        completion = await cls._complete_cycle_locked(
                            session, company, locked_factory, current
                        )
                        if completion.get("success"):
                            completed.append(completion)
                elif locked_factory:
                    transition = await cls._catch_up_automation_locked(
                        session, company, locked_factory, current
                    )
                    if transition.get("completed_cycles", 0) > 0:
                        completed.append(transition)
                # Release the company row lock before waiting for another
                # factory's process-local lock on the next iteration.
                await session.commit()
        return completed

    @classmethod
    async def has_due_factory_cycles(
        cls,
        session: AsyncSession,
        company_id: int,
        now: Optional[datetime] = None,
    ) -> bool:
        """Return whether an active factory still has an elapsed cycle to settle."""
        current = normalize_dt(now or get_game_now())
        result = await session.execute(
            select(NatFactory.cycle_ready_at).where(
                NatFactory.company_id == company_id,
                NatFactory.is_active == True,
                NatFactory.cycle_ready_at.is_not(None),
            )
        )
        return any(
            normalize_dt(ready_at) <= current
            for (ready_at,) in result.all()
        )

    @classmethod
    async def process_global_scheduled_tick(
        cls, session: AsyncSession, now: Optional[datetime] = None
    ) -> Dict[str, Any]:
        current = normalize_dt(now or get_game_now())
        result = await session.execute(
            select(NatFactory.id, NatFactory.company_id)
            .join(NatCompany, NatFactory.company_id == NatCompany.id)
            .where(NatFactory.is_active == True, NatCompany.is_bankrupt == False)
        )
        completed = 0
        started = 0
        for factory_id, company_id in result.all():
            async with cls._get_lock(factory_id):
                locked_company = await session.scalar(
                    select(NatCompany).where(
                        NatCompany.id == company_id,
                        NatCompany.is_bankrupt == False,
                    ).with_for_update().execution_options(populate_existing=True)
                )
                locked_factory = await session.scalar(
                    select(NatFactory).where(
                        NatFactory.id == factory_id,
                        NatFactory.company_id == company_id,
                        NatFactory.is_active == True,
                    ).with_for_update().execution_options(populate_existing=True)
                )
                if locked_factory and locked_company and not locked_factory.automation_enabled:
                    if locked_factory.cycle_ready_at and current >= normalize_dt(locked_factory.cycle_ready_at):
                        cycle_result = await cls._complete_cycle_locked(
                            session, locked_company, locked_factory, current
                        )
                        completed += int(bool(cycle_result.get("success")))
                elif locked_factory and locked_company:
                    transition = await cls._catch_up_automation_locked(
                        session, locked_company, locked_factory, current
                    )
                    completed += int(transition.get("completed_cycles", 0))
                    started += int(transition.get("started_cycles", 0))
                # A tick may visit many factories for one company. Commit each
                # before waiting for the next factory lock to avoid lock cycles.
                await session.commit()
        return {
            "success": True,
            "ticks_processed": completed + started,
            "cycles_completed": completed,
            "cycles_started": started,
        }



__all__ = ["ProductionAutomationMixin"]
