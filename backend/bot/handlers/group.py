from datetime import date, timedelta
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, ChatMemberUpdated,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import ChatMemberUpdatedFilter, JOIN_TRANSITION
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings, get_today
from backend.db.crud import (
    get_group_chat_by_id, create_or_update_group_chat,
    update_group_chat_role, get_homework_for_date,
    get_bell_schedule, get_bell_schedule_for_date, get_upcoming_deadlines
)
from backend.bot.handlers.schedule import format_day_schedule

router = Router(name="group_router")


def get_admin_chat_approval_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить чат", callback_data=f"admin_chat_approve_{chat_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_chat_reject_{chat_id}")
            ]
        ]
    )

# 1. Event: Bot added to group
@router.my_chat_member(
    ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION),
    F.chat.type.in_({"group", "supergroup"})
)
async def on_bot_added_to_group(event: ChatMemberUpdated, db_session: AsyncSession, bot: Bot):
    chat = event.chat
    inviter = event.from_user

    # Only process actual group and supergroup chats
    if chat.type not in ["group", "supergroup"]:
        return

    # Register group chat as pending
    await create_or_update_group_chat(
        session=db_session,
        chat_id=chat.id,
        title=chat.title or "Групповой чат",
        chat_type=chat.type,
        added_by=inviter.id if inviter else None,
        role="pending"
    )

    # Greet in the group
    await bot.send_message(
        chat_id=chat.id,
        text=(
            f"👋 **Здравствуйте!** Бот класса успешно добавлен в **{chat.title}**!\n\n"
            "⏳ Заявка на авторизацию чата отправлена администратору. "
            "После одобрения бот сможет присылать домашку, расписание и звонки по командам и по расписанию."
        ),
        parse_mode="Markdown"
    )

    # Notify all admins
    from backend.bot.services.notifier import notify_all_admins
    inviter_name = inviter.full_name if inviter else "Неизвестно"
    inviter_uname = f"@{inviter.username}" if inviter and inviter.username else ""
    
    admin_text = (
        "🔔 **Новая заявка на авторизацию группового чата!**\n\n"
        f"👥 **Группа:** {chat.title}\n"
        f"🆔 **ID чата:** `{chat.id}`\n"
        f"👤 **Добавил:** {inviter_name} {inviter_uname}"
    )
    await notify_all_admins(
        bot=bot,
        session=db_session,
        text=admin_text,
        reply_markup=get_admin_chat_approval_keyboard(chat.id)
    )

# Admin approve group callback
@router.callback_query(F.data.startswith("admin_chat_approve_"))
async def cb_admin_approve_chat(callback: CallbackQuery, db_session: AsyncSession, bot: Bot):
    chat_id = int(callback.data.replace("admin_chat_approve_", ""))
    existing_chat = await get_group_chat_by_id(db_session, chat_id)
    if not existing_chat:
        await callback.answer("Чат не найден", show_alert=True)
        return
    if existing_chat.role != "pending":
        await callback.answer(f"Заявка чата уже обработана (статус: {existing_chat.role})!", show_alert=True)
        return

    chat = await update_group_chat_role(db_session, chat_id, "approved")

    await callback.message.edit_text(
        f"{callback.message.text}\n\n✅ **ЧАТ ОДОБРЕН** администратором {callback.from_user.full_name}",
        parse_mode="Markdown"
    )
    await callback.answer("Чат успешно авторизован!")

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "🎉 **Этот чат успешно авторизован администратором!**\n\n"
                "Бот подключен к чату 11 «Б». "
                "Каждый вечер в 18:30 сюда автоматически приходит дайджест с расписанием и домашним заданием на следующий день, "
                "а также оперативные уведомления о любых заменах!"
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Failed to notify group {chat_id}: {e}")

# Admin reject group callback
@router.callback_query(F.data.startswith("admin_chat_reject_"))
async def cb_admin_reject_chat(callback: CallbackQuery, db_session: AsyncSession, bot: Bot):
    chat_id = int(callback.data.replace("admin_chat_reject_", ""))
    existing_chat = await get_group_chat_by_id(db_session, chat_id)
    if not existing_chat:
        await callback.answer("Чат не найден", show_alert=True)
        return
    if existing_chat.role != "pending":
        await callback.answer(f"Заявка чата уже обработана (статус: {existing_chat.role})!", show_alert=True)
        return

    await update_group_chat_role(db_session, chat_id, "rejected")

    await callback.message.edit_text(
        f"{callback.message.text}\n\n❌ **ЧАТ ОТКЛОНЕН** администратором {callback.from_user.full_name}",
        parse_mode="Markdown"
    )
    await callback.answer("Чат отклонен!")


