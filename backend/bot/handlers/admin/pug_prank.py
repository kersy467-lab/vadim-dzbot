"""
backend/bot/handlers/admin/pug_prank.py
Шуточный изолированный модуль для режима «Глеб Мопс».
Полностью автономен — для удаления достаточно просто удалить этот файл и убрать 1 строчку импорта.
"""

import os
import json
import logging
from urllib.parse import parse_qs, unquote
from typing import Optional, Any
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from fastapi import APIRouter, Query, Header, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.session import get_db_session, async_session_factory
from backend.bot.handlers.admin.helpers import is_admin

logger = logging.getLogger("pug_prank")

router = Router(name="pug_prank_router")
pug_api_router = APIRouter(tags=["pug_prank"])

GLEB_TG_ID = 5181261098
GLEB_USERNAME = "glebasikpodpivasik87"
DATA_FILE = os.path.join("data", "pug_prank.json")

_cached_pug_mode: Optional[bool] = None


def _extract_id_and_username_from_init_data(init_data_str: str) -> tuple[Optional[int], Optional[str]]:
    if not init_data_str:
        return None, None
    try:
        parsed = parse_qs(init_data_str)
        user_raw = parsed.get("user", [None])[0]
        if user_raw:
            user_json = json.loads(unquote(user_raw))
            uid = int(user_json.get("id")) if user_json.get("id") else None
            uname = str(user_json.get("username") or "").lower() or None
            return uid, uname
    except Exception:
        pass
    return None, None


def is_pug_mode_active() -> bool:
    global _cached_pug_mode
    if _cached_pug_mode is not None:
        return _cached_pug_mode
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                _cached_pug_mode = bool(data.get("active", False))
                return _cached_pug_mode
        except Exception as e:
            logger.warning(f"Could not read {DATA_FILE}: {e}")
    _cached_pug_mode = False
    return False


def set_pug_mode(active: bool) -> bool:
    global _cached_pug_mode
    _cached_pug_mode = bool(active)
    try:
        os.makedirs("data", exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"active": _cached_pug_mode, "target_tg_id": GLEB_TG_ID}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Could not save {DATA_FILE}: {e}")
    return _cached_pug_mode


async def set_pug_mode_async(session: AsyncSession, active: bool) -> bool:
    set_pug_mode(active)
    try:
        from backend.db.crud.duty import set_class_setting
        await set_class_setting(session, "pug_prank_active", "1" if active else "0")
    except Exception as e:
        logger.warning(f"Could not persist pug_prank_active in DB: {e}")
    return active


async def toggle_pug_mode_async(session: AsyncSession) -> bool:
    new_state = not is_pug_mode_active()
    await set_pug_mode_async(session, new_state)
    return new_state


def toggle_pug_mode() -> bool:
    new_state = not is_pug_mode_active()
    set_pug_mode(new_state)
    try:
        import asyncio
        async def _save():
            async with async_session_factory() as s:
                from backend.db.crud.duty import set_class_setting
                await set_class_setting(s, "pug_prank_active", "1" if new_state else "0")
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_save())
        except RuntimeError:
            asyncio.run(_save())
    except Exception as e:
        logger.warning(f"Async DB save fallback in toggle_pug_mode failed: {e}")
    return new_state


def get_pug_keyboard_button() -> InlineKeyboardButton:
    active = is_pug_mode_active()
    status_label = "[ВКЛ] 🟢" if active else "[ВЫКЛ] ⚪"
    return InlineKeyboardButton(
        text=f"🐶 Мопс Глеб: {status_label}",
        callback_data="admin_toggle_pug_mode"
    )


@router.message(F.text.startswith("/pug") | F.text.startswith("/mops") | F.text.startswith("/мопс") | (F.text == "🐶 Мопс"))
async def cmd_admin_toggle_pug_mode(message: Message, current_user: User, db_session: AsyncSession):
    if not is_admin(current_user, message.from_user.id):
        return
    text = (message.text or "").strip().lower()
    if "on" in text or "вкл" in text or "1" in text:
        new_state = await set_pug_mode_async(db_session, True)
    elif "off" in text or "выкл" in text or "0" in text:
        new_state = await set_pug_mode_async(db_session, False)
    else:
        new_state = await toggle_pug_mode_async(db_session)

    state_txt = "АКТИВИРОВАН 🟢" if new_state else "ВЫКЛЮЧЕН ⚪"
    await message.answer(
        f"🐶 Режим «Глеб Мопс» {state_txt}!\n\n"
        f"Целевой пользователь: Глеб (ID: `{GLEB_TG_ID}`, @{GLEB_USERNAME}).\n"
        f"В Mini App: {'полноэкранный мопс на черном фоне' if new_state else 'обычное школьное расписание'}.",
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin_toggle_pug_mode")
async def cb_admin_toggle_pug_mode(callback: CallbackQuery, current_user: User, db_session: AsyncSession):
    if not is_admin(current_user, callback.from_user.id):
        await callback.answer("⛔ Только для администраторов!", show_alert=True)
        return

    new_state = await toggle_pug_mode_async(db_session)
    state_txt = "АКТИВИРОВАН 🟢" if new_state else "ВЫКЛЮЧЕН ⚪"
    alert_msg = (
        f"🐶 Режим «Глеб Мопс» {state_txt}!\n\n"
        f"Теперь у Глеба (ID: {GLEB_TG_ID}) в Mini App "
        f"{'будет мопс на черном фоне и кнопки «Гав-гав»' if new_state else 'отображается обычное расписание'}."
    )

    try:
        from backend.bot.keyboards.admin_kb import get_admin_panel_keyboard
        await callback.message.edit_reply_markup(reply_markup=get_admin_panel_keyboard())
    except Exception:
        pass

    try:
        await callback.answer(alert_msg, show_alert=True)
    except Exception:
        pass


@pug_api_router.get("/pug_prank/status")
async def api_pug_prank_status(
    request: Request,
    tg_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    uid: Optional[int] = Query(None),
    tg_user_id: Optional[int] = Query(None),
    username: Optional[str] = Query(None),
    x_telegram_user_id: Optional[str] = Header(None),
    x_telegram_init_data: Optional[str] = Header(None),
    session: AsyncSession = Depends(get_db_session)
):
    global _cached_pug_mode
    if _cached_pug_mode is None:
        try:
            from backend.db.crud.duty import get_class_setting
            val = await get_class_setting(session, "pug_prank_active")
            if val is not None:
                _cached_pug_mode = (val == "1")
        except Exception:
            pass

    enabled = is_pug_mode_active()

    viewer_id = tg_id or user_id or uid or tg_user_id
    viewer_username: Optional[str] = username

    if not viewer_id and x_telegram_user_id and x_telegram_user_id.isdigit():
        viewer_id = int(x_telegram_user_id)

    raw_init = x_telegram_init_data
    if not raw_init and request:
        raw_init = request.headers.get("x-telegram-init-data") or request.headers.get("X-Telegram-Init-Data")
    if raw_init:
        init_uid, init_uname = _extract_id_and_username_from_init_data(raw_init)
        if init_uid and not viewer_id:
            viewer_id = init_uid
        if init_uname and not viewer_username:
            viewer_username = init_uname

    if not viewer_id and request:
        for qk in ("tg_id", "user_id", "uid", "tg_user_id"):
            val = request.query_params.get(qk)
            if val and val.isdigit():
                viewer_id = int(val)
                break

    if not viewer_username and request:
        viewer_username = request.query_params.get("username")

    is_target = bool(
        (viewer_id and int(viewer_id) == GLEB_TG_ID) or
        (viewer_username and viewer_username.lower() == GLEB_USERNAME)
    )
    if is_target and not viewer_id:
        viewer_id = GLEB_TG_ID

    return {
        "enabled": enabled,
        "target_tg_id": GLEB_TG_ID,
        "user_tg_id": viewer_id,
        "is_target": is_target,
        "active": enabled and is_target
    }


@pug_api_router.post("/pug_prank/toggle")
async def api_pug_prank_toggle(session: AsyncSession = Depends(get_db_session)):
    new_state = await toggle_pug_mode_async(session)
    return {
        "success": True,
        "active": new_state,
        "target_tg_id": GLEB_TG_ID
    }
