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

router = Router(name='admin_duty_broadcast_router')

# ==============================================================================
# ОБЪЯВЛЕНИЕ ДЕЖУРНЫМ
# ==============================================================================

@router.callback_query(F.data == "admin_duty_broadcast")
async def cb_admin_duty_broadcast_start(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    active_group, _ = await get_current_duty_info(db_session)
    if not active_group:
        try:
            await callback.answer("⚠️ Активная группа дежурных не найдена!", show_alert=True)
        except Exception:
            pass
        return

    await state.set_state(DutyBroadcastStates.entering_message)
    await state.update_data(
        duty_group_number=active_group.group_number,
        duty_group_name=active_group.name
    )

    members_str = active_group.members if active_group.members and active_group.members != "Состав не назначен" else "Состав не назначен"
    await callback.message.edit_text(
        f"📢 **Объявление дежурным ({active_group.name}):**\n\n"
        f"👥 **Состав:** {members_str}\n\n"
        "Отправьте текст сообщения для дежурных или прикрепите файл (фото, PDF, документ, видео, аудио) с описанием:",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(DutyBroadcastStates.entering_message)
async def msg_admin_duty_broadcast_text(message: Message, state: FSMContext, db_session: AsyncSession, current_user: User):
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
        await message.answer("⚠️ Пожалуйста, введите текст сообщения или прикрепите файл (фото, PDF, документ, видео, аудио):")
        return

    photo_id = file_id if attachment_type == "photo" else None
    await state.update_data(
        broadcast_text=text,
        photo_id=photo_id,
        attachment_type=attachment_type,
        attachment_file_id=file_id,
        attachment_file_name=file_name
    )
    await state.set_state(DutyBroadcastStates.confirm_destination)

    data = await state.get_data()
    g_name = data.get("duty_group_name", "дежурных")
    type_label = {
        "photo": "фото",
        "document": f"файл ({file_name})" if file_name else "документ",
        "video": "видео",
        "audio": "аудио"
    }.get(attachment_type, "файл")
    preview_text = text if text else f"*(без текста, только {type_label})*"

    active_group, _ = await get_current_duty_info(db_session)
    duty_users = await get_users_in_duty_group(db_session, active_group) if active_group else []
    found_count = len(duty_users)
    count_info = f"{found_count} чел." if found_count > 0 else "аккаунты не привязаны"

    prompt_text = (
        f"👀 **Предпросмотр объявления ({g_name}):**\n"
        "──────────────────────\n"
        f"{preview_text}\n"
        "──────────────────────\n\n"
        f"👥 Дежурных в боте: **{count_info}**\n\n"
        "Куда отправить объявление?"
    )

    if attachment_type == "photo":
        await message.answer_photo(
            photo=file_id,
            caption=prompt_text,
            reply_markup=get_duty_broadcast_destination_keyboard(),
            parse_mode="Markdown"
        )
    elif attachment_type == "document":
        await message.answer_document(
            document=file_id,
            caption=prompt_text,
            reply_markup=get_duty_broadcast_destination_keyboard(),
            parse_mode="Markdown"
        )
    elif attachment_type == "video":
        await message.answer_video(
            video=file_id,
            caption=prompt_text,
            reply_markup=get_duty_broadcast_destination_keyboard(),
            parse_mode="Markdown"
        )
    elif attachment_type == "audio":
        await message.answer_audio(
            audio=file_id,
            caption=prompt_text,
            reply_markup=get_duty_broadcast_destination_keyboard(),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            prompt_text,
            reply_markup=get_duty_broadcast_destination_keyboard(),
            parse_mode="Markdown"
        )


@router.callback_query(DutyBroadcastStates.confirm_destination, F.data.startswith("duty_bcast_dest_"))
async def cb_admin_duty_broadcast_send(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    dest = callback.data.replace("duty_bcast_dest_", "")
    data = await state.get_data()
    raw_text = data.get("broadcast_text", "")
    photo_id = data.get("photo_id")
    attachment_type = data.get("attachment_type") or ("photo" if photo_id else None)
    file_id = data.get("attachment_file_id") or photo_id

    active_group, _ = await get_current_duty_info(db_session)
    duty_users = await get_users_in_duty_group(db_session, active_group) if active_group else []

    group_name = active_group.name if active_group else "Дежурная группа"
    members_name = active_group.members if active_group and active_group.members else ""

    pm_text = (
        "🧹 **ОБЪЯВЛЕНИЕ ДЕЖУРНЫМ • 11 «Б»**\n\n"
        f"{raw_text}\n\n"
        f"📌 _Дежурит: {group_name}_"
    )
    pm_plain = (
        "🧹 ОБЪЯВЛЕНИЕ ДЕЖУРНЫМ • 11 «Б»\n\n"
        f"{raw_text}\n\n"
        f"📌 Дежурит: {group_name}"
    )

    mentions = []
    for u in duty_users:
        if u.username:
            mentions.append(f"@{u.username}")
        else:
            mentions.append(f"**{escape_md(u.display_name)}**")
    mention_prefix = ("🔔 " + ", ".join(mentions) + "\n\n") if mentions else ""

    group_text = (
        "🧹 **ОБЪЯВЛЕНИЕ ДЕЖУРНЫМ • 11 «Б»**\n\n"
        f"{mention_prefix}{raw_text}\n\n"
        f"📌 _Дежурная группа: {group_name}_"
    )
    if members_name:
        group_text += f"\n👥 _Состав: {members_name}_"

    group_plain = group_text.replace("**", "").replace("*", "").replace("`", "").replace("_", "")

    async def _send_media_or_msg(chat_id: int, thread_id: int, formatted_text: str, plain_content: str):
        kwargs = {"message_thread_id": thread_id} if thread_id else {}
        if attachment_type == "photo":
            try:
                await bot.send_photo(chat_id=chat_id, photo=file_id, caption=formatted_text, parse_mode="Markdown", **kwargs)
            except Exception:
                await bot.send_photo(chat_id=chat_id, photo=file_id, caption=plain_content, **kwargs)
        elif attachment_type == "document":
            try:
                await bot.send_document(chat_id=chat_id, document=file_id, caption=formatted_text, parse_mode="Markdown", **kwargs)
            except Exception:
                await bot.send_document(chat_id=chat_id, document=file_id, caption=plain_content, **kwargs)
        elif attachment_type == "video":
            try:
                await bot.send_video(chat_id=chat_id, video=file_id, caption=formatted_text, parse_mode="Markdown", **kwargs)
            except Exception:
                await bot.send_video(chat_id=chat_id, video=file_id, caption=plain_content, **kwargs)
        elif attachment_type == "audio":
            try:
                await bot.send_audio(chat_id=chat_id, audio=file_id, caption=formatted_text, parse_mode="Markdown", **kwargs)
            except Exception:
                await bot.send_audio(chat_id=chat_id, audio=file_id, caption=plain_content, **kwargs)
        else:
            try:
                await bot.send_message(chat_id=chat_id, text=formatted_text, parse_mode="Markdown", **kwargs)
            except Exception:
                await bot.send_message(chat_id=chat_id, text=plain_content, **kwargs)

    sent_pm = 0
    sent_groups = 0

    if dest in ["pm", "all"]:
        for u in duty_users:
            try:
                await _send_media_or_msg(u.tg_id, None, pm_text, pm_plain)
                sent_pm += 1
            except Exception as e:
                logger.warning(f"Could not send duty PM to {u.tg_id}: {e}")

    if dest in ["groups", "all"]:
        groups = await get_approved_group_chats(db_session)
        for g in groups:
            try:
                await _send_media_or_msg(g.chat_id, g.topic_duty_id, group_text, group_plain)
                sent_groups += 1
            except Exception as e:
                logger.warning(f"Could not send duty announcement to group {g.chat_id}: {e}")

    await state.clear()

    res_lines = ["✅ **Объявление дежурным успешно отправлено!**\n"]
    if dest in ["pm", "all"]:
        res_lines.append(f"📨 Доставлено в ЛС: **{sent_pm} дежурным**")
        if sent_pm == 0 and len(duty_users) == 0:
            res_lines.append("⚠️ _Ученики текущей группы пока не зарегистрированы в боте._")
    if dest in ["groups", "all"]:
        res_lines.append(f"👥 Отправлено в бесед: **{sent_groups}**")

    has_media = bool(callback.message.photo or callback.message.document or callback.message.video or callback.message.audio)
    if has_media:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            "\n".join(res_lines),
            reply_markup=get_admin_panel_keyboard(),
            parse_mode="Markdown"
        )
    else:
        try:
            await callback.message.edit_text(
                "\n".join(res_lines),
                reply_markup=get_admin_panel_keyboard(),
                parse_mode="Markdown"
            )
        except Exception:
            await callback.message.answer(
                "\n".join(res_lines),
                reply_markup=get_admin_panel_keyboard(),
                parse_mode="Markdown"
            )
    try:
        await callback.answer()
    except Exception:
        pass


