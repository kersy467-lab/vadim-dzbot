"""
FastAPI роутер игры «Слоты» на монеты.
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Body

from backend.db.models import User
from backend.db.session import async_session_factory
from backend.db.crud.users import add_user_coins, get_user_by_tg_id
from backend.api.auth import get_optional_webapp_user, extract_viewer_tg_id as _extract_viewer_tg_id
from backend.bot.game_slots import play_slots, SLOT_SYMBOLS

router = APIRouter(prefix="/slots", tags=["slots"])


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
                detail="Включите игровую экосистему в настройках бота для игры в Слоты"
            )
        return viewer_id, db_user


@router.get("/state")
async def slots_state(
    request: Request,
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Текущий баланс пользователя и каталог символов."""
    _, db_user = await _resolve_user_and_check_ecosystem(request, user)
    return {
        "ok": True,
        "coins": db_user.coins or 0,
        "symbols": SLOT_SYMBOLS,
    }


@router.post("/spin")
async def slots_spin(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """
    Вращение слотов.
    payload: {"stake": 50}
    """
    viewer_id, db_user = await _resolve_user_and_check_ecosystem(request, user, payload=payload)

    try:
        stake = int(payload.get("stake", 0))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Некорректный размер ставки")

    if stake <= 0:
        raise HTTPException(status_code=400, detail="Ставка должна быть больше 0")

    if (db_user.coins or 0) < stake:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно монет. Ставка: {stake} 🪙, баланс: {db_user.coins or 0} 🪙"
        )

    # 1. Расчет слотов
    result = play_slots(stake)
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
        "reels": result["reels"],
        "stake": stake,
        "multiplier": result["multiplier"],
        "payout": payout,
        "net_profit": result["net_profit"],
        "status": result["status"],
        "combination": result["combination"],
        "coins": user_coins,
    }
