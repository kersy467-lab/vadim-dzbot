import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud import get_active_users, get_user_by_tg_id, update_user_custom_name
from backend.bot.keyboards.admin_kb import get_admin_panel_keyboard, get_cancel_keyboard
from backend.bot.handlers.admin.helpers import is_admin
from backend.bot.handlers.admin.states import RenameUserStates
from backend.bot.services.notifier import escape_md

logger = logging.getLogger(__name__)

router = Router(name="admin_users_rename_router")


@router.callback_query(F.data == "admin_change_name")
async def cb_admin_change_name_list(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    students = await get_active_users(db_session)
    if not students:
        await callback.message.edit_text(
            "ℹ️ В базе пока нет зарегистрированных учеников.",
            reply_markup=get_admin_panel_keyboard()
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return

    buttons = []
    for s in students:
        uname = f" (@{s.username})" if s.username else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"✏️ {s.display_name}{uname}",
                callback_data=f"adm_ren_ask_{s.tg_id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_menu_back")])

    await callback.message.edit_text(
        "✏️ **Смена имени ученика в системе**\n\n"
        "Выберите ученика из списка ниже, чтобы изменить его отображаемое имя (оно показывается в Mini App и списках дежурных):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_ren_ask_"))
async def cb_admin_rename_ask(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    target_id = int(callback.data.replace("adm_ren_ask_", ""))
    user = await get_user_by_tg_id(db_session, target_id)

    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    await state.set_state(RenameUserStates.entering_name)
    await state.update_data(rename_target_tg_id=target_id)

    safe_name = escape_md(user.display_name)
    safe_uname = f"@{escape_md(user.username)}" if user.username else "без @username"

    md_text = (
        f"✏️ **Изменение имени ученика:**\n\n"
        f"Текущее имя: **{safe_name}**\n"
        f"Telegram: {safe_uname}\n\n"
        "Отправьте в ответ сообщение с новым именем и фамилией (например: `Иван Иванов`):"
    )

    try:
        await callback.message.edit_text(
            md_text,
            reply_markup=get_cancel_keyboard(),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Markdown error in cb_admin_rename_ask: {e}")
        plain_text = (
            f"✏️ Изменение имени ученика:\n\n"
            f"Текущее имя: {user.display_name}\n"
            f"Telegram: @{user.username if user.username else 'без @username'}\n\n"
            "Отправьте в ответ сообщение с новым именем и фамилией (например: Иван Иванов):"
        )
        try:
            await callback.message.edit_text(
                plain_text,
                reply_markup=get_cancel_keyboard()
            )
        except Exception as e2:
            logger.error(f"Failed to edit plain text in cb_admin_rename_ask: {e2}")

    try:
        await callback.answer()
    except Exception:
        pass


@router.message(RenameUserStates.entering_name)
async def msg_admin_rename_save(message: Message, state: FSMContext, db_session: AsyncSession):
    new_name = (message.text or "").strip()
    if not new_name or len(new_name) < 2:
        await message.answer("⚠️ Введите корректное имя и фамилию (не менее 2 символов):", reply_markup=get_cancel_keyboard())
        return

    data = await state.get_data()
    target_tg_id = data.get("rename_target_tg_id")
    if not target_tg_id:
        await state.clear()
        return

    await update_user_custom_name(db_session, target_tg_id, new_name)
    await state.clear()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить еще имя", callback_data="admin_change_name")],
            [InlineKeyboardButton(text="🔙 В панель управления", callback_data="admin_menu_back")]
        ]
    )
    safe_new_name = escape_md(new_name)
    try:
        await message.answer(
            f"✅ Имя ученика успешно изменено на: **{safe_new_name}**!\n\n"
            "Оно обновлено в системе, списках дежурных и Mini App.",
            reply_markup=kb,
            parse_mode="Markdown"
        )
    except Exception:
        await message.answer(
            f"✅ Имя ученика успешно изменено на: {new_name}!\n\n"
            "Оно обновлено в системе, списках дежурных и Mini App.",
            reply_markup=kb
        )
