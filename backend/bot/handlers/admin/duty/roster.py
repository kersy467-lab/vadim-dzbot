import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud import (
    get_all_duty_groups, get_duty_group_by_number, create_or_update_duty_group,
    set_class_setting, get_current_duty_info, clear_all_duty_members, get_active_users,
    get_users_in_duty_group, get_approved_group_chats
)
from backend.bot.keyboards.admin_kb import (
    get_admin_panel_keyboard, get_cancel_keyboard, get_duty_broadcast_destination_keyboard
)
from backend.bot.handlers.admin.helpers import is_admin
from backend.bot.handlers.admin.states import ManageDutyStates, DutyBroadcastStates
from backend.bot.services.notifier import escape_md

logger = logging.getLogger(__name__)

router = Router(name='admin_duty_roster_router')



@router.callback_query(F.data == "admin_manage_duty")
async def cb_admin_manage_duty(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    active_group, all_groups = await get_current_duty_info(db_session)
    lines = ["🧹 **Управление дежурствами 11 «Б»:**\n"]
    if active_group:
        lines.append(f"⭐ **Текущая дежурная группа:** **{active_group.name}**\n")

    lines.append("📋 **Список всех групп:**")
    for g in all_groups:
        badge = " *(дежурит)*" if active_group and g.group_number == active_group.group_number else ""
        lines.append(f"• **{g.name}:** {g.members}{badge}")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Назначить дежурных", callback_data="adm_duty_pick_active"),
                InlineKeyboardButton(text="✏️ Изменить состав", callback_data="adm_duty_pick_edit")
            ],
            [
                InlineKeyboardButton(text="📢 Объявление дежурным", callback_data="admin_duty_broadcast"),
                InlineKeyboardButton(text="🗑 Очистить все составы", callback_data="adm_duty_clear_all")
            ],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="admin_menu_back")]
        ]
    )

    await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "adm_duty_clear_all")
async def cb_admin_duty_clear_all(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return
    await clear_all_duty_members(db_session)
    try:
        await callback.answer("Все составы групп очищены!")
    except Exception:
        pass
    await cb_admin_manage_duty(callback, db_session, current_user)


@router.callback_query(F.data == "adm_duty_pick_active")
async def cb_admin_duty_pick_active(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    all_groups = await get_all_duty_groups(db_session)
    btns = [[InlineKeyboardButton(text=f"⭐ {g.name}", callback_data=f"adm_duty_set_{g.group_number}")] for g in all_groups]
    btns.append([InlineKeyboardButton(text="🔄 Автоматически (по неделям)", callback_data="adm_duty_set_auto")])
    btns.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage_duty")])

    await callback.message.edit_text(
        "👥 **Выберите группу, которая дежурит сейчас:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_duty_set_"))
async def cb_admin_duty_set(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    val = callback.data.replace("adm_duty_set_", "")
    if val == "auto":
        await set_class_setting(db_session, "current_duty_group", "")
        msg_toast = "Установлена авто-ротация по неделям!"
    else:
        await set_class_setting(db_session, "current_duty_group", val)
        msg_toast = f"Назначена Группа {val}!"

    try:
        await callback.answer(msg_toast)
    except Exception:
        pass

    try:
        from backend.bot.services.notifier import notify_duty_change_if_needed
        await notify_duty_change_if_needed(callback.bot, db_session, force=True)
    except Exception as e:
        logger.warning(f"Could not notify duty change: {e}")

    await cb_admin_manage_duty(callback, db_session, current_user)


@router.callback_query(F.data == "adm_duty_pick_edit")
async def cb_admin_duty_pick_edit(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    all_groups = await get_all_duty_groups(db_session)
    btns = [[InlineKeyboardButton(text=f"✏️ {g.name}", callback_data=f"adm_duty_ed_{g.group_number}")] for g in all_groups]
    btns.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage_duty")])

    await state.set_state(ManageDutyStates.choosing_group_to_edit)
    await callback.message.edit_text(
        "✏️ **Состав какой группы вы хотите изменить?**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=btns),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


def build_duty_members_keyboard(students: list[User], selected_ids: list[int], g_num: int) -> InlineKeyboardMarkup:
    buttons = []
    # Кнопки со списком зарегистрированных учеников
    for s in students:
        is_sel = s.tg_id in selected_ids
        icon = "✅" if is_sel else "⬜"
        buttons.append([
            InlineKeyboardButton(
                text=f"{icon} {s.display_name}",
                callback_data=f"adm_dt_tog_{s.tg_id}"
            )
        ])

    sel_cnt = len(selected_ids)
    buttons.append([
        InlineKeyboardButton(
            text=f"💾 Сохранить состав ({sel_cnt} чел.)",
            callback_data="adm_dt_save_btn"
        )
    ])
    buttons.append([
        InlineKeyboardButton(text="✏️ Ввести текстом вручную", callback_data="adm_dt_ed_manual"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="adm_duty_pick_edit")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("adm_duty_ed_"))
async def cb_admin_duty_edit_chosen(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    g_num = int(callback.data.replace("adm_duty_ed_", ""))
    group = await get_duty_group_by_number(db_session, g_num)
    students = await get_active_users(db_session)

    selected_ids = list(group.member_ids or []) if group else []

    # Если member_ids еще пуст, но есть текстовый состав, пытаемся сопоставить
    if not selected_ids and group and group.members and group.members != "Состав не назначен":
        mem_lower = group.members.lower()
        for s in students:
            n1 = (s.custom_name or "").lower()
            n2 = (s.full_name or "").lower()
            p1 = [p.strip() for p in n1.split() if len(p.strip()) > 2]
            p2 = [p.strip() for p in n2.split() if len(p.strip()) > 2]
            if (n1 and (n1 in mem_lower or any(p in mem_lower for p in p1))) or \
               (n2 and (n2 in mem_lower or any(p in mem_lower for p in p2))):
                selected_ids.append(s.tg_id)

    await state.update_data(edit_duty_group=g_num, selected_duty_ids=selected_ids)
    await state.set_state(ManageDutyStates.selecting_members_buttons)

    curr_members = group.members if group and group.members else "не указаны"
    kb = build_duty_members_keyboard(students, selected_ids, g_num)

    await callback.message.edit_text(
        f"👥 **Выбор дежурных — {group.name if group else f'Группа {g_num}'}:**\n\n"
        f"Текущий состав:\n_{curr_members}_\n\n"
        "Нажимайте на кнопки учеников, чтобы отметить их как дежурных в этой группе (✅ / ⬜), затем нажмите кнопку сохранения:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_dt_tog_"))
async def cb_admin_duty_toggle(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    target_id = int(callback.data.replace("adm_dt_tog_", ""))
    data = await state.get_data()
    selected_ids = list(data.get("selected_duty_ids", []))
    g_num = data.get("edit_duty_group", 0)

    if target_id in selected_ids:
        selected_ids.remove(target_id)
    else:
        selected_ids.append(target_id)

    await state.update_data(selected_duty_ids=selected_ids)

    students = await get_active_users(db_session)
    kb = build_duty_members_keyboard(students, selected_ids, g_num)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "adm_dt_save_btn")
async def cb_admin_duty_save_btn(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    g_num = data.get("edit_duty_group", 0)
    selected_ids = list(data.get("selected_duty_ids", []))

    students = await get_active_users(db_session)
    st_map = {s.tg_id: s for s in students}
    chosen_students = [st_map[tid] for tid in selected_ids if tid in st_map]

    if chosen_students:
        members_str = ", ".join([s.display_name for s in chosen_students])
    else:
        members_str = "Состав не назначен"

    group_name = f"Группа {g_num}"
    await create_or_update_duty_group(
        session=db_session,
        group_number=g_num,
        name=group_name,
        members=members_str,
        member_ids=selected_ids
    )

    await state.clear()
    await callback.message.edit_text(
        f"✅ **Состав Группы {g_num} успешно сохранен!**\n\n👥 {members_str}",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Сохранено!")
    except Exception:
        pass


@router.callback_query(F.data == "adm_dt_ed_manual")
async def cb_admin_duty_ed_manual(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    g_num = data.get("edit_duty_group", 0)
    group = await get_duty_group_by_number(db_session, g_num)

    curr_members = group.members if group and group.members else "не указаны"
    await state.set_state(ManageDutyStates.entering_members)
    await callback.message.edit_text(
        f"✏️ **Ввод состава вручную — {group.name if group else f'Группа {g_num}'}:**\n\n"
        f"Текущий состав:\n_{curr_members}_\n\n"
        "Отправьте в ответ сообщение с новым списком учеников (через запятую):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(ManageDutyStates.entering_members)
async def msg_admin_duty_save_members(message: Message, state: FSMContext, db_session: AsyncSession):
    members = message.text.strip()
    if not members:
        await message.answer("⚠️ Состав группы не может быть пустым.")
        return

    data = await state.get_data()
    g_num = data.get("edit_duty_group", 0)
    group_name = f"Группа {g_num}"

    # Пытаемся автоматически сопоставить введенные имена с зарегистрированными учениками
    students = await get_active_users(db_session)
    matched_ids = []
    text_lower = members.lower()
    for s in students:
        n1 = (s.custom_name or "").lower()
        n2 = (s.full_name or "").lower()
        p1 = [p.strip() for p in n1.split() if len(p.strip()) > 2]
        p2 = [p.strip() for p in n2.split() if len(p.strip()) > 2]
        if (n1 and (n1 in text_lower or any(p in text_lower for p in p1))) or \
           (n2 and (n2 in text_lower or any(p in text_lower for p in p2))):
            matched_ids.append(s.tg_id)

    await create_or_update_duty_group(
        session=db_session,
        group_number=g_num,
        name=group_name,
        members=members,
        member_ids=matched_ids
    )

    await state.clear()
    await message.answer(
        f"✅ **Состав Группы {g_num} успешно обновлен!**\n\n👥 {members}",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )


