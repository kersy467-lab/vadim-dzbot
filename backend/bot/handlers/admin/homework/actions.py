import time
import asyncio
from datetime import date, datetime, timedelta
from typing import List, Tuple, Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User, Subject
from backend.db.crud import (
    get_all_subjects, get_subject_by_id, create_homework, delete_homework,
    get_recent_active_homeworks, get_homework_by_id, find_upcoming_dates_for_subject
)
from backend.bot.keyboards.admin_kb import (
    get_admin_panel_keyboard, get_cancel_keyboard, get_hw_notify_keyboard
)
from backend.bot.keyboards.calendar import get_inline_calendar
from backend.bot.services.notifier import send_new_homework_alert
from backend.bot.handlers.schedule import DAYS_RU
from backend.bot.handlers.admin.helpers import is_admin
from backend.bot.handlers.admin.states import AddHomeworkStates

from backend.bot.handlers.admin.homework.helpers import safe_answer, safe_edit_text, escape_md

router = Router(name="admin_homework_actions_router")

# ==================== HOMEWORK NOTIFICATIONS & DELETION ====================

@router.callback_query(F.data.startswith("adm_hwnotif_grp_"))
async def cb_hw_notif_group(callback: CallbackQuery, db_session: AsyncSession, bot: Bot):
    hw_id = int(callback.data.replace("adm_hwnotif_grp_", ""))
    hw = await get_homework_by_id(db_session, hw_id)
    if not hw:
        await callback.answer("ДЗ не найдено", show_alert=True)
        return

    g_cnt, _ = await send_new_homework_alert(bot, db_session, hw, to_group=True, to_users=False)
    await safe_edit_text(
        callback.message,
        f"📢 **Оповещение о новом ДЗ успешно отправлено в беседы класса ({g_cnt} чат(ов))!**",
        reply_markup=get_admin_panel_keyboard()
    )
    try:
        await callback.answer("Оповещение отправлено в беседу!")
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_hwnotif_all_"))
async def cb_hw_notif_all(callback: CallbackQuery, db_session: AsyncSession, bot: Bot):
    hw_id = int(callback.data.replace("adm_hwnotif_all_", ""))
    hw = await get_homework_by_id(db_session, hw_id)
    if not hw:
        await callback.answer("ДЗ не найдено", show_alert=True)
        return

    g_cnt, u_cnt = await send_new_homework_alert(bot, db_session, hw, to_group=True, to_users=True)
    await safe_edit_text(
        callback.message,
        f"📢 **Оповещение о новом ДЗ успешно разослано:**\n\n"
        f"• В беседы класса: **{g_cnt}**\n"
        f"• Ученикам в личные сообщения: **{u_cnt}**",
        reply_markup=get_admin_panel_keyboard()
    )
    try:
        await callback.answer("Оповещение разослано в беседу и всем в ЛС!")
    except Exception:
        pass


@router.callback_query(F.data == "adm_hwnotif_none")
async def cb_hw_notif_none(callback: CallbackQuery):
    await safe_edit_text(
        callback.message,
        "✅ **Домашнее задание сохранено без рассылки.**",
        reply_markup=get_admin_panel_keyboard()
    )
    try:
        await callback.answer("Сохранено без оповещения")
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_hw_del_"))
async def cb_hw_delete(callback: CallbackQuery, db_session: AsyncSession):
    hw_id = int(callback.data.replace("adm_hw_del_", ""))
    deleted = await delete_homework(db_session, hw_id)
    if deleted:
        await safe_edit_text(
            callback.message,
            "🗑 **Домашнее задание успешно удалено!**",
            reply_markup=get_admin_panel_keyboard()
        )
        try:
            await callback.answer("ДЗ удалено!")
        except Exception:
            pass
    else:
        await callback.answer("Задание уже было удалено.", show_alert=True)


@router.callback_query(F.data == "admin_delete_hw")
async def cb_start_delete_hw(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    recent = await get_recent_active_homeworks(db_session)
    if not recent:
        await safe_edit_text(
            callback.message,
            "ℹ️ **Список актуальных ДЗ пуст.** Нет заданий для удаления.",
            reply_markup=get_admin_panel_keyboard()
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return

    buttons = []
    for hw in recent:
        s_name = hw.subject.name if hw.subject else "Предмет"
        d_str = hw.due_date.strftime("%d.%m")
        desc_short = (hw.description[:25] + "...") if len(hw.description) > 25 else hw.description
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {s_name} ({d_str}): {desc_short}",
                callback_data=f"adm_hw_confirm_del_{hw.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад в панель", callback_data="admin_menu_back")])

    await safe_edit_text(
        callback.message,
        "🗑 **Удаление домашнего задания:**\n"
        "Выберите задание, которое хотите удалить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_hw_confirm_del_"))
async def cb_confirm_delete_hw(callback: CallbackQuery, db_session: AsyncSession):
    hw_id = int(callback.data.replace("adm_hw_confirm_del_", ""))
    hw = await get_homework_by_id(db_session, hw_id)
    if not hw:
        await callback.answer("ДЗ уже удалено", show_alert=True)
        return

    s_name = hw.subject.name if hw.subject else "Предмет"
    d_str = hw.due_date.strftime("%d.%m.%Y")
    desc_escaped = escape_md(hw.description)
    text = (
        f"⚠️ **Вы уверены, что хотите удалить это ДЗ?**\n\n"
        f"📖 **Предмет:** {s_name}\n"
        f"📅 **Дата сдачи:** {d_str}\n"
        f"📝 **Задание:** {desc_escaped}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Да, удалить", callback_data=f"adm_hw_del_{hw.id}")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_delete_hw")]
        ]
    )
    await safe_edit_text(callback.message, text, reply_markup=kb)
    try:
        await callback.answer()
    except Exception:
        pass
