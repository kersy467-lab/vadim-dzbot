from datetime import date, timedelta
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_today
from backend.db.models import User
from backend.db.crud import (
    get_all_subjects, get_subject_by_id,
    set_schedule_item, set_date_schedule_item, set_permanent_schedule_item,
    get_schedule_for_date, get_schedule_for_day,
    save_bulk_date_schedule, save_bulk_permanent_schedule, clear_date_schedule,
    auto_shift_active_homeworks, create_substitution,
    get_notifiable_users, get_approved_group_chats
)
from backend.bot.keyboards.admin_kb import (
    get_admin_panel_keyboard, get_cancel_keyboard, get_notify_confirm_keyboard,
    get_date_schedule_notify_keyboard, get_schedule_broadcast_day_keyboard,
    get_schedule_broadcast_destination_keyboard
)
from backend.bot.keyboards.calendar import get_inline_calendar
from backend.bot.services.notifier import send_schedule_change_alert
from backend.bot.handlers.schedule import DAYS_RU, format_day_schedule
from backend.bot.handlers.admin.helpers import is_admin, parse_schedule_text
from backend.bot.handlers.admin.states import (
    EditScheduleStates, EditDateScheduleStates, AddSubstitutionStates,
    ScheduleWizardStates, ScheduleBroadcastStates
)

router = Router(name='admin_sched_sub_router')

# ==================== SUBSTITUTIONS & CANCELLATIONS ====================

@router.callback_query(F.data == "admin_add_sub")
async def cb_start_add_sub(callback: CallbackQuery, state: FSMContext, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    today = date.today()
    kb = get_inline_calendar("adm_sub", year=today.year, month=today.month, back_callback="admin_cancel")

    await state.set_state(AddSubstitutionStates.entering_date)
    await callback.message.edit_text(
        "🔄 **Замена урока (Шаг 1/4):**\n"
        "Выберите дату на интерактивном календаре:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("cal_nav_adm_sub_"))
async def cb_cal_nav_adm_sub(callback: CallbackQuery):
    parts = callback.data.split("_")
    year = int(parts[4])
    month = int(parts[5])
    kb = get_inline_calendar("adm_sub", year=year, month=month, back_callback="admin_cancel")
    await callback.message.edit_text(
        "🔄 **Замена урока (Шаг 1/4):**\n"
        "Выберите дату на интерактивном календаре:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("cal_act_adm_sub_"))
async def cb_cal_act_adm_sub(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    year = int(parts[4])
    month = int(parts[5])
    day = int(parts[6])
    sub_date = date(year, month, day)

    await state.update_data(sub_date=sub_date.isoformat())

    lesson_btns = [
        [InlineKeyboardButton(text=f"{i} урок", callback_data=f"adm_sub_l_{i}") for i in range(1, 5)],
        [InlineKeyboardButton(text=f"{i} урок", callback_data=f"adm_sub_l_{i}") for i in range(5, 9)],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
    ]

    await state.set_state(AddSubstitutionStates.entering_lesson_num)
    await callback.message.edit_text(
        f"🔢 **Замена на {sub_date.strftime('%d.%m.%Y')} (Шаг 2/4):**\nКакой по счету урок заменяется/отменяется?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=lesson_btns),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_sub_l_"))
async def cb_sub_lesson_chosen(callback: CallbackQuery, state: FSMContext):
    l_num = int(callback.data.replace("adm_sub_l_", ""))
    await state.update_data(lesson_number=l_num)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Замена на другой предмет", callback_data="adm_sub_act_replace")],
            [InlineKeyboardButton(text="❌ Отмена урока (урока не будет)", callback_data="adm_sub_act_cancel")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
        ]
    )

    await state.set_state(AddSubstitutionStates.choosing_action)
    await callback.message.edit_text(
        f"⚡ **{l_num}-й урок (Шаг 3/4):** Что происходит с уроком?",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "adm_sub_act_cancel")
async def cb_sub_cancel_lesson(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    sub_date = date.fromisoformat(data["sub_date"])

    sub = await create_substitution(
        session=db_session,
        target_date=sub_date,
        lesson_number=data["lesson_number"],
        old_subject_id=None,
        new_subject_id=None,
        comment="Урок отменен",
        is_cancelled=True
    )
    await auto_shift_active_homeworks(db_session)
    await state.update_data(sub_id=sub.id)

    await state.set_state(AddSubstitutionStates.confirm_notification)

    await callback.message.edit_text(
        f"❌ **Зафиксирована отмена {data['lesson_number']}-го урока на {sub_date.strftime('%d.%m.%Y')}!**\n\n"
        "Отправить мгновенное уведомление всему классу?",
        reply_markup=get_notify_confirm_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "adm_sub_act_replace")
async def cb_sub_action_replace(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    subjects = await get_all_subjects(db_session)
    buttons = [[InlineKeyboardButton(text=s.name, callback_data=f"adm_sub_new_s_{s.id}")] for s in subjects]
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")])

    await state.set_state(AddSubstitutionStates.choosing_new_subject)
    await callback.message.edit_text(
        "📖 **Какой предмет будет вместо прежнего?**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_sub_new_s_"))
async def cb_sub_new_subject_chosen(callback: CallbackQuery, state: FSMContext):
    new_s_id = int(callback.data.replace("adm_sub_new_s_", ""))
    await state.update_data(new_subject_id=new_s_id)
    await state.set_state(AddSubstitutionStates.entering_comment)

    await callback.message.edit_text(
        "📝 **Напишите комментарий (например, имя учителя или тему) либо отправьте `-`:**",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(AddSubstitutionStates.entering_comment)
async def msg_sub_finish(message: Message, state: FSMContext, db_session: AsyncSession):
    text = message.text.strip()
    comment = text if text != "-" else None

    data = await state.get_data()
    sub_date = date.fromisoformat(data["sub_date"])

    sub = await create_substitution(
        session=db_session,
        target_date=sub_date,
        lesson_number=data["lesson_number"],
        old_subject_id=None,
        new_subject_id=data.get("new_subject_id"),
        comment=comment,
        is_cancelled=False
    )
    await auto_shift_active_homeworks(db_session)
    await state.update_data(sub_id=sub.id)

    await state.set_state(AddSubstitutionStates.confirm_notification)

    await message.answer(
        f"✅ **Замена сохранена!**\n"
        f"📅 **Дата:** {sub_date.strftime('%d.%m.%Y')}\n"
        f"🔢 **Урок:** {data['lesson_number']}\n\n"
        "Отправить срочное оповещение всему классу?",
        reply_markup=get_notify_confirm_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data.in_(["sub_notify_groups", "sub_notify_pm", "sub_notify_all", "sub_notify_yes"]))
async def cb_sub_broadcast(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot):
    data = await state.get_data()
    sub_date_str = data.get("sub_date") or data.get("edit_target_date")
    if not sub_date_str:
        await callback.answer("Данные для оповещения не найдены", show_alert=True)
        await state.clear()
        return

    to_groups = callback.data in ("sub_notify_groups", "sub_notify_all", "sub_notify_yes")
    to_users = callback.data in ("sub_notify_pm", "sub_notify_all", "sub_notify_yes")

    sub_date = date.fromisoformat(sub_date_str)
    l_num = data.get("lesson_number")

    if l_num is not None:
        notif_text = (
            f"🚨 **ВНИМАНИЕ! ЗАМЕНА В РАСПИСАНИИ 11 «Б»!** 🚨\n\n"
            f"📅 **Дата:** {sub_date.strftime('%d.%m.%Y')}\n"
            f"🔢 **{l_num}-й урок** изменен!\n\n"
            "Пожалуйста, проверьте расписание в боте или в Mini App."
        )

        sent_count = 0

        if to_users:
            students = await get_notifiable_users(db_session)
            for s in students:
                try:
                    await bot.send_message(chat_id=s.tg_id, text=notif_text, parse_mode="Markdown")
                    sent_count += 1
                except Exception:
                    pass

        if to_groups:
            groups = await get_approved_group_chats(db_session)
            for g in groups:
                try:
                    await bot.send_message(
                        chat_id=g.chat_id,
                        message_thread_id=g.topic_schedule_id,
                        text=notif_text,
                        parse_mode="Markdown"
                    )
                    sent_count += 1
                except Exception:
                    pass

        await state.clear()
        dest_text = "в чат и в ЛС" if (to_groups and to_users) else ("в чат" if to_groups else "в ЛС")
        await callback.message.edit_text(
            f"📢 Оповещение о замене успешно разослано ({dest_text}) {sent_count} получателям!",
            reply_markup=get_admin_panel_keyboard()
        )
        try:
            await callback.answer("Разослано!")
        except Exception:
            pass
    else:
        # Full date schedule broadcast fallback
        day_name = DAYS_RU.get(sub_date.isoweekday(), "")
        title = data.get("alert_title", f"📅 **{day_name} ({sub_date.strftime('%d.%m.%Y')}):**")
        lines = data.get("alert_lines", [])
        try:
            await send_schedule_change_alert(bot, title, lines, to_groups=to_groups, to_users=to_users)
        except Exception as e:
            logger.error(f"Error sending schedule change alert: {e}")
        await state.clear()
        dest_text = "в чат и в ЛС" if (to_groups and to_users) else ("в чат" if to_groups else "в ЛС")
        await callback.message.edit_text(
            f"📢 **Оповещение об изменении расписания успешно разослано ({dest_text})!**",
            reply_markup=get_admin_panel_keyboard(),
            parse_mode="Markdown"
        )
        try:
            await callback.answer("Разослано!")
        except Exception:
            pass


@router.callback_query(F.data == "sub_notify_no")
async def cb_sub_no_broadcast(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    is_sub = "sub_date" in data and "lesson_number" in data
    await state.clear()
    msg = "✅ Замена сохранена без массового оповещения." if is_sub else "🔇 Изменения сохранены без рассылки оповещения."
    await callback.message.edit_text(
        msg,
        reply_markup=get_admin_panel_keyboard()
    )
    try:
        await callback.answer()
    except Exception:
        pass


# ==================== SCHEDULE ON-DEMAND BROADCAST ====================

@router.callback_query(F.data == "admin_broadcast_schedule")
async def cb_admin_broadcast_schedule_start(callback: CallbackQuery, state: FSMContext, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return
    await state.set_state(ScheduleBroadcastStates.choosing_date)
    await callback.message.edit_text(
        "📢 **Рассылка расписания:**\n\n"
        "Какое расписание вы хотите скинуть?",
        reply_markup=get_schedule_broadcast_day_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(ScheduleBroadcastStates.choosing_date, F.data == "bcast_sched_day_today")
async def cb_bcast_sched_day_today(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return
    await _show_broadcast_schedule_preview(callback, state, db_session, get_today())


@router.callback_query(ScheduleBroadcastStates.choosing_date, F.data == "bcast_sched_day_tomorrow")
async def cb_bcast_sched_day_tomorrow(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return
    await _show_broadcast_schedule_preview(callback, state, db_session, get_today() + timedelta(days=1))


@router.callback_query(ScheduleBroadcastStates.choosing_date, F.data == "bcast_sched_day_cal")
async def cb_bcast_sched_day_cal(callback: CallbackQuery, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return
    today = get_today()
    kb = get_inline_calendar("adm_bsc_cal", year=today.year, month=today.month, back_callback="admin_broadcast_schedule")
    await callback.message.edit_text(
        "📅 **Выберите дату расписания на календаре:**",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("cal_nav_adm_bsc_cal_"))
async def cb_cal_nav_adm_bsc_cal(callback: CallbackQuery):
    parts = callback.data.split("_")
    year = int(parts[5])
    month = int(parts[6])
    kb = get_inline_calendar("adm_bsc_cal", year=year, month=month, back_callback="admin_broadcast_schedule")
    await callback.message.edit_text(
        "📅 **Выберите дату расписания на календаре:**",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("cal_act_adm_bsc_cal_"))
async def cb_cal_act_adm_bsc_cal(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return
    parts = callback.data.split("_")
    year = int(parts[5])
    month = int(parts[6])
    day = int(parts[7])
    target_d = date(year, month, day)
    await _show_broadcast_schedule_preview(callback, state, db_session, target_d)


async def _show_broadcast_schedule_preview(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, target_d: date):
    day_name = DAYS_RU.get(target_d.isoweekday(), "")
    date_str = target_d.strftime('%d.%m.%Y')
    sched_text = await format_day_schedule(db_session, target_d)

    await state.update_data(
        bcast_target_date=target_d.isoformat(),
        bcast_sched_text=sched_text,
        bcast_day_name=day_name,
        bcast_date_str=date_str
    )
    await state.set_state(ScheduleBroadcastStates.confirm_destination)

    preview = (
        f"📋 **Предпросмотр расписания для отправки:**\n\n"
        f"{sched_text}\n\n"
        f"📢 **Куда скинуть расписание?**"
    )
    await callback.message.edit_text(
        preview,
        reply_markup=get_schedule_broadcast_destination_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(ScheduleBroadcastStates.confirm_destination, F.data.startswith("bcast_sched_dest_"))
async def cb_admin_broadcast_schedule_send(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    dest = callback.data.replace("bcast_sched_dest_", "")
    data = await state.get_data()
    sched_text = data.get("bcast_sched_text")
    day_name = data.get("bcast_day_name", "")
    date_str = data.get("bcast_date_str", "")

    if not sched_text:
        await callback.answer("Ошибка: расписание не найдено", show_alert=True)
        await state.clear()
        return

    sent_pm = 0
    sent_groups = 0

    if dest in ["pm", "all"]:
        students = await get_notifiable_users(db_session)
        for s in students:
            try:
                await bot.send_message(chat_id=s.tg_id, text=sched_text, parse_mode="Markdown")
                sent_pm += 1
            except Exception:
                pass

    if dest in ["groups", "all"]:
        groups = await get_approved_group_chats(db_session)
        for g in groups:
            try:
                await bot.send_message(
                    chat_id=g.chat_id,
                    message_thread_id=g.topic_schedule_id,
                    text=sched_text,
                    parse_mode="Markdown"
                )
                sent_groups += 1
            except Exception:
                pass

    await state.clear()
    dest_text = "в чат и в ЛС" if dest == "all" else ("в чат" if dest == "groups" else "в ЛС")
    await callback.message.edit_text(
        f"✅ **Расписание на {day_name} ({date_str}) успешно отправлено ({dest_text})!**\n\n"
        f"👥 В беседы: {sent_groups}\n"
        f"👤 В ЛС: {sent_pm}",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Расписание отправлено!")
    except Exception:
        pass
