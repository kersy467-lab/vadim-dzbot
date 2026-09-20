import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud.polls import (
    get_active_polls,
    get_poll_by_id,
    get_poll_results_data,
    get_poll_non_voters,
    close_poll,
    delete_poll,
    format_poll_message_text,
)
from backend.bot.handlers.admin.helpers import is_admin
from backend.bot.services.notifier import escape_md

logger = logging.getLogger(__name__)

router = Router(name="admin_polls_manage_router")


@router.callback_query(F.data == "admin_polls_menu")
async def cb_admin_polls_menu(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    polls = await get_active_polls(db_session)
    buttons = [
        [InlineKeyboardButton(text="➕ Создать новый опрос", callback_data="admin_polls_create")]
    ]

    lines = [
        "📊 **Управление опросами класса 11 «Б»**\n",
        "Здесь вы можете создавать опросы, смотреть списки тех, кто ещё не проголосовал, "
        "отправлять им точечные напоминания в ЛС и завершать голосования.\n"
    ]

    if polls:
        lines.append(f"📋 **Активные опросы ({len(polls)}):**")
        for p in polls:
            votes_count = len(p.votes)
            short_q = p.question if len(p.question) <= 30 else f"{p.question[:28]}…"
            buttons.append([
                InlineKeyboardButton(
                    text=f"📊 {short_q} ({votes_count} гол.)",
                    callback_data=f"adm_poll_view_{p.id}"
                )
            ])
    else:
        lines.append("ℹ️ Сейчас нет активных открытых опросов.")

    buttons.append([InlineKeyboardButton(text="🔙 В панель управления", callback_data="admin_menu_back")])

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_poll_view_"))
async def cb_admin_poll_view(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    poll_id = int(callback.data.replace("adm_poll_view_", ""))
    results = await get_poll_results_data(db_session, poll_id)

    if not results:
        await callback.answer("Опрос не найден или удален.", show_alert=True)
        await cb_admin_polls_menu(callback, db_session, current_user)
        return

    poll_text = format_poll_message_text(results)
    buttons = [
        [
            InlineKeyboardButton(text="👥 Кто не голосовал", callback_data=f"adm_poll_nonvoters_{poll_id}"),
            InlineKeyboardButton(text="🔔 Напомнить в ЛС", callback_data=f"adm_poll_remind_{poll_id}"),
        ]
    ]

    if not results.get("is_anonymous"):
        buttons.append([
            InlineKeyboardButton(text="📋 Поименные голоса", callback_data=f"adm_poll_details_{poll_id}")
        ])

    if not results.get("is_closed"):
        buttons.append([
            InlineKeyboardButton(text="🔒 Завершить опрос", callback_data=f"adm_poll_close_{poll_id}")
        ])

    buttons.append([
        InlineKeyboardButton(text="🗑 Удалить опрос", callback_data=f"adm_poll_del_{poll_id}")
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 К списку опросов", callback_data="admin_polls_menu")
    ])

    await callback.message.edit_text(
        f"⚙️ **Панель управления опросом:**\n\n{poll_text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_poll_nonvoters_"))
async def cb_admin_poll_nonvoters(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    poll_id = int(callback.data.replace("adm_poll_nonvoters_", ""))
    poll = await get_poll_by_id(db_session, poll_id)
    if not poll:
        await callback.answer("Опрос не найден.", show_alert=True)
        return

    non_voters = await get_poll_non_voters(db_session, poll_id)

    lines = [
        f"👥 **Ожидаем голоса в опросе:**\n«{poll.question}»\n"
    ]

    if non_voters:
        lines.append(f"⏳ **Не проголосовали ({len(non_voters)} чел.):**")
        for i, u in enumerate(non_voters, 1):
            disp = escape_md(u.display_name)
            uname = f" (@{escape_md(u.username)})" if u.username else ""
            lines.append(f"{i}. {disp}{uname}")
    else:
        lines.append("🎉 **Все ученики класса уже проголосовали!**")

    buttons = []
    if non_voters and not poll.is_closed:
        buttons.append([
            InlineKeyboardButton(text="🔔 Отправить напоминание только им в ЛС", callback_data=f"adm_poll_remind_{poll_id}")
        ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Назад к опросу", callback_data=f"adm_poll_view_{poll_id}")
    ])

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_poll_remind_"))
async def cb_admin_poll_remind(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    poll_id = int(callback.data.replace("adm_poll_remind_", ""))
    poll = await get_poll_by_id(db_session, poll_id)
    if not poll or poll.is_closed:
        await callback.answer("Опрос завершён или не найден.", show_alert=True)
        return

    non_voters = await get_poll_non_voters(db_session, poll_id)
    if not non_voters:
        await callback.answer("Все ученики уже проголосовали!", show_alert=True)
        return

    remind_text = (
        "🔔 **Напоминание от старосты / администратора:**\n\n"
        f"Ты ещё не проголосовал в важном опросе класса:\n"
        f"**«{poll.question}»**\n\n"
        "Пожалуйста, зайди в беседу класса (топик **«Важные объявления»**) и выбери свой вариант! 🗳"
    )

    sent_count = 0
    for u in non_voters:
        try:
            await callback.bot.send_message(
                chat_id=u.tg_id,
                text=remind_text,
                parse_mode="Markdown"
            )
            sent_count += 1
        except Exception as e:
            logger.warning(f"Failed to send poll reminder to {u.tg_id}: {e}")

    await callback.answer(f"✅ Напоминание отправлено {sent_count} ученикам в ЛС!", show_alert=True)
    await cb_admin_poll_view(callback, db_session, current_user)


@router.callback_query(F.data.startswith("adm_poll_details_"))
async def cb_admin_poll_details(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    poll_id = int(callback.data.replace("adm_poll_details_", ""))
    results = await get_poll_results_data(db_session, poll_id)
    if not results or results.get("is_anonymous"):
        await callback.answer("Детализация недоступна для анонимного опроса.", show_alert=True)
        return

    lines = [
        f"📋 **Поименные результаты опроса:**\n«{results['question']}»\n"
    ]

    for opt in results.get("options", []):
        voters = opt.get("voters", [])
        voters_str = ", ".join(escape_md(v) for v in voters) if voters else "_пока нет голосов_"
        lines.append(f"**{opt['order_index']}. {opt['text']}** ({opt['count']} чел.):")
        lines.append(f"{voters_str}\n")

    buttons = [
        [InlineKeyboardButton(text="🔙 Назад к опросу", callback_data=f"adm_poll_view_{poll_id}")]
    ]

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_poll_close_"))
async def cb_admin_poll_close(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    poll_id = int(callback.data.replace("adm_poll_close_", ""))
    poll = await close_poll(db_session, poll_id)
    if not poll:
        await callback.answer("Опрос не найден.", show_alert=True)
        return

    # Обновляем сообщения в группах: убираем инлайн-кнопки и закрепляем статус "ОПРОС ЗАВЕРШЁН"
    results = await get_poll_results_data(db_session, poll_id)
    final_text = format_poll_message_text(results)

    for msg_info in poll.dispatched_messages:
        try:
            await callback.bot.edit_message_text(
                chat_id=msg_info["chat_id"],
                message_id=msg_info["message_id"],
                text=final_text,
                reply_markup=None,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.warning(f"Could not edit closed poll msg in {msg_info}: {e}")

    await callback.answer("🔒 Опрос успешно завершён. Кнопки в беседе сняты.", show_alert=True)
    await cb_admin_poll_view(callback, db_session, current_user)


@router.callback_query(F.data.startswith("adm_poll_del_"))
async def cb_admin_poll_delete(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    poll_id = int(callback.data.replace("adm_poll_del_", ""))
    await delete_poll(db_session, poll_id)
    await callback.answer("🗑 Опрос удален.", show_alert=True)
    await cb_admin_polls_menu(callback, db_session, current_user)
