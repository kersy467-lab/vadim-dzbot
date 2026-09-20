from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud import (
    get_all_subjects, get_subject_by_id, create_subject, delete_subject
)
from backend.bot.keyboards.admin_kb import get_admin_panel_keyboard, get_cancel_keyboard
from backend.bot.handlers.admin.helpers import is_admin
from backend.bot.handlers.admin.states import SubjectManagementStates

router = Router(name="admin_subjects_router")


@router.callback_query(F.data == "admin_manage_subjects")
async def cb_manage_subjects(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    subjects = await get_all_subjects(db_session)
    subj_list = "\n".join([f"{i}. {s.name}" for i, s in enumerate(subjects, 1)]) if subjects else "Список пуст"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Добавить предмет", callback_data="admin_add_subject_btn"),
                InlineKeyboardButton(text="🗑 Удалить предмет", callback_data="admin_del_subject_btn")
            ],
            [InlineKeyboardButton(text="🔙 В меню", callback_data="admin_menu_back")]
        ]
    )

    await callback.message.edit_text(
        f"📚 **Список предметов 11 «Б» ({len(subjects)}):**\n\n"
        f"{subj_list}\n\n"
        "Выберите действие:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "admin_add_subject_btn")
async def cb_start_add_subject(callback: CallbackQuery, state: FSMContext, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    await state.set_state(SubjectManagementStates.entering_new_name)
    await callback.message.edit_text(
        "➕ **Добавление нового предмета:**\n\n"
        "Напишите в чат точное название предмета (например: `Информатика` или `Астрономия`):",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(SubjectManagementStates.entering_new_name)
async def msg_save_subject(message: Message, state: FSMContext, db_session: AsyncSession):
    name = message.text.strip()
    if not name:
        await message.answer("⚠️ Название предмета не может быть пустым.")
        return

    await create_subject(db_session, name=name)
    await state.clear()
    await message.answer(
        f"✅ Предмет **«{name}»** успешно добавлен в список!",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin_del_subject_btn")
async def cb_start_del_subject(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    subjects = await get_all_subjects(db_session)
    if not subjects:
        await callback.answer("Список предметов пуст", show_alert=True)
        return

    buttons = [[InlineKeyboardButton(text=f"🗑 {s.name}", callback_data=f"adm_delsubj_{s.id}")] for s in subjects]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_manage_subjects")])

    await callback.message.edit_text(
        "🗑 **Выберите предмет для удаления:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_delsubj_"))
async def cb_confirm_del_subject(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    subj_id = int(callback.data.replace("adm_delsubj_", ""))
    subj = await get_subject_by_id(db_session, subj_id)
    name = subj.name if subj else "Предмет"

    await delete_subject(db_session, subj_id)
    try:
        await callback.answer(f"Предмет {name} удален!")
    except Exception:
        pass
    await cb_manage_subjects(callback, db_session, current_user)
