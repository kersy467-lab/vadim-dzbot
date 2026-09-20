import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models import User
from backend.db.crud import get_user_by_tg_id, update_user_role, update_user_tester_status
from backend.bot.keyboards.main_menu import get_main_keyboard
from backend.bot.handlers.admin.helpers import is_admin

logger = logging.getLogger(__name__)

router = Router(name="admin_users_roles_router")


@router.callback_query(F.data.startswith("adm_toggle_role_"))
async def cb_toggle_user_role(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    parts = callback.data.replace("adm_toggle_role_", "").split("_")
    target_id = int(parts[0])
    page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

    if target_id == callback.from_user.id:
        await callback.answer("❌ Вы не можете снять права администратора с самого себя!", show_alert=True)
        return

    user = await get_user_by_tg_id(db_session, target_id)
    if user and user.tg_id != settings.ADMIN_ID:
        new_role = "student" if user.role == "admin" else "admin"
        await update_user_role(db_session, target_id, new_role)
        role_label = "Администратор" if new_role == "admin" else "Ученик"
        try:
            await callback.answer(f"Роль изменена на: {role_label}!", show_alert=True)
        except Exception:
            pass

        # Отправляем уведомление и моментально обновляем меню у пользователя
        if new_role == "admin":
            try:
                await callback.bot.send_message(
                    chat_id=target_id,
                    text=(
                        "👑 **Вам предоставлены права администратора класса 11 «Б»!**\n\n"
                        "Вам открыт доступ к **«👑 Панель управления»** (появилась в кнопках внизу чата). "
                        "Вы можете редактировать расписание уроков, звонков и домашние задания."
                    ),
                    reply_markup=get_main_keyboard(is_admin=True, user_id=target_id),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Could not notify new admin: {e}")
        else:
            try:
                await callback.bot.send_message(
                    chat_id=target_id,
                    text="ℹ️ Ваши права администратора были отозваны. Панель управления закрыта.",
                    reply_markup=get_main_keyboard(is_admin=False, user_id=target_id),
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.warning(f"Could not notify demoted admin: {e}")

        # Обновляем сообщение со списком учеников на той же странице
        from backend.bot.handlers.admin.users.list import cb_view_students
        await cb_view_students(callback, db_session, page=page)
    else:
        await callback.answer("Невозможно изменить права главного создателя", show_alert=True)


@router.callback_query(F.data.startswith("adm_tog_test_"))
async def cb_toggle_user_tester(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    parts = callback.data.replace("adm_tog_test_", "").split("_")
    target_id = int(parts[0])
    page = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

    user = await get_user_by_tg_id(db_session, target_id)
    if user:
        new_status = not bool(getattr(user, "is_tester", False))
        await update_user_tester_status(db_session, target_id, new_status)
        state_str = "выдан (Тестер)" if new_status else "снят"
        try:
            await callback.answer(f"Доступ к закрытому тестированию {state_str}!", show_alert=True)
        except Exception:
            pass
        from backend.bot.handlers.admin.users.list import cb_view_students
        await cb_view_students(callback, db_session, page=page)
    else:
        try:
            await callback.answer("Пользователь не найден", show_alert=True)
        except Exception:
            pass
