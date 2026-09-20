"""
FastAPI роутер игры «Подбрасывание монетки» на монеты.
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Body

from backend.db.models import User
from backend.db.session import async_session_factory
from backend.db.crud.users import add_user_coins, get_user_by_tg_id
from backend.api.auth import get_optional_webapp_user, extract_viewer_tg_id as _extract_viewer_tg_id
from backend.bot.game_coinflip import flip_coin, SIDES

router = APIRouter(prefix="/coinflip", tags=["coinflip"])


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
                detail="Включите игровую экосистему в настройках бота для игры в Монетку"
            )
        return viewer_id, db_user


@router.get("/state")
async def coinflip_state(
    request: Request,
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Текущий баланс пользователя и список сторон монетки."""
    _, db_user = await _resolve_user_and_check_ecosystem(request, user)
    return {
        "ok": True,
        "coins": db_user.coins or 0,
        "sides": SIDES,
    }


@router.post("/flip")
async def coinflip_flip(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """
    Бросок монетки.
    payload: {"stake": 50, "choice": "heads"}
    """
    viewer_id, db_user = await _resolve_user_and_check_ecosystem(request, user, payload=payload)

    try:
        stake = int(payload.get("stake", 0))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Некорректный размер ставки")

    if stake <= 0:
        raise HTTPException(status_code=400, detail="Ставка должна быть больше 0")

    choice = str(payload.get("choice", "heads")).lower().strip()
    if choice not in SIDES:
        raise HTTPException(status_code=400, detail="Выберите сторону: heads (Орёл) или tails (Решка)")

    if (db_user.coins or 0) < stake:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно монет. Ставка: {stake} 🪙, баланс: {db_user.coins or 0} 🪙"
        )

    # 1. Бросок монетки
    result = flip_coin(stake, choice)
    payout = result["payout"]
    net_change = payout - stake

    # 2. Атомарное обновление баланса
    async with async_session_factory() as session:
        cur_user = await get_user_by_tg_id(session, viewer_id)
        if not cur_user or (cur_user.coins or 0) < stake:
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно монет. Ставка: {stake} 🪙, баланс: {getattr(cur_user, 'coins', 0) or 0} 🪙"
            )
        new_balance = await add_user_coins(session, viewer_id, net_change)
        user_coins = new_balance if new_balance is not None else 0

    return {
        "ok": True,
        "stake": stake,
        "choice": result["choice"],
        "choice_name": result["choice_name"],
        "choice_icon": result["choice_icon"],
        "outcome": result["outcome"],
        "outcome_name": result["outcome_name"],
        "outcome_icon": result["outcome_icon"],
        "status": result["status"],
        "multiplier": result["multiplier"],
        "payout": payout,
        "net_profit": result["net_profit"],
        "coins": user_coins,
    }
