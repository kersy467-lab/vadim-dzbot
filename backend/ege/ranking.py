"""Ranking, profiles and idempotent settlement for EGE Arena duels."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User

logger = logging.getLogger(__name__)

MIN_RATING = 0
MAX_RATING = 1000
WIN_RATING = 30
LOSS_RATING = -25
LEADERBOARD_TTL_SECONDS = 600

_RANKS = (
    (800, "titan", "Титан", "🏆"),
    (600, "divine", "Божество", "💎"),
    (500, "lord", "Властелин", "👑"),
    (400, "legend", "Легенда", "🌟"),
    (300, "hero", "Герой", "🛡️"),
    (200, "knight", "Рыцарь", "⚔️"),
    (100, "guardian", "Страж", "🔰"),
    (0, "recruit", "Рекрут", "🎖️"),
)
_NICK_RE = re.compile(r"^[A-Za-zА-Яа-яЁё0-9_.-]{2,24}$")
_CACHE_LOCK = asyncio.Lock()
_CACHE_EXPIRES_AT = 0.0
_CACHE_ROWS: list[dict[str, Any]] = []
_RANK_ASSET_DIR = Path(__file__).resolve().parents[2] / "frontend" / "assets" / "ranks"


def clamp_rating(value: int) -> int:
    return max(MIN_RATING, min(MAX_RATING, int(value or 0)))


def normalize_nickname(value: str) -> str:
    return str(value or "").strip().casefold()


def validate_nickname(value: str) -> tuple[bool, str]:
    nickname = str(value or "").strip()
    if not _NICK_RE.fullmatch(nickname):
        return False, "Ник: 2–24 символа, только буквы, цифры, _, - или точка."
    return True, nickname


def medal_for_rating(rating: int, top_position: int | None = None) -> dict[str, Any]:
    value = clamp_rating(rating)
    key, name, emoji = "recruit", "Рекрут", "🎖️"
    for threshold, rank_key, rank_name, rank_emoji in _RANKS:
        if value >= threshold:
            key, name, emoji = rank_key, rank_name, rank_emoji
            break
    special = key == "titan" and top_position is not None and 1 <= int(top_position) <= 5
    display_name = f"Титан ({int(top_position)})" if special else name
    image_key = f"titan_top_{int(top_position)}" if special else key
    return {
        "key": key,
        "name": name,
        "display_name": display_name,
        "emoji": emoji,
        "rating": value,
        "image_key": image_key,
        "image_url": f"/static/assets/ranks/thumbs/{image_key}.png",
        "image_path": str(_RANK_ASSET_DIR / f"{image_key}.png"),
    }


def rating_payload(rating: int, top_position: int | None = None) -> dict[str, Any]:
    medal = medal_for_rating(rating, top_position)
    return {
        "rating": medal["rating"],
        "medal": medal["display_name"],
        "base_medal": medal["name"],
        "medal_emoji": medal["emoji"],
        "medal_image": medal["image_url"],
        "top_position": top_position,
    }


async def _users_by_tg_ids(session: AsyncSession, tg_ids: Iterable[int]) -> dict[int, User]:
    ids = [int(uid) for uid in tg_ids if uid]
    if not ids:
        return {}
    result = await session.execute(select(User).where(User.tg_id.in_(ids)).with_for_update())
    return {int(user.tg_id): user for user in result.scalars().all()}


async def get_leaderboard(session: AsyncSession, *, force: bool = False) -> list[dict[str, Any]]:
    """Return a cached deterministic leaderboard; cache is refreshed at most every 10 minutes."""
    global _CACHE_EXPIRES_AT, _CACHE_ROWS
    now = time.monotonic()
    if not force and _CACHE_ROWS and now < _CACHE_EXPIRES_AT:
        return [dict(row) for row in _CACHE_ROWS]
    async with _CACHE_LOCK:
        now = time.monotonic()
        if not force and _CACHE_ROWS and now < _CACHE_EXPIRES_AT:
            return [dict(row) for row in _CACHE_ROWS]
        result = await session.execute(
            select(User).where(
                User.tg_id > 0,
                User.ege_nickname.is_not(None),
                User.ege_nickname_normalized.is_not(None),
                User.role != "rejected",
            ).order_by(
                User.ege_rating.desc(),
                User.ege_wins.desc(),
                User.ege_losses.asc(),
                User.created_at.asc(),
                User.id.asc(),
            ).limit(100)
        )
        rows: list[dict[str, Any]] = []
        for position, user in enumerate(result.scalars().all(), start=1):
            rank = medal_for_rating(user.ege_rating, position)
            rows.append({
                "position": position,
                "tg_id": int(user.tg_id),
                "nickname": user.ege_nickname,
                "rating": clamp_rating(user.ege_rating),
                "wins": int(user.ege_wins or 0),
                "losses": int(user.ege_losses or 0),
                "draws": int(user.ege_draws or 0),
                "matches": int(user.ege_wins or 0) + int(user.ege_losses or 0) + int(user.ege_draws or 0),
                "rank": rank["display_name"],
                "rank_image": rank["image_url"],
            })
        _CACHE_ROWS = rows
        _CACHE_EXPIRES_AT = now + LEADERBOARD_TTL_SECONDS
        return [dict(row) for row in rows]


async def get_player_profile(session: AsyncSession, user: User) -> dict[str, Any]:
    board = await get_leaderboard(session)
    cached = next((row for row in board if int(row["tg_id"]) == int(user.tg_id)), None)
    position = int(cached["position"]) if cached else None
    rank = medal_for_rating(user.ege_rating, position)
    wins, losses, draws = int(user.ege_wins or 0), int(user.ege_losses or 0), int(user.ege_draws or 0)
    return {
        "tg_id": int(user.tg_id),
        "nickname": user.ege_nickname or user.display_name,
        "rating": clamp_rating(user.ege_rating),
        "rank": rank["display_name"],
        "base_rank": rank["name"],
        "rank_emoji": rank["emoji"],
        "rank_image": rank["image_url"],
        "rank_image_path": rank["image_path"],
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "matches": wins + losses + draws,
        "top_position": position,
        "leaderboard_refresh_seconds": LEADERBOARD_TTL_SECONDS,
    }


async def settle_duel(session: AsyncSession, room: Any) -> None:
    """Atomically settle one in-memory duel exactly once, including persistent W/L/D stats."""
    if getattr(room, "game_type", "") not in {"ege_stress_duel", "ege_vocabulary_duel"}:
        return
    if getattr(room, "status", None) != "finished":
        return
    lock = getattr(room, "settlement_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        room.settlement_lock = lock
    async with lock:
        if getattr(room, "rating_settled", False):
            return
        players = [getattr(room, "host_tg_id", None), getattr(room, "opponent_tg_id", None)]
        users = await _users_by_tg_ids(session, players)
        winner = getattr(room, "winner", None)
        changes: dict[int, int] = {}
        snapshots: dict[int, dict[str, int]] = {}
        for tg_id in players:
            if not tg_id:
                continue
            user = users.get(int(tg_id))
            before = clamp_rating(getattr(user, "ege_rating", 0) if user else 0)
            requested_delta = 0 if winner is None else (WIN_RATING if int(tg_id) == int(winner) else LOSS_RATING)
            after = clamp_rating(before + requested_delta)
            actual_delta = after - before
            if user is not None:
                user.ege_rating = after
                if winner is None:
                    user.ege_draws = int(user.ege_draws or 0) + 1
                elif int(tg_id) == int(winner):
                    user.ege_wins = int(user.ege_wins or 0) + 1
                else:
                    user.ege_losses = int(user.ege_losses or 0) + 1
            changes[int(tg_id)] = actual_delta
            snapshots[int(tg_id)] = {"before": before, "after": after}
        await session.commit()
        room.rating_changes = changes
        room.rating_snapshots = snapshots
        room.rating_settled = True
        logger.info(
            "EGE rating settled room=%s winner=%s changes=%s",
            getattr(room, "room_id", "?"), winner, changes,
        )


async def build_room_payload(session: AsyncSession, room: Any, viewer_tg_id: int | None) -> dict[str, Any]:
    state = room.to_dict(viewer_tg_id=viewer_tg_id)
    if getattr(room, "game_type", "") not in {"ege_stress_duel", "ege_vocabulary_duel"}:
        return state
    host_id, opponent_id = getattr(room, "host_tg_id", None), getattr(room, "opponent_tg_id", None)
    users = await _users_by_tg_ids(session, [host_id, opponent_id])

    async def profile(tg_id: int | None) -> dict[str, Any]:
        user = users.get(int(tg_id)) if tg_id else None
        return await get_player_profile(session, user) if user else rating_payload(0)

    host_profile = await profile(host_id)
    opponent_profile = await profile(opponent_id)
    viewer_id = int(viewer_tg_id) if viewer_tg_id else None
    other_id = opponent_id if viewer_id == host_id else host_id
    state["host_rating"] = host_profile
    state["opponent_rating"] = opponent_profile
    state["your_rating"] = host_profile if viewer_id == host_id else opponent_profile
    state["rival_rating"] = opponent_profile if viewer_id == host_id else host_profile
    changes = getattr(room, "rating_changes", {}) or {}
    state["your_rating_change"] = int(changes.get(viewer_id, 0)) if viewer_id else 0
    state["rival_rating_change"] = int(changes.get(int(other_id), 0)) if other_id else 0
    return state
