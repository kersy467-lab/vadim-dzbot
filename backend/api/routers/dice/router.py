"""
FastAPI роутер игры «Кости» на монеты.
"""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Body

from backend.db.models import User
from backend.db.session import async_session_factory
from backend.db.crud.users import add_user_coins, get_user_by_tg_id
from backend.api.auth import get_optional_webapp_user, extract_viewer_tg_id as _extract_viewer_tg_id
from backend.bot.game_dice import play_dice_duel, play_dice_over_under

router = APIRouter(prefix="/dice", tags=["dice"])


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
                detail="Включите игровую экосистему в настройках бота для игры в Кости"
            )
        return viewer_id, db_user


@router.get("/state")
async def dice_state(
    request: Request,
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """Получение текущего баланса и статуса костей."""
    _, db_user = await _resolve_user_and_check_ecosystem(request, user)
    return {
        "ok": True,
        "coins": db_user.coins or 0,
    }


@router.post("/duel")
async def dice_duel(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """
    Бросок в режиме «Дуэль с дилером».
    payload: {"stake": 25}
    """
    viewer_id, db_user = await _resolve_user_and_check_ecosystem(request, user, payload=payload)

    stake = int(payload.get("stake", 10))
    if stake <= 0:
        raise HTTPException(status_code=400, detail="Ставка должна быть больше 0")

    if (db_user.coins or 0) < stake:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно монет для ставки. Ваш баланс: {db_user.coins or 0} 🪙"
        )

    # 1. Игра
    result = play_dice_duel(stake)
    net_change = result["payout"] - stake

    # 2. Атомарное обновление баланса
    async with async_session_factory() as session:
        cur_user = await get_user_by_tg_id(session, viewer_id)
        if not cur_user or (cur_user.coins or 0) < stake:
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно монет для ставки. Ваш баланс: {getattr(cur_user, 'coins', 0) or 0} 🪙"
            )
        new_balance = await add_user_coins(session, viewer_id, net_change)
        user_coins = new_balance if new_balance is not None else 0

    return {
        "ok": True,
        "result": result,
        "coins": user_coins,
    }


@router.post("/over_under")
async def dice_over_under(
    request: Request,
    payload: Dict[str, Any] = Body(default={}),
    user: Optional[User] = Depends(get_optional_webapp_user),
):
    """
    Бросок в режиме «Больше / Меньше / 7».
    payload: {"stake": 25, "prediction": "under_7" | "over_7" | "exact_7" | "double"}
    """
    viewer_id, db_user = await _resolve_user_and_check_ecosystem(request, user, payload=payload)

    stake = int(payload.get("stake", 10))
    if stake <= 0:
        raise HTTPException(status_code=400, detail="Ставка должна быть больше 0")

    pred = str(payload.get("prediction", "under_7")).lower().strip()
    if pred not in ("under_7", "over_7", "exact_7", "seven", "double", "any_double"):
        raise HTTPException(status_code=400, detail="Недопустимый тип ставки")

    if (db_user.coins or 0) < stake:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно монет для ставки. Ваш баланс: {db_user.coins or 0} 🪙"
        )

    # 1. Игра
    result = play_dice_over_under(stake, pred)
    net_change = result["payout"] - stake

    # 2. Атомарное обновление баланса
    async with async_session_factory() as session:
        cur_user = await get_user_by_tg_id(session, viewer_id)
        if not cur_user or (cur_user.coins or 0) < stake:
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно монет для ставки. Ваш баланс: {getattr(cur_user, 'coins', 0) or 0} 🪙"
            )
        new_balance = await add_user_coins(session, viewer_id, net_change)
        user_coins = new_balance if new_balance is not None else 0

    return {
        "ok": True,
        "result": result,
        "coins": user_coins,
    }
