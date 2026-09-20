import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models import User
from backend.db.crud import get_all_users, get_user_by_tg_id, delete_user
from backend.bot.keyboards.admin_kb import get_admin_panel_keyboard
from backend.bot.handlers.admin.helpers import is_admin
from backend.bot.services.notifier import escape_md

logger = logging.getLogger(__name__)

router = Router(name="admin_users_delete_router")


@router.callback_query(F.data == "admin_delete_user")
async def cb_admin_delete_user_list(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    users = await get_all_users(db_session)
    deletable_users = [u for u in users if u.tg_id != settings.ADMIN_ID and u.tg_id != callback.from_user.id]

    if not deletable_users:
        await callback.message.edit_text(
            "ℹ️ В базе нет других пользователей, доступных для удаления.",
            reply_markup=get_admin_panel_keyboard()
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return

    buttons = []
    for u in deletable_users:
        uname = f" (@{u.username})" if u.username else ""
        role_badge = "👑 [Админ]" if u.role == "admin" else ("⏳ [Заявка]" if u.role == "pending" else ("❌ [Отклонен]" if u.role == "rejected" else "👤 [Ученик]"))
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {u.full_name[:18]}{uname} — {role_badge}",
                callback_data=f"adm_del_user_ask_{u.tg_id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="👥 К списку пользователей", callback_data="admin_view_students")])
    buttons.append([InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_menu_back")])

    await callback.message.edit_text(
        "🗑 **Удаление пользователя из базы бота**\n\n"
        "Выберите пользователя, которого нужно удалить.\n"
        "⚠️ _Пользователь будет полностью удален, его доступ аннулирован, а персональный чек-лист очищен._",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_del_user_ask_"))
async def cb_admin_delete_user_ask(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    target_tg_id = int(callback.data.replace("adm_del_user_ask_", ""))
    if target_tg_id == settings.ADMIN_ID:
        await callback.answer("Нельзя удалить главного администратора!", show_alert=True)
        return
    if target_tg_id == callback.from_user.id:
        await callback.answer("❌ Вы не можете удалить самого себя!", show_alert=True)
        return

    target_user = await get_user_by_tg_id(db_session, target_tg_id)
    if not target_user:
        await callback.answer("Пользователь не найден или уже удален", show_alert=True)
        from backend.bot.handlers.admin.users.list import cb_view_students
        await cb_view_students(callback, db_session)
        return

    uname = f"@{escape_md(target_user.username)}" if target_user.username else "без @username"
    safe_name = escape_md(target_user.full_name)
    role_name = "👑 Администратор" if target_user.role == "admin" else ("⏳ На рассмотрении" if target_user.role == "pending" else ("❌ Отклонен" if target_user.role == "rejected" else "👤 Ученик"))

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚠️ Да, удалить пользователя!",
                    callback_data=f"adm_del_user_confirm_{target_tg_id}"
                )
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_view_students")
            ]
        ]
    )

    try:
        await callback.message.edit_text(
            f"❓ **Подтверждение удаления пользователя**\n\n"
            f"👤 **Имя:** {safe_name}\n"
            f"🔗 **Telegram:** {uname}\n"
            f"🏷 **Роль:** {role_name}\n\n"
            "⚠️ _Пользователь потеряет доступ к боту. Если он снова нажмет /start, ему придется заново отправлять заявку на регистрацию._",
            reply_markup=kb,
            parse_mode="Markdown"
        )
    except Exception:
        await callback.message.edit_text(
            f"❓ Подтверждение удаления пользователя\n\n"
            f"👤 Имя: {target_user.full_name}\n"
            f"🔗 Telegram: {target_user.username or 'нет'}\n"
            f"🏷 Роль: {role_name}\n\n"
            "Пользователь потеряет доступ к боту.",
            reply_markup=kb
        )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_del_user_confirm_"))
async def cb_admin_delete_user_confirm(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    target_tg_id = int(callback.data.replace("adm_del_user_confirm_", ""))
    if target_tg_id == settings.ADMIN_ID:
        await callback.answer("Нельзя удалить главного администратора!", show_alert=True)
        return
    if target_tg_id == callback.from_user.id:
        await callback.answer("❌ Вы не можете удалить самого себя!", show_alert=True)
        return

    target_user = await get_user_by_tg_id(db_session, target_tg_id)
    user_name = target_user.full_name if target_user else f"ID {target_tg_id}"
    safe_user_name = escape_md(user_name)

    success = await delete_user(db_session, target_tg_id)
    if success:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👥 К списку пользователей", callback_data="admin_view_students")],
                [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_menu_back")]
            ]
        )
        try:
            await callback.message.edit_text(
                f"✅ **Пользователь {safe_user_name} успешно удален.**\n\n"
                "Его доступ к боту аннулирован, а персональный чек-лист очищен.",
                reply_markup=kb,
                parse_mode="Markdown"
            )
        except Exception:
            await callback.message.edit_text(
                f"✅ Пользователь {user_name} успешно удален.\n\n"
                "Его доступ к боту аннулирован, а персональный чек-лист очищен.",
                reply_markup=kb
            )
    else:
        await callback.message.edit_text(
            "⚠️ Не удалось удалить пользователя (возможно, он уже был удален).",
            reply_markup=get_admin_panel_keyboard()
        )
    try:
        await callback.answer()
    except Exception:
        pass
