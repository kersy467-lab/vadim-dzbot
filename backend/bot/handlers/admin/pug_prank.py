"""
backend/bot/handlers/admin/pug_prank.py
Шуточный изолированный модуль для режима «Глеб Мопс».
Полностью автономен — для удаления достаточно просто удалить этот файл и убрать 1 строчку импорта.
"""

import os
import json
import logging
from typing import Optional
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from fastapi import APIRouter, Query

from backend.db.models import User
from backend.bot.handlers.admin.helpers import is_admin

logger = logging.getLogger("pug_prank")

router = Router(name="pug_prank_router")
pug_api_router = APIRouter(tags=["pug_prank"])

GLEB_TG_ID = 5181261098
DATA_FILE = os.path.join("data", "pug_prank.json")

_cached_pug_mode: Optional[bool] = None


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


def toggle_pug_mode() -> bool:
    return set_pug_mode(not is_pug_mode_active())


def get_pug_keyboard_button() -> InlineKeyboardButton:
    active = is_pug_mode_active()
    status_label = "[ВКЛ] 🟢" if active else "[ВЫКЛ] ⚪"
    return InlineKeyboardButton(
        text=f"🐶 Мопс Глеб: {status_label}",
        callback_data="admin_toggle_pug_mode"
    )


@router.message(F.text.in_(["/pug", "/mops", "/мопс", "🐶 Мопс"]))
async def cmd_admin_toggle_pug_mode(message: Message, current_user: User):
    if not is_admin(current_user, message.from_user.id):
        return
    new_state = toggle_pug_mode()
    state_txt = "АКТИВИРОВАН 🟢" if new_state else "ВЫКЛЮЧЕН ⚪"
    await message.answer(
        f"🐶 Режим «Глеб Мопс» {state_txt}!\n\n"
        f"Целевой пользователь: Глеб (ID: `{GLEB_TG_ID}`).\n"
        f"В Mini App: {'полноэкранный мопс на черном фоне' if new_state else 'обычное школьное расписание'}.",
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin_toggle_pug_mode")
async def cb_admin_toggle_pug_mode(callback: CallbackQuery, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        await callback.answer("⛔ Только для администраторов!", show_alert=True)
        return

    new_state = toggle_pug_mode()
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
async def api_pug_prank_status(tg_id: Optional[int] = Query(None)):
    enabled = is_pug_mode_active()
    is_target = bool(tg_id and int(tg_id) == GLEB_TG_ID)
    return {
        "enabled": enabled,
        "target_tg_id": GLEB_TG_ID,
        "user_tg_id": tg_id,
        "is_target": is_target,
        "active": enabled and is_target
    }


@pug_api_router.post("/pug_prank/toggle")
async def api_pug_prank_toggle():
    new_state = toggle_pug_mode()
    return {
        "success": True,
        "active": new_state,
        "target_tg_id": GLEB_TG_ID
    }
