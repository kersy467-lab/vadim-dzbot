import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.crud import (
    get_pending_users, get_pending_group_chats, get_active_users,
    get_approved_group_chats
)
from backend.bot.keyboards.admin_kb import get_admin_panel_keyboard
from backend.bot.keyboards.inline import get_admin_approval_keyboard
from backend.bot.handlers.group import get_admin_chat_approval_keyboard
from backend.bot.handlers.admin.logging import is_logged
from backend.bot.services.notifier import escape_md

logger = logging.getLogger(__name__)

router = Router(name="admin_users_list_router")


@router.callback_query(F.data == "admin_view_pending")
async def cb_view_pending(callback: CallbackQuery, db_session: AsyncSession):
    pending_users = await get_pending_users(db_session)
    pending_groups = await get_pending_group_chats(db_session)

    if not pending_users and not pending_groups:
        await callback.message.edit_text(
            "✅ Нет заявок, ожидающих рассмотрения.",
            reply_markup=get_admin_panel_keyboard()
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return

    await callback.message.edit_text(
        f"👥 **Заявок на рассмотрении:** {len(pending_users)} учеников, {len(pending_groups)} групп\n"
    )

    for u in pending_users:
        safe_full_name = escape_md(u.full_name)
        uname = f"@{escape_md(u.username)}" if u.username else "без @username"
        msg_text = f"👤 **Ученик:** {safe_full_name}\n🔗 **Telegram:** {uname}"
        kb = get_admin_approval_keyboard(u.tg_id)
        try:
            await callback.message.answer(
                msg_text,
                reply_markup=kb,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Markdown error sending pending user {u.tg_id}: {e}")
            try:
                plain = f"👤 Ученик: {u.full_name}\n🔗 Telegram: {u.username or 'без @username'}"
                await callback.message.answer(plain, reply_markup=kb)
            except Exception as e2:
                logger.error(f"Failed to send plain pending user {u.tg_id}: {e2}")

    for g in pending_groups:
        safe_title = escape_md(g.title)
        kb_g = get_admin_chat_approval_keyboard(g.chat_id)
        try:
            await callback.message.answer(
                f"👥 **Группа:** {safe_title}",
                reply_markup=kb_g,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Markdown error sending pending group {g.chat_id}: {e}")
            try:
                await callback.message.answer(f"👥 Группа: {g.title}", reply_markup=kb_g)
            except Exception as e2:
                logger.error(f"Failed to send plain pending group {g.chat_id}: {e2}")

    try:
        await callback.answer()
    except Exception:
        pass


STUDENTS_PER_PAGE = 8


@router.callback_query(F.data == "noop_page")
async def cb_noop_page(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "admin_view_students")
@router.callback_query(F.data.startswith("adm_students_page_"))
async def cb_view_students(callback: CallbackQuery, db_session: AsyncSession, page: int = 0):
    if callback.data and callback.data.startswith("adm_students_page_"):
        try:
            page = int(callback.data.replace("adm_students_page_", ""))
        except ValueError:
            page = 0

    students = await get_active_users(db_session)
    groups = await get_approved_group_chats(db_session)

    total_students = len(students)
    total_pages = max(1, (total_students + STUDENTS_PER_PAGE - 1) // STUDENTS_PER_PAGE)
    page = max(0, min(page, total_pages - 1))

    page_students = students[page * STUDENTS_PER_PAGE : (page + 1) * STUDENTS_PER_PAGE]

    buttons = []
    lines = [f"📋 **Управление правами доступа 11 «Б» (Стр. {page + 1}/{total_pages}):**\n"]
    lines.append(f"👤 **Ученики (всего {total_students}):**")

    start_idx = page * STUDENTS_PER_PAGE + 1
    for i, s in enumerate(page_students, start=start_idx):
        role_label = "👑 [Админ]" if s.role == "admin" else "👤 [Ученик]"
        tester_badge = " 🧪 [Тестер]" if getattr(s, "is_tester", False) else ""
        safe_disp = escape_md(s.display_name)
        uname = f" (@{escape_md(s.username)})" if s.username else ""
        lines.append(f"{i}. {safe_disp}{uname} — {role_label}{tester_badge}")

        tester_icon = "🧪 ✅" if getattr(s, "is_tester", False) else "🧪 ⬜"
        toggle_role_text = "👑 Снять админа" if s.role == "admin" else "👑 Сделать админом"
        log_icon = "🔴 Лог" if is_logged(s.tg_id) else "🔍 Лог"

        # 1-й ряд: ник и смена роли (сохраняем текущую страницу пагинации)
        buttons.append([
            InlineKeyboardButton(text=f"✏️ {s.display_name[:12]}", callback_data=f"adm_ren_ask_{s.tg_id}"),
            InlineKeyboardButton(text=toggle_role_text, callback_data=f"adm_toggle_role_{s.tg_id}_{page}"),
        ])
        # 2-й ряд: тестер, удаление, просмотр логов
        buttons.append([
            InlineKeyboardButton(text=tester_icon, callback_data=f"adm_tog_test_{s.tg_id}_{page}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"adm_del_user_ask_{s.tg_id}"),
            InlineKeyboardButton(text=log_icon, callback_data=f"adm_log_open_{s.tg_id}")
        ])

    # Панель пагинации страниц
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_students_page_{page - 1}"))
        nav_row.append(InlineKeyboardButton(text=f"Стр. {page + 1}/{total_pages}", callback_data="noop_page"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"adm_students_page_{page + 1}"))
        buttons.append(nav_row)

    if groups:
        lines.append(f"\n👥 **Авторизованные группы ({len(groups)}):**")
        for j, g in enumerate(groups, start=1):
            lines.append(f"{j}. {escape_md(g.title)} (ID: `{g.chat_id}`)")

    buttons.append([InlineKeyboardButton(text="🗑 Удалить пользователя", callback_data="admin_delete_user")])
    buttons.append([InlineKeyboardButton(text="🔙 В меню", callback_data="admin_menu_back")])

    try:
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Markdown error in cb_view_students: {e}")
        plain_lines = [l.replace("*", "").replace("`", "").replace("\\", "") for l in lines]
        await callback.message.edit_text(
            "\n".join(plain_lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )
    try:
        await callback.answer()
    except Exception:
        pass
