"""Server-validated active-production sessions for NATBIRZHA 2.0."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.next_game import NatNextGameCompany, NatNextGameFacility
from backend.natbirzha.models.next_game_active import (
    NatNextGameActiveInterval,
    NatNextGameActiveSession,
)
from backend.natbirzha.active_production_scene_catalog import scene_for_branch
from backend.natbirzha.next_game_catalog import find_next_game_branch
from backend.natbirzha.services.next_game_service.common import _utcnow
from backend.natbirzha.services.next_game_active_time import (
    ACTIVE_TIMEOUT_SECONDS, HEARTBEAT_SECONDS, IDLE_WARNING_SECONDS,
    MAX_ACTIVE_MULTIPLIER, MAX_HEARTBEAT_GAP_SECONDS, active_cycle_multiplier,
    active_multiplier_for_cycle, active_production_enabled, output_with_active_bonus,
)
from backend.natbirzha.services.active_production_minigame import (
    average_interval_multiplier, create_target_bars, multiplier_for_charge, timing_state,
)
from backend.natbirzha.services.next_game_active_input import process_active_input
_INPUT_ACTIONS = frozenset({"move", "pickup", "deliver", "interact", "tap"})


class NextGameActiveProductionService:
    """Creates timed sessions; game animation never writes economic rewards."""

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _active_now(row: NatNextGameActiveSession, now: datetime) -> bool:
        return (row.status == "ACTIVE" and row.expires_at > now
                and row.last_interaction_at + timedelta(seconds=ACTIVE_TIMEOUT_SECONDS) > now)

    @staticmethod
    async def _lock_economy(session: AsyncSession) -> None:
        from backend.natbirzha.services.next_game_service import NextGameService
        await NextGameService._lock_treasury_for_sqlite(session)

    @staticmethod
    async def _company(session: AsyncSession, owner_tg_id: int) -> NatNextGameCompany:
        company = await session.scalar(select(NatNextGameCompany).where(
            NatNextGameCompany.owner_tg_id == int(owner_tg_id),
        ).with_for_update())
        if company is None:
            raise ValueError("Сначала создайте компанию 2.0")
        return company

    @staticmethod
    async def _record_confirmed_tail(
        session: AsyncSession,
        row: NatNextGameActiveSession,
        now: datetime,
        reason: str,
        pulse_seq: int,
    ) -> None:
        gap = (now - row.last_ping_at).total_seconds()
        if gap <= 0 or gap > MAX_HEARTBEAT_GAP_SECONDS:
            return
        end = min(now, row.last_interaction_at + timedelta(seconds=ACTIVE_TIMEOUT_SECONDS))
        if end <= row.last_ping_at:
            return
        multiplier = average_interval_multiplier(
            row.last_ping_at, end, row.skill_charge, row.last_skill_tap_at,
        )
        session.add(NatNextGameActiveInterval(
            session_id=row.id,
            company_id=row.company_id,
            pulse_seq=max(1, pulse_seq),
            start_at=row.last_ping_at,
            end_at=end,
            reason=reason,
            output_multiplier=multiplier,
        ))

    @staticmethod
    async def _scene_facility(
        session: AsyncSession,
        company: NatNextGameCompany,
        branch_id: str,
    ) -> NatNextGameFacility:
        if branch_id not in (company.branch_path or []):
            raise ValueError("Можно открыть только построенное направление своей компании")
        facility = await session.scalar(select(NatNextGameFacility).where(
            NatNextGameFacility.company_id == company.id,
            NatNextGameFacility.branch_id == branch_id,
        ).with_for_update())
        if facility is None or find_next_game_branch(branch_id) is None:
            raise ValueError("Для активной сцены сначала постройте этот завод")
        return facility

    @staticmethod
    async def _snapshot(session: AsyncSession, owner_tg_id: int, now: datetime) -> dict:
        from backend.natbirzha.services.next_game_service import NextGameService
        return await NextGameService.snapshot(session, owner_tg_id, section="factories", now=now)

    @staticmethod
    def _scene_payload(snapshot: dict) -> list[dict]:
        company = snapshot.get("company") or {}
        return [{
            "branch_id": facility["branch_id"],
            "facility_id": facility["id"],
            "name": facility["name"],
            "level": facility["level"],
            "sector_id": company.get("sector_id"),
            "next_cycle_at": facility["next_cycle_at"],
            "status": facility["status"],
            "blocked_reason": facility["blocked_reason"],
            "scene": scene_for_branch(facility["branch_id"], company.get("sector_id", "")),
        } for facility in snapshot.get("facilities", [])]

    @classmethod
    async def config(cls, session: AsyncSession, owner_tg_id: int, *, now: datetime | None = None) -> dict:
        current = now or _utcnow()
        if not active_production_enabled():
            return {"enabled": False, "facilities": [], "production": None}
        company = await session.scalar(select(NatNextGameCompany).where(
            NatNextGameCompany.owner_tg_id == int(owner_tg_id),
        ))
        if company is None:
            return {"enabled": True, "facilities": [], "production": None}
        snapshot = await cls._snapshot(session, owner_tg_id, current)
        active = await session.scalar(select(NatNextGameActiveSession).where(
            NatNextGameActiveSession.company_id == company.id,
            NatNextGameActiveSession.status == "ACTIVE",
        ).order_by(NatNextGameActiveSession.started_at.desc()).with_for_update())
        if active and active.expires_at <= current:
            await cls._record_confirmed_tail(session, active, current, "expired", active.last_sequence + 1)
            active.status, active.ended_at, active.end_reason = "EXPIRED", current, "heartbeat_timeout"
        return {
            "enabled": True,
            "server_now": current.isoformat(),
            "facilities": cls._scene_payload(snapshot),
            "production": snapshot.get("production"),
            "current_session": cls._session_summary(active, current) if active else None,
        }

    @classmethod
    async def start(
        cls,
        session: AsyncSession,
        owner_tg_id: int,
        branch_id: str,
        *,
        now: datetime | None = None,
    ) -> dict:
        if not active_production_enabled():
            raise ValueError("Активное производство сейчас отключено")
        current = now or _utcnow()
        await cls._lock_economy(session)
        company = await cls._company(session, owner_tg_id)
        await cls._scene_facility(session, company, branch_id)
        previous_skill = await session.scalar(select(NatNextGameActiveSession).where(
            NatNextGameActiveSession.company_id == company.id,
            NatNextGameActiveSession.selected_branch_id == branch_id,
        ).order_by(NatNextGameActiveSession.started_at.desc()).limit(1))
        previous = list((await session.scalars(select(NatNextGameActiveSession).where(
            NatNextGameActiveSession.company_id == company.id,
            NatNextGameActiveSession.status == "ACTIVE",
        ).with_for_update())).all())
        for old in previous:
            await cls._record_confirmed_tail(session, old, current, "replaced", old.last_sequence + 1)
            old.status, old.ended_at, old.end_reason = "STOPPED", current, "replaced"

        token = secrets.token_urlsafe(32)
        row = NatNextGameActiveSession(
            id=str(uuid4()), company_id=company.id, owner_tg_id=int(owner_tg_id),
            sector_id=company.sector_id or "", selected_branch_id=branch_id,
            session_token_hash=cls._token_hash(token), status="ACTIVE",
            started_at=current, last_ping_at=current, last_interaction_at=current,
            expires_at=current + timedelta(seconds=ACTIVE_TIMEOUT_SECONDS),
            last_sequence=0, last_user_input_counter=0, scene_version=1,
            skill_charge=max(0, min(16, int(previous_skill.skill_charge))) if previous_skill else 0,
            hit_streak=max(0, int(previous_skill.hit_streak)) if previous_skill else 0,
            last_skill_tap_at=previous_skill.last_skill_tap_at if previous_skill else None,
            wheel_angle=float(secrets.randbelow(36_000)) / 100,
            wheel_direction=1 if secrets.randbelow(2) else -1,
            target_angle=float(secrets.randbelow(36_000)) / 100,
            target_bars_json=json.dumps(create_target_bars(), separators=(",", ":")),
        )
        session.add(row)
        await session.flush()
        snapshot = await cls._snapshot(session, owner_tg_id, current)
        return {
            "session_id": row.id,
            "session_token": token,
            "server_now": current.isoformat(),
            "heartbeat_seconds": HEARTBEAT_SECONDS,
            "active_timeout_seconds": ACTIVE_TIMEOUT_SECONDS,
            "warning_after_seconds": IDLE_WARNING_SECONDS,
            "selected_branch_id": branch_id,
            "timing": timing_state(row, current),
            "facilities": cls._scene_payload(snapshot),
            "production": snapshot.get("production"),
        }

    @classmethod
    async def _owned_session(
        cls, session: AsyncSession, owner_tg_id: int, session_id: str, token: str,
    ) -> NatNextGameActiveSession:
        row = await session.scalar(select(NatNextGameActiveSession).where(
            NatNextGameActiveSession.id == session_id,
            NatNextGameActiveSession.owner_tg_id == int(owner_tg_id),
        ).with_for_update())
        if row is None or not hmac.compare_digest(row.session_token_hash, cls._token_hash(token)):
            raise ValueError("Активная сессия не найдена или уже закрыта")
        return row

    @staticmethod
    def _session_summary(row: NatNextGameActiveSession | None, now: datetime) -> dict | None:
        if row is None:
            return None
        age = max(0, int((now - row.last_interaction_at).total_seconds()))
        return {
            "session_id": row.id,
            "selected_branch_id": row.selected_branch_id,
            "status": row.status,
            "active": NextGameActiveProductionService._active_now(row, now),
            "last_valid_interaction_age": age,
            "timing": timing_state(row, now),
        }

    @classmethod
    async def pulse(
        cls,
        session: AsyncSession,
        owner_tg_id: int,
        session_id: str,
        token: str,
        sequence: int,
        scene_action: str,
        user_input_counter: int,
        *,
        tap_at_ms: int | None = None,
        now: datetime | None = None,
    ) -> dict:
        current = now or _utcnow()
        await cls._lock_economy(session)
        row = await cls._owned_session(session, owner_tg_id, session_id, token)
        company = await cls._company(session, owner_tg_id)
        facility = await session.scalar(select(NatNextGameFacility.id).where(
            NatNextGameFacility.company_id == company.id,
            NatNextGameFacility.branch_id == row.selected_branch_id,
        ))
        if (company.id != row.company_id or company.sector_id != row.sector_id
                or row.selected_branch_id not in (company.branch_path or []) or facility is None):
            await cls._record_confirmed_tail(session, row, current, "invalidated", row.last_sequence + 1)
            row.status, row.ended_at, row.end_reason = "STOPPED", current, "company_changed"
            await session.flush()
            return {"active": False, "status": row.status, "reason": row.end_reason}
        if row.status != "ACTIVE":
            return {"active": False, "status": row.status, "reason": row.end_reason}
        if row.expires_at <= current:
            await cls._record_confirmed_tail(session, row, current, "expired", row.last_sequence + 1)
            row.status, row.ended_at, row.end_reason = "EXPIRED", current, "heartbeat_timeout"
            await session.flush()
            return {"active": False, "status": row.status, "reason": row.end_reason}
        if sequence <= row.last_sequence:
            return cls._session_summary(row, current) | {
                "duplicate": True, "next_heartbeat_seconds": HEARTBEAT_SECONDS,
                "tap_result": None,
            }
        if scene_action not in _INPUT_ACTIONS | {"idle"}:
            raise ValueError("Такое событие сцены не поддерживается")

        await cls._record_confirmed_tail(session, row, current, "heartbeat", sequence)
        tap_result = process_active_input(
            row, current, scene_action, user_input_counter, tap_at_ms,
        )
        legacy_input = (
            scene_action in {"pickup", "deliver", "interact"}
            and user_input_counter > row.last_user_input_counter
        )
        if legacy_input:
            row.last_interaction_at = current
            row.last_user_input_counter = user_input_counter
        row.last_ping_at = current
        row.last_sequence = sequence
        row.expires_at = current + timedelta(seconds=ACTIVE_TIMEOUT_SECONDS)
        active = cls._active_now(row, current)
        snapshot = None if scene_action == "tap" else await cls._snapshot(session, owner_tg_id, current)
        working = int((snapshot.get("production") or {}).get("active", 0)) if snapshot else None
        total = int((snapshot.get("production") or {}).get("total", 0)) if snapshot else None
        next_cycles = [facility.get("next_cycle_at") for facility in snapshot.get("facilities", [])
                       if facility.get("next_cycle_at")] if snapshot else []
        age = max(0, int((current - row.last_interaction_at).total_seconds()))
        return {
            "status": row.status,
            "active": active,
            "server_now": current.isoformat(),
            "next_heartbeat_seconds": HEARTBEAT_SECONDS,
            "multiplier_now": multiplier_for_charge(row.skill_charge) if active else 1.0,
            "timing": timing_state(row, current),
            "tap_result": tap_result,
            "last_valid_interaction_age": age,
            "idle_warning": IDLE_WARNING_SECONDS <= age < ACTIVE_TIMEOUT_SECONDS,
            "working_facilities": working,
            "total_facilities": total,
            "nearest_cycle_at": min(next_cycles) if next_cycles else None,
            "production_summary": snapshot.get("production") if snapshot else None,
        }

    @classmethod
    async def finish(
        cls,
        session: AsyncSession,
        owner_tg_id: int,
        session_id: str,
        token: str,
        *,
        status: str = "STOPPED",
        reason: str = "user_exit",
        now: datetime | None = None,
    ) -> dict:
        if status not in {"PAUSED", "STOPPED"}:
            raise ValueError("Недопустимый статус завершения сцены")
        current = now or _utcnow()
        await cls._lock_economy(session)
        row = await cls._owned_session(session, owner_tg_id, session_id, token)
        if row.status == "ACTIVE":
            await cls._record_confirmed_tail(session, row, current, reason, row.last_sequence + 1)
            row.status, row.ended_at, row.end_reason = status, current, reason
            row.expires_at = current
        elif row.status == "PAUSED" and status == "STOPPED":
            row.status, row.ended_at, row.end_reason = "STOPPED", current, reason
        await session.flush()
        return {"success": True, "status": row.status, "active": False}

    @classmethod
    async def status(cls, session: AsyncSession, owner_tg_id: int, *, now: datetime | None = None) -> dict:
        current = now or _utcnow()
        if not active_production_enabled():
            return {"enabled": False, "session": None}
        company = await session.scalar(select(NatNextGameCompany).where(
            NatNextGameCompany.owner_tg_id == int(owner_tg_id),
        ))
        if company is None:
            return {"enabled": True, "session": None}
        row = await session.scalar(select(NatNextGameActiveSession).where(
            NatNextGameActiveSession.company_id == company.id,
            NatNextGameActiveSession.status == "ACTIVE",
        ).order_by(NatNextGameActiveSession.started_at.desc()).with_for_update())
        if row and row.expires_at <= current:
            await cls._record_confirmed_tail(session, row, current, "expired", row.last_sequence + 1)
            row.status, row.ended_at, row.end_reason = "EXPIRED", current, "heartbeat_timeout"
        return {"enabled": True, "server_now": current.isoformat(), "session": cls._session_summary(row, current)}


__all__ = [
    "ACTIVE_TIMEOUT_SECONDS", "HEARTBEAT_SECONDS", "IDLE_WARNING_SECONDS",
    "MAX_ACTIVE_MULTIPLIER", "NextGameActiveProductionService",
    "active_cycle_multiplier", "active_multiplier_for_cycle", "active_production_enabled",
    "output_with_active_bonus",
]
