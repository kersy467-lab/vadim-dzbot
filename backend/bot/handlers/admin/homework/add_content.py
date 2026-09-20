import time
import asyncio
from datetime import date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.crud import get_subject_by_id, create_homework
from backend.bot.keyboards.admin_kb import get_admin_panel_keyboard, get_cancel_keyboard, get_hw_notify_keyboard
from backend.bot.keyboards.calendar import get_inline_calendar
from backend.bot.handlers.schedule import DAYS_RU
from backend.bot.handlers.admin.states import AddHomeworkStates
from backend.bot.handlers.admin.homework.helpers import escape_md, safe_answer, safe_edit_text

router = Router(name="admin_homework_add_content_router")


@router.message(AddHomeworkStates.entering_content)
async def msg_add_hw_collect_content(message: Message, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    attachments = list(data.get("attachments", []))
    description = data.get("description", "")

    if message.photo:
        photo = message.photo[-1]
        attachments.append({"type": "photo", "file_id": photo.file_id})
        if message.caption and not description:
            description = message.caption.strip()
    elif message.document:
        attachments.append({
            "type": "document",
            "file_id": message.document.file_id,
            "file_name": message.document.file_name or "документ"
        })
        if message.caption and not description:
            description = message.caption.strip()
    elif message.video:
        attachments.append({
            "type": "document",
            "file_id": message.video.file_id,
            "file_name": message.video.file_name or "видео.mp4"
        })
        if message.caption and not description:
            description = message.caption.strip()
    elif message.audio:
        attachments.append({
            "type": "document",
            "file_id": message.audio.file_id,
            "file_name": message.audio.file_name or "аудио.mp3"
        })
        if message.caption and not description:
            description = message.caption.strip()
    elif message.text:
        description = message.text.strip()

    await state.update_data(attachments=attachments, description=description)

    # Дебаунс для медиа-групп (альбомов)
    if message.media_group_id:
        req_token = f"{message.media_group_id}_{time.time()}"
        await state.update_data(last_mg_req=req_token)
        await asyncio.sleep(0.4)
        latest_data = await state.get_data()
        if latest_data.get("last_mg_req") != req_token:
            return
        attachments = list(latest_data.get("attachments", []))
        description = latest_data.get("description", "")

    num_att = len(attachments)
    photos_cnt = len([a for a in attachments if a.get("type") == "photo"])
    docs_cnt = len([a for a in attachments if a.get("type") == "document"])

    if num_att > 0:
        details = []
        if photos_cnt > 0:
            details.append(f"📷 {photos_cnt} фото")
        if docs_cnt > 0:
            details.append(f"📄 {docs_cnt} файл(ов)")
        att_str = f"📎 **Прикреплено файлов:** {num_att} ({', '.join(details)})"
        save_btn_label = f"💾 Сохранить ДЗ ({num_att} влож.)"
    else:
        att_str = "📎 Вложений нет (можно отправить фото/документы/файлы)"
        save_btn_label = "💾 Сохранить ДЗ"

    desc_escaped = escape_md(description)
    desc_line = f"📝 **Текст задания:** {desc_escaped}" if description else "📝 **Текст:** _(не указан, можно отправить сейчас)_"

    due_d_str = data.get("due_date")
    from backend.config import get_today
    today = get_today()

    if not due_d_str:
        await state.set_state(AddHomeworkStates.entering_date)
        kb = get_inline_calendar("adm_hw", year=today.year, month=today.month, back_callback="admin_cancel")
        await safe_answer(
            message,
            "⚠️ **Дата сдачи ещё не выбрана!**\n\n"
            "Этого предмета нет в расписании уроков. Пожалуйста, выберите дату сдачи на календаре:",
            reply_markup=kb
        )
        return

    due_d = date.fromisoformat(due_d_str)
    day_ru = DAYS_RU.get(due_d.isoweekday(), "")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=save_btn_label, callback_data="adm_hw_save_now")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
        ]
    )

    last_msg_id = data.get("hw_prompt_msg_id")
    if last_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_msg_id)
        except Exception:
            pass

    text_msg = (
        f"📥 **Материалы получены!**\n\n"
        f"📅 **Дата сдачи:** {day_ru}, {due_d.strftime('%d.%m.%Y')}\n"
        f"{att_str}\n"
        f"{desc_line}\n\n"
        "⬇️ **Отправьте ещё фото/файлы или текст**, либо нажмите кнопку сохранения:"
    )

    sent = await safe_answer(message, text_msg, reply_markup=kb)
    if sent:
        await state.update_data(hw_prompt_msg_id=sent.message_id)


@router.callback_query(F.data == "adm_hw_save_now")
async def cb_add_hw_save_now(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    data = await state.get_data()
    from backend.config import get_today
    today = get_today()

    due_d_str = data.get("due_date")
    if not due_d_str:
        await callback.answer("⚠️ Сначала выберите дату сдачи ДЗ!", show_alert=True)
        return
    due_d = date.fromisoformat(due_d_str)

    assigned_d_str = data.get("assigned_date") or today.isoformat()
    assigned_d = date.fromisoformat(assigned_d_str)

    subj_id = data.get("subject_id")
    if not subj_id:
        await safe_edit_text(callback.message, "⚠️ Ошибка: предмет не выбран. Начните добавление ДЗ заново.", reply_markup=get_admin_panel_keyboard())
        await state.clear()
        return

    attachments = list(data.get("attachments", []))
    description = (data.get("description") or "").strip()

    if not description:
        if attachments:
            description = "Домашнее задание (см. прикрепленные материалы)"
        else:
            description = "Домашнее задание"

    hw = await create_homework(
        session=db_session,
        subject_id=subj_id,
        due_date=due_d,
        assigned_date=assigned_d,
        description=description,
        attachments=attachments,
        created_by=callback.from_user.id
    )

    subj = await get_subject_by_id(db_session, subj_id)
    subj_name = subj.name if subj else "Предмет"
    day_ru = DAYS_RU.get(due_d.isoweekday(), "")

    att_info = ""
    if attachments:
        photos = len([a for a in attachments if a.get("type") == "photo"])
        docs = len([a for a in attachments if a.get("type") == "document"])
        details = []
        if photos: details.append(f"{photos} фото")
        if docs: details.append(f"{docs} файл(ов)")
        att_info = f"📎 **Вложения ({len(attachments)}):** {', '.join(details)}\n"

    desc_escaped = escape_md(hw.description)
    await state.clear()
    await safe_edit_text(
        callback.message,
        f"✅ **Домашнее задание успешно сохранено!**\n\n"
        f"📖 **Предмет:** {subj_name}\n"
        f"📅 **Дата сдачи:** {day_ru}, {due_d.strftime('%d.%m.%Y')}\n"
        f"{att_info}"
        f"📝 **Задание:** {desc_escaped}\n\n"
        "📢 **Отправить оповещение ученикам о новом задании?**\n"
        "Выберите, куда сделать рассылку:",
        reply_markup=get_hw_notify_keyboard(hw.id)
    )
    try:
        await callback.answer("ДЗ успешно сохранено!")
    except Exception:
        pass
