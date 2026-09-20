"""
FastAPI роутер игры «Рулетка» на монеты.
"""
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, Body

from backend.db.models import User
from backend.db.session import async_session_factory
from backend.db.crud.users import add_user_coins, get_user_by_tg_id
from backend.api.auth import get_optional_webapp_user, extract_viewer_tg_id as _extract_viewer_tg_id
from backend.bot.game_roulette import (
    spin_wheel,
    get_number_color,
    evaluate_roulette_spin,
)

router = APIRouter(prefix="/roulette", tags=["roulette"])


async def _resolve_user_and_check_ecosystem(
    request: Request,
    user: Optional[User],
    payload: Optional[Dict[str, Any]] = None,
) -> tuple[int, User]:
    viewer_id = _extract_viewer_tg_id(user, request, payload=payload)
    if not viewer_id:
        raise HTTPException(status_code=401, detail="Требуется авторизация через Telegram Mini App")

    async with async_session_factory() as session:
        db_user = await get_user_by_tg_id(session, viewer_id)
        if not db_user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        if not bool(getattr(db_user, "currency_ecosystem_enabled", False)):
            raise HTTPException(
                status_code=400,
                detail="Включите игровую экосистему в настройках бота для игры в Рулетку"
            )
        return viewer_id, db_user


@router.get("/state")
async def roulette_state(
    request: Request,
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Получение текущего баланса и статуса рулетки."""
    _, db_user = await _resolve_user_and_check_ecosystem(request, user)
    return {
        "ok": True,
        "coins": db_user.coins or 0,
    }


@router.post("/spin")
async def roulette_spin(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """
    Вращение рулетки.
    payload: {"bets": [{"type": "red", "amount": 25}, {"type": "straight", "value": 7, "amount": 10}]}
    """
    viewer_id, db_user = await _resolve_user_and_check_ecosystem(request, user, payload=payload)

    bets = payload.get("bets", [])
    if not isinstance(bets, list) or not bets:
        raise HTTPException(status_code=400, detail="Необходимо сделать хотя бы одну ставку")

    total_stake = sum(max(0, int(b.get("amount", 0))) for b in bets)
    if total_stake <= 0:
        raise HTTPException(status_code=400, detail="Сумма ставок должна быть больше 0")

    if (db_user.coins or 0) < total_stake:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно монет. Общая ставка: {total_stake} 🪙, баланс: {db_user.coins or 0} 🪙"
        )

    # 1. Вращение рулетки и оценка ставок
    winning_num = spin_wheel()
    color = get_number_color(winning_num)
    _, total_payout, evaluated_bets = evaluate_roulette_spin(bets, winning_num)
    net_change = total_payout - total_stake

    # 2. Атомарное обновление баланса
    async with async_session_factory() as session:
        cur_user = await get_user_by_tg_id(session, viewer_id)
        if not cur_user or (cur_user.coins or 0) < total_stake:
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно монет. Общая ставка: {total_stake} 🪙, баланс: {getattr(cur_user, 'coins', 0) or 0} 🪙"
            )
        new_balance = await add_user_coins(session, viewer_id, net_change)
        user_coins = new_balance if new_balance is not None else 0

    return {
        "ok": True,
        "winning_number": winning_num,
        "color": color,
        "total_stake": total_stake,
        "total_payout": total_payout,
        "net_profit": total_payout - total_stake,
        "evaluated_bets": evaluated_bets,
        "coins": user_coins,
    }
