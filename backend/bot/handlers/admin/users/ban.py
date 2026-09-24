import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models import User
from backend.db.crud import get_banned_users, get_all_users, get_user_by_tg_id, update_user_role
from backend.bot.handlers.admin.helpers import is_admin
from backend.bot.services.notifier import escape_md
from backend.api.public_access import invalidate_access_cache

logger = logging.getLogger(__name__)
router = Router(name="admin_users_ban_router")

BAN_PER_PAGE = 5
PICK_PER_PAGE = 6


@router.callback_query(F.data == "admin_view_banlist")
@router.callback_query(F.data.startswith("adm_banlist_page_"))
async def cb_admin_view_banlist(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    page = 0
    if callback.data and callback.data.startswith("adm_banlist_page_"):
        try:
            page = int(callback.data.replace("adm_banlist_page_", ""))
        except ValueError:
            page = 0

    banned_users = await get_banned_users(db_session)
    total_banned = len(banned_users)

    if total_banned == 0:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Забанить пользователя", callback_data="adm_ban_pick_user")],
            [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_menu_back")]
        ])
        await callback.message.edit_text(
            "🚫 **Бан-лист класса 11 «Б» пуст**\n\n"
            "В данный момент нет заблокированных пользователей. "
            "Вы можете забанить пользователя вручную, нажав кнопку ниже.",
            reply_markup=kb, parse_mode="Markdown"
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return

    total_pages = max(1, (total_banned + BAN_PER_PAGE - 1) // BAN_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    page_banned = banned_users[page * BAN_PER_PAGE : (page + 1) * BAN_PER_PAGE]

    lines = [
        f"🚫 **Бан-лист 11 «Б» (Стр. {page + 1}/{total_pages}, всего {total_banned}):**\n",
        "Заблокированные пользователи не могут пользоваться ботом и отправлять заявки:\n"
    ]

    buttons = []
    start_idx = page * BAN_PER_PAGE + 1
    for idx, u in enumerate(page_banned, start=start_idx):
        safe_name = escape_md(u.full_name)
        uname = f" (@{escape_md(u.username)})" if u.username else ""
        lines.append(f"{idx}. {safe_name}{uname} — ID: `{u.tg_id}`")
        buttons.append([InlineKeyboardButton(text=f"♻️ Разбанить: {u.display_name[:20]}", callback_data=f"adm_unban_ask_{u.tg_id}")])

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_banlist_page_{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"Стр. {page + 1}/{total_pages}", callback_data="noop_page"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"adm_banlist_page_{page + 1}"))
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="➕ Забанить пользователя", callback_data="adm_ban_pick_user")])
    buttons.append([InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_menu_back")])

    try:
        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Markdown error in banlist: {e}")
        plain = "\n".join([l.replace("*", "").replace("`", "").replace("\\", "") for l in lines])
        await callback.message.edit_text(plain, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_unban_ask_"))
async def cb_admin_unban_ask(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    target_tg_id = int(callback.data.replace("adm_unban_ask_", ""))
    target_user = await get_user_by_tg_id(db_session, target_tg_id)
    if not target_user:
        await callback.answer("Пользователь не найден!", show_alert=True)
        return

    safe_name = escape_md(target_user.full_name)
    uname = f"@{escape_md(target_user.username)}" if target_user.username else "без @username"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👢 Кикнуть (сможет подать заявку через /start)", callback_data=f"adm_unban_kick_{target_tg_id}")],
        [InlineKeyboardButton(text="🎓 Сразу вернуть доступ ученика", callback_data=f"adm_unban_student_{target_tg_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_view_banlist")]
    ])

    await callback.message.edit_text(
        f"❓ **Разблокировка пользователя**\n\n"
        f"👤 **Имя:** {safe_name}\n"
        f"🔗 **Telegram:** {uname}\n"
        f"🆔 **ID:** `{target_user.tg_id}`\n\n"
        "Выберите режим разбана:\n"
        "1. **Кикнуть** — блокировка снимается, но доступ пока закрыт. Пользователь сможет нажать /start и подать повторную заявку.\n"
        "2. **Вернуть доступ** — пользователь сразу восстанавливается в ученики класса.",
        reply_markup=kb, parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_unban_kick_"))
async def cb_admin_unban_kick(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    target_tg_id = int(callback.data.replace("adm_unban_kick_", ""))
    target_user = await get_user_by_tg_id(db_session, target_tg_id)
    if not target_user:
        await callback.answer("Пользователь не найден!", show_alert=True)
        return

    await update_user_role(db_session, target_tg_id, "kicked")
    invalidate_access_cache(target_tg_id)

    name = target_user.display_name
    await callback.answer(f"Пользователь {name} разбанен со статусом «Кикнут»!", show_alert=True)
    await cb_admin_view_banlist(callback, db_session, current_user)


@router.callback_query(F.data.startswith("adm_unban_student_"))
async def cb_admin_unban_student(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    target_tg_id = int(callback.data.replace("adm_unban_student_", ""))
    target_user = await get_user_by_tg_id(db_session, target_tg_id)
    if not target_user:
        await callback.answer("Пользователь не найден!", show_alert=True)
        return

    await update_user_role(db_session, target_tg_id, "student")
    invalidate_access_cache(target_tg_id)

    try:
        from backend.bot.services.commands import set_user_command_scope
        await set_user_command_scope(
            callback.bot,
            chat_id=target_tg_id,
            is_tester=bool(getattr(target_user, "is_tester", False)),
            is_admin=False,
            full_access=True
        )
    except Exception:
        pass

    try:
        from backend.bot.keyboards.main_menu import get_main_keyboard
        await callback.bot.send_message(
            chat_id=target_tg_id,
            text=(
                "🎉 **Ваш аккаунт разблокирован администратором!**\n\n"
                "Вам снова открыт доступ к расписанию, домашним заданиям и Mini App класса."
            ),
            reply_markup=get_main_keyboard(
                is_admin=False,
                user_id=target_tg_id,
                is_tester=bool(getattr(target_user, "is_tester", False)),
                flag_b=bool(getattr(target_user, "flag_b", False))
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.warning(f"Could not notify unbanned user {target_tg_id}: {e}")

    name = target_user.display_name
    await callback.answer(f"Пользователь {name} разбанен и восстановлен в ученики!", show_alert=True)
    await cb_admin_view_banlist(callback, db_session, current_user)


@router.callback_query(F.data == "adm_ban_pick_user")
@router.callback_query(F.data.startswith("adm_ban_pick_page_"))
async def cb_admin_ban_pick_user(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    page = 0
    if callback.data and callback.data.startswith("adm_ban_pick_page_"):
        try:
            page = int(callback.data.replace("adm_ban_pick_page_", ""))
        except ValueError:
            page = 0

    all_users = await get_all_users(db_session)
    eligible = [
        u for u in all_users
        if u.tg_id != settings.ADMIN_ID
        and u.tg_id != callback.from_user.id
        and u.role != "rejected"
    ]

    if not eligible:
        await callback.answer("Нет пользователей, доступных для блокировки.", show_alert=True)
        return

    total_eligible = len(eligible)
    total_pages = max(1, (total_eligible + PICK_PER_PAGE - 1) // PICK_PER_PAGE)
    page = max(0, min(page, total_pages - 1))
    page_users = eligible[page * PICK_PER_PAGE : (page + 1) * PICK_PER_PAGE]

    buttons = []
    for u in page_users:
        uname = f" (@{u.username})" if u.username else ""
        role_label = "👑 Админ" if u.role == "admin" else ("⏳ Заявка" if u.role == "pending" else ("👢 Кикнут" if u.role == "kicked" else "👤 Ученик"))
        buttons.append([InlineKeyboardButton(text=f"🚫 {u.display_name[:18]}{uname} — {role_label}", callback_data=f"adm_ban_ask_{u.tg_id}")])

    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"adm_ban_pick_page_{page - 1}"))
        nav.append(InlineKeyboardButton(text=f"Стр. {page + 1}/{total_pages}", callback_data="noop_page"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="Вперёд ▶️", callback_data=f"adm_ban_pick_page_{page + 1}"))
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="🔙 К бан-листу", callback_data="admin_view_banlist")])

    await callback.message.edit_text(
        "🚫 **Выбор пользователя для блокировки**\n\n"
        "Выберите пользователя, которого хотите отправить в бан-лист:\n"
        "⚠️ _Забаненный пользователь будет исключен, бот перестанет ему отвечать, а отправка повторных заявок станет недоступной._",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_ban_ask_"))
async def cb_admin_ban_ask(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    target_tg_id = int(callback.data.replace("adm_ban_ask_", ""))
    if target_tg_id == settings.ADMIN_ID:
        await callback.answer("Нельзя забанить главного администратора!", show_alert=True)
        return
    if target_tg_id == callback.from_user.id:
        await callback.answer("Вы не можете забанить самого себя!", show_alert=True)
        return

    target_user = await get_user_by_tg_id(db_session, target_tg_id)
    if not target_user:
        await callback.answer("Пользователь не найден!", show_alert=True)
        return

    safe_name = escape_md(target_user.full_name)
    uname = f"@{escape_md(target_user.username)}" if target_user.username else "без @username"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Да, забанить пользователя!", callback_data=f"adm_ban_confirm_{target_tg_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_view_banlist")]
    ])

    await callback.message.edit_text(
        f"❓ **Подтверждение блокировки**\n\n"
        f"👤 **Имя:** {safe_name}\n"
        f"🔗 **Telegram:** {uname}\n"
        f"🆔 **ID:** `{target_user.tg_id}`\n\n"
        "⚠️ Пользователь будет добавлен в **бан-лист**. "
        "Бот перестанет отвечать на его сообщения, доступ к Mini App будет заблокирован, "
        "а подать повторную заявку он **не сможет**.",
        reply_markup=kb, parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_ban_confirm_"))
async def cb_admin_ban_confirm(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    target_tg_id = int(callback.data.replace("adm_ban_confirm_", ""))
    if target_tg_id in (settings.ADMIN_ID, callback.from_user.id):
        await callback.answer("Действие отклонено!", show_alert=True)
        return

    target_user = await get_user_by_tg_id(db_session, target_tg_id)
    if not target_user:
        await callback.answer("Пользователь не найден!", show_alert=True)
        return

    await update_user_role(db_session, target_tg_id, "rejected")
    target_user.is_classmate = False
    await db_session.commit()

    invalidate_access_cache(target_tg_id)

    try:
        from backend.bot.services.commands import set_user_command_scope
        await set_user_command_scope(callback.bot, chat_id=target_tg_id, is_tester=False, is_admin=False, full_access=False)
    except Exception:
        pass

    safe_name = escape_md(target_user.display_name)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 К бан-листу", callback_data="admin_view_banlist")],
        [InlineKeyboardButton(text="👥 К списку пользователей", callback_data="admin_view_students")],
        [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_menu_back")]
    ])

    await callback.message.edit_text(
        f"🚫 **Пользователь {safe_name} успешно заблокирован (в бан-листе).**\n\n"
        "Его доступ к боту и Mini App закрыт. Бот не будет отвечать на его команды, "
        "а повторные заявки заблокированы.",
        reply_markup=kb, parse_mode="Markdown"
    )
    try:
        await callback.answer("Пользователь забанен!")
    except Exception:
        pass
