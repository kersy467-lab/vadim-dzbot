import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud import get_notifiable_users, get_approved_group_chats
from backend.bot.keyboards.admin_kb import (
    get_admin_panel_keyboard, get_cancel_keyboard, get_broadcast_destination_keyboard
)
from backend.bot.handlers.admin.helpers import is_admin
from backend.bot.handlers.admin.states import BroadcastStates

logger = logging.getLogger(__name__)

router = Router(name="admin_broadcast_router")


@router.callback_query(F.data == "admin_broadcast_custom")
async def cb_admin_broadcast_custom_start(callback: CallbackQuery, state: FSMContext, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return
    await state.set_state(BroadcastStates.entering_message)
    await callback.message.edit_text(
        "📢 **Создание срочного объявления для 11 «Б»**\n\n"
        "Отправьте текст объявления, которое необходимо разослать.\n\n"
        "💡 _Поддерживается форматирование (жирный, курсив, списки). Также можно отправить файл или медиа (фото, PDF, документ, видео, аудио) с текстом в описании._",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(BroadcastStates.entering_message)
async def msg_admin_broadcast_text(message: Message, state: FSMContext, current_user: User):
    if not is_admin(current_user, message.from_user.id):
        return

    text = message.text or message.caption or ""
    attachment_type = None
    file_id = None
    file_name = None

    if message.photo:
        attachment_type = "photo"
        file_id = message.photo[-1].file_id
    elif message.document:
        attachment_type = "document"
        file_id = message.document.file_id
        file_name = message.document.file_name or "документ"
    elif message.video:
        attachment_type = "video"
        file_id = message.video.file_id
        file_name = message.video.file_name or "видео"
    elif message.audio:
        attachment_type = "audio"
        file_id = message.audio.file_id
        file_name = message.audio.file_name or "аудио"

    if not text and not attachment_type:
        await message.answer("⚠️ Пожалуйста, введите текст объявления или отправьте файл (фото, PDF, документ, видео) с описанием:")
        return

    photo_id = file_id if attachment_type == "photo" else None
    await state.update_data(
        broadcast_text=text,
        photo_id=photo_id,
        attachment_type=attachment_type,
        attachment_file_id=file_id,
        attachment_file_name=file_name
    )
    await state.set_state(BroadcastStates.confirm_destination)

    type_label = {
        "photo": "фото",
        "document": f"файл ({file_name})" if file_name else "документ",
        "video": "видео",
        "audio": "аудио"
    }.get(attachment_type, "файл")

    preview_text = text if text else f"*(без текста, только {type_label})*"
    prompt_text = (
        "👀 **Предпросмотр объявления:**\n"
        "──────────────────────\n"
        f"{preview_text}\n"
        "──────────────────────\n\n"
        "Куда отправить это объявление?"
    )

    if attachment_type == "photo":
        await message.answer_photo(
            photo=file_id,
            caption=prompt_text,
            reply_markup=get_broadcast_destination_keyboard(),
            parse_mode="Markdown"
        )
    elif attachment_type == "document":
        await message.answer_document(
            document=file_id,
            caption=prompt_text,
            reply_markup=get_broadcast_destination_keyboard(),
            parse_mode="Markdown"
        )
    elif attachment_type == "video":
        await message.answer_video(
            video=file_id,
            caption=prompt_text,
            reply_markup=get_broadcast_destination_keyboard(),
            parse_mode="Markdown"
        )
    elif attachment_type == "audio":
        await message.answer_audio(
            audio=file_id,
            caption=prompt_text,
            reply_markup=get_broadcast_destination_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            prompt_text,
            reply_markup=get_broadcast_destination_keyboard(),
            parse_mode="Markdown"
        )


@router.callback_query(BroadcastStates.confirm_destination, F.data.startswith("bcast_dest_"))
async def cb_admin_broadcast_send(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    dest = callback.data.replace("bcast_dest_", "")
    data = await state.get_data()
    raw_text = data.get("broadcast_text", "")
    photo_id = data.get("photo_id")
    attachment_type = data.get("attachment_type") or ("photo" if photo_id else None)
    file_id = data.get("attachment_file_id") or photo_id

    author_name = current_user.full_name or callback.from_user.full_name or "Администрация"
    final_text = (
        "📢 **СРОЧНОЕ ОБЪЯВЛЕНИЕ • 11 «Б»** 📢\n\n"
        f"{raw_text}\n\n"
        f"✍️ _Опубликовал(а): {author_name}_"
    )
    plain_text = (
        "📢 СРОЧНОЕ ОБЪЯВЛЕНИЕ • 11 «Б» 📢\n\n"
        f"{raw_text}\n\n"
        f"✍️ Опубликовал(а): {author_name}"
    )

    async def _send_to(chat_id: int, thread_id: int = None):
        kwargs = {"message_thread_id": thread_id} if thread_id else {}
        if attachment_type == "photo":
            try:
                await bot.send_photo(chat_id=chat_id, photo=file_id, caption=final_text, parse_mode="Markdown", **kwargs)
            except Exception:
                await bot.send_photo(chat_id=chat_id, photo=file_id, caption=plain_text, **kwargs)
        elif attachment_type == "document":
            try:
                await bot.send_document(chat_id=chat_id, document=file_id, caption=final_text, parse_mode="Markdown", **kwargs)
            except Exception:
                await bot.send_document(chat_id=chat_id, document=file_id, caption=plain_text, **kwargs)
        elif attachment_type == "video":
            try:
                await bot.send_video(chat_id=chat_id, video=file_id, caption=final_text, parse_mode="Markdown", **kwargs)
            except Exception:
                await bot.send_video(chat_id=chat_id, video=file_id, caption=plain_text, **kwargs)
        elif attachment_type == "audio":
            try:
                await bot.send_audio(chat_id=chat_id, audio=file_id, caption=final_text, parse_mode="Markdown", **kwargs)
            except Exception:
                await bot.send_audio(chat_id=chat_id, audio=file_id, caption=plain_text, **kwargs)
        else:
            try:
                await bot.send_message(chat_id=chat_id, text=final_text, parse_mode="Markdown", **kwargs)
            except Exception:
                await bot.send_message(chat_id=chat_id, text=plain_text, **kwargs)

    sent_users = 0
    sent_groups = 0

    if dest in ["users", "all"]:
        users = await get_notifiable_users(db_session)
        for u in users:
            try:
                await _send_to(u.tg_id)
                sent_users += 1
            except Exception as e:
                logger.warning(f"Failed to send broadcast to user {u.tg_id}: {e}")

    if dest in ["groups", "all"]:
        groups = await get_approved_group_chats(db_session)
        for g in groups:
            try:
                await _send_to(g.chat_id, thread_id=g.topic_announcements_id)
                sent_groups += 1
            except Exception as e:
                logger.warning(f"Failed to send broadcast to group {g.chat_id}: {e}")

    total_sent = sent_users + sent_groups
    dest_label = "всему классу (в ЛС)" if dest == "users" else ("в беседы" if dest == "groups" else "всему классу и в беседы")

    await state.clear()
    result_msg = (
        f"✅ **Объявление успешно разослано {dest_label}!**\n\n"
        f"📊 **Получателей:** {total_sent} (учеников: {sent_users}, бесед: {sent_groups})"
    )

    has_media = bool(callback.message.photo or callback.message.document or callback.message.video or callback.message.audio)
    if has_media:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(result_msg, reply_markup=get_admin_panel_keyboard(), parse_mode="Markdown")
    else:
        try:
            await callback.message.edit_text(result_msg, reply_markup=get_admin_panel_keyboard(), parse_mode="Markdown")
        except Exception:
            await callback.message.answer(result_msg, reply_markup=get_admin_panel_keyboard(), parse_mode="Markdown")
    try:
        await callback.answer("Объявление отправлено!", show_alert=True)
    except Exception:
        pass
