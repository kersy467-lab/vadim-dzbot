from datetime import date, timedelta
from typing import List
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, InputMediaDocument
)
from sqlalchemy.ext.asyncio import AsyncSession


from backend.db.models import Homework, User
from backend.db.crud import (
    get_homework_for_date, get_homework_by_subject,
    get_all_subjects, get_homework_by_id, get_subject_by_id,
    get_user_homework_status, toggle_homework_completion,
    get_all_upcoming_homeworks
)
from backend.bot.keyboards.inline import (
    get_homework_keyboard, get_subjects_keyboard, get_homework_item_keyboard
)
from backend.bot.services.notifier import format_copyable_desc

router = Router(name="homework_router")

def escape_md(text: str) -> str:
    r"""Экранирует спецсимволы Markdown v1: \, _, *, `, ["""
    if not text:
        return ""
    for ch in ["\\", "_", "*", "`", "["]:
        text = text.replace(ch, f"\\{ch}")
    return text


async def send_homework_card(
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    user: User,
    hw: Homework
):
    status = await get_user_homework_status(session, user.id, hw.id)
    is_done = status.is_completed if status else False

    status_icon = "✅" if is_done else "📌"
    date_str = hw.due_date.strftime("%d.%m.%Y")
    title_str = f" — *{escape_md(hw.title)}*" if hw.title else ""
    title_plain = f" — {hw.title}" if hw.title else ""
    
    desc_formatted = format_copyable_desc(hw.description)
    caption = (
        f"{status_icon} **{hw.subject.name}**{title_str}\n"
        f"📅 **Сдать до:** `{date_str}`\n\n"
        f"{desc_formatted}"
    )
    caption_plain = (
        f"{status_icon} {hw.subject.name}{title_plain}\n"
        f"📅 Сдать до: {date_str}\n\n"
        f"{hw.description}"
    )

    kb = get_homework_item_keyboard(hw.id, is_done)

    photos = [a for a in (hw.attachments or []) if a.get("type") == "photo" and a.get("file_id")]
    docs = [a for a in (hw.attachments or []) if a.get("type") == "document" and a.get("file_id")]

    if photos:
        if len(photos) == 1 and not docs:
            # Ровно одно фото с текстом и кнопкой в одном сообщении
            try:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photos[0]["file_id"],
                    caption=caption,
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
            except Exception:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photos[0]["file_id"],
                    caption=caption_plain,
                    reply_markup=kb,
                    parse_mode=None
                )
            return
        else:
            # Все фото отправляются единым альбомом (media_group)
            media_group = [
                InputMediaPhoto(
                    media=p["file_id"],
                    caption=caption if i == 0 else None,
                    parse_mode="Markdown" if i == 0 else None
                )
                for i, p in enumerate(photos)
            ]
            try:
                await bot.send_media_group(chat_id=chat_id, media=media_group)
            except Exception:
                media_group_plain = [
                    InputMediaPhoto(
                        media=p["file_id"],
                        caption=caption_plain if i == 0 else None,
                        parse_mode=None
                    )
                    for i, p in enumerate(photos)
                ]
                await bot.send_media_group(chat_id=chat_id, media=media_group_plain)

            # Если есть документы — группируем их
            if docs:
                if len(docs) == 1:
                    try:
                        await bot.send_document(
                            chat_id=chat_id,
                            document=docs[0]["file_id"],
                            caption=f"📎 Документ: **{escape_md(docs[0].get('file_name', 'файл'))}**",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        await bot.send_document(
                            chat_id=chat_id,
                            document=docs[0]["file_id"],
                            caption=f"📎 Документ: {docs[0].get('file_name', 'файл')}",
                            parse_mode=None
                        )
                else:
                    doc_group = [InputMediaDocument(media=d["file_id"]) for d in docs]
                    await bot.send_media_group(chat_id=chat_id, media=doc_group)

            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"📋 Статус выполнения задания: **{hw.subject.name}**",
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
            except Exception:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"📋 Статус выполнения задания: {hw.subject.name}",
                    reply_markup=kb,
                    parse_mode=None
                )
            return

    elif docs:
        if len(docs) == 1:
            # Ровно один документ с текстом и кнопкой в одном сообщении
            try:
                await bot.send_document(
                    chat_id=chat_id,
                    document=docs[0]["file_id"],
                    caption=caption,
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
            except Exception:
                await bot.send_document(
                    chat_id=chat_id,
                    document=docs[0]["file_id"],
                    caption=caption_plain,
                    reply_markup=kb,
                    parse_mode=None
                )
            return
        else:
            # Все документы единым альбомом
            doc_group = [
                InputMediaDocument(
                    media=d["file_id"],
                    caption=caption if i == 0 else None,
                    parse_mode="Markdown" if i == 0 else None
                )
                for i, d in enumerate(docs)
            ]
            try:
                await bot.send_media_group(chat_id=chat_id, media=doc_group)
            except Exception:
                doc_group_plain = [
                    InputMediaDocument(
                        media=d["file_id"],
                        caption=caption_plain if i == 0 else None,
                        parse_mode=None
                    )
                    for i, d in enumerate(docs)
                ]
                await bot.send_media_group(chat_id=chat_id, media=doc_group_plain)

            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"📋 Статус выполнения задания: **{hw.subject.name}**",
                    reply_markup=kb,
                    parse_mode="Markdown"
                )
            except Exception:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"📋 Статус выполнения задания: {hw.subject.name}",
                    reply_markup=kb,
                    parse_mode=None
                )
            return

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=kb,
            parse_mode="Markdown"
        )
    except Exception:
        await bot.send_message(
            chat_id=chat_id,
            text=caption_plain,
            reply_markup=kb,
            parse_mode=None
        )


@router.message(F.text == "📚 Домашка")
async def show_homework_menu(message: Message):

    await message.answer(
        "📚 **Раздел Домашнего Задания:**\n\n"
        "Выберите, какое ДЗ вы хотите посмотреть:",
        reply_markup=get_homework_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "hw_tomorrow")
async def cb_hw_tomorrow(callback: CallbackQuery, db_session: AsyncSession, current_user: User, bot: Bot):
    tomorrow = date.today() + timedelta(days=1)
    homeworks = await get_homework_for_date(db_session, tomorrow)

    if not homeworks:
        await callback.message.edit_text(
            f"🎉 **На завтра ({tomorrow.strftime('%d.%m.%Y')}) заданий нет!**",
            reply_markup=get_homework_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"📚 **Домашнее задание на завтра ({tomorrow.strftime('%d.%m.%Y')}):**\n"
        f"Найдено заданий: {len(homeworks)}",
        parse_mode="Markdown"
    )

    for hw in homeworks:
        await send_homework_card(bot, callback.message.chat.id, db_session, current_user, hw)
    
    await callback.answer()

from backend.bot.keyboards.calendar import get_inline_calendar

@router.callback_query(F.data == "hw_pick_date")
async def cb_hw_pick_date(callback: CallbackQuery):
    today = date.today()
    kb = get_inline_calendar("hw", year=today.year, month=today.month, back_callback="hw_menu")
    await callback.message.edit_text(
        "🗓 **Выберите дату на календаре для просмотра заданий:**",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cal_nav_hw_"))
async def cb_cal_nav_hw(callback: CallbackQuery):
    parts = callback.data.split("_")
    year = int(parts[3])
    month = int(parts[4])
    kb = get_inline_calendar("hw", year=year, month=month, back_callback="hw_menu")
    await callback.message.edit_text(
        "🗓 **Выберите дату на календаре для просмотра заданий:**",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("cal_act_hw_"))
async def cb_cal_act_hw(callback: CallbackQuery, db_session: AsyncSession, current_user: User, bot: Bot):
    parts = callback.data.split("_")
    year = int(parts[3])
    month = int(parts[4])
    day = int(parts[5])
    target_date = date(year, month, day)

    homeworks = await get_homework_for_date(db_session, target_date)

    if not homeworks:
        await callback.message.edit_text(
            f"🎉 **На дату {target_date.strftime('%d.%m.%Y')} заданий не было / нет!**",
            reply_markup=get_homework_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    from backend.config import get_today
    today = get_today()
    past_note = " _(срок сдачи прошел)_" if target_date < today else ""

    await callback.message.edit_text(
        f"📚 **Домашнее задание на {target_date.strftime('%d.%m.%Y')}{past_note}:**\n"
        f"Найдено заданий: {len(homeworks)}",
        parse_mode="Markdown"
    )

    for hw in homeworks:
        await send_homework_card(bot, callback.message.chat.id, db_session, current_user, hw)

    await callback.answer()

@router.callback_query(F.data.startswith("hw_date_"))
async def cb_hw_for_specific_date(callback: CallbackQuery, db_session: AsyncSession, current_user: User, bot: Bot):
    date_str = callback.data.replace("hw_date_", "")
    target_date = date.fromisoformat(date_str)

    homeworks = await get_homework_for_date(db_session, target_date)

    if not homeworks:
        await callback.message.edit_text(
            f"🎉 **На дату {target_date.strftime('%d.%m.%Y')} заданий не было / нет!**",
            reply_markup=get_homework_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    from backend.config import get_today
    today = get_today()
    past_note = " _(срок сдачи прошел)_" if target_date < today else ""

    await callback.message.edit_text(
        f"📚 **Домашнее задание на {target_date.strftime('%d.%m.%Y')}{past_note}:**\n"
        f"Найдено заданий: {len(homeworks)}",
        parse_mode="Markdown"
    )

    for hw in homeworks:
        await send_homework_card(bot, callback.message.chat.id, db_session, current_user, hw)

    await callback.answer()


@router.callback_query(F.data == "hw_by_subject")
async def cb_hw_by_subject(callback: CallbackQuery, db_session: AsyncSession):
    subjects = await get_all_subjects(db_session)
    if not subjects:
        await callback.answer("Список предметов пуст", show_alert=True)
        return

    await callback.message.edit_text(
        "📖 **Выберите предмет:**",
        reply_markup=get_subjects_keyboard(subjects, prefix="hw_view_subj_"),
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("hw_view_subj_") | F.data.startswith("hw_subj_"))
async def cb_hw_view_subject(callback: CallbackQuery, db_session: AsyncSession, current_user: User, bot: Bot):
    raw_id = callback.data.replace("hw_view_subj_", "").replace("hw_subj_", "")
    subj_id = int(raw_id)

    from backend.config import get_today
    today = get_today()

    subj = await get_subject_by_id(db_session, subj_id)
    subj_name = subj.name if subj else "Предмет"

    homeworks = await get_homework_by_subject(db_session, subj_id, limit=20, from_date=today)
    # Строгая фильтрация в Python (начиная с сегодняшнего дня и далее)
    homeworks = [h for h in homeworks if h.due_date >= today]
    homeworks.sort(key=lambda h: h.due_date)

    if not homeworks:
        await callback.message.edit_text(
            f"ℹ️ По предмету **{subj_name}** нет активных заданий (начиная с сегодня, {today.strftime('%d.%m.%Y')}).",
            reply_markup=get_homework_keyboard(),
            parse_mode="Markdown"
        )
        try:
            await callback.answer()
        except Exception:
            pass
        return

    await callback.message.edit_text(
        f"📖 **Актуальные задания по предмету {subj_name}:**\n_(начиная с сегодня, {today.strftime('%d.%m.%Y')})_",
        parse_mode="Markdown"
    )

    for hw in homeworks:
        await send_homework_card(bot, callback.message.chat.id, db_session, current_user, hw)

    try:
        await callback.answer()
    except Exception:
        pass

@router.callback_query(F.data == "hw_my_tasks")
async def cb_hw_my_tasks(callback: CallbackQuery, db_session: AsyncSession, current_user: User, bot: Bot):
    # Fetch upcoming homework: today + all future
    from backend.config import get_today
    today = get_today()
    all_hw = await get_all_upcoming_homeworks(db_session, today)

    # Filter uncompleted
    uncompleted = []
    for hw in all_hw:
        status = await get_user_homework_status(db_session, current_user.id, hw.id)
        if not status or not status.is_completed:
            uncompleted.append(hw)

    if not uncompleted:
        await callback.message.edit_text(
            "🎉 **Отлично! У вас нет невыполненных заданий!**",
            reply_markup=get_homework_keyboard(),
            parse_mode="Markdown"
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"📝 **Ваши невыполненные задания ({len(uncompleted)}):**",
        parse_mode="Markdown"
    )

    for hw in uncompleted:
        await send_homework_card(bot, callback.message.chat.id, db_session, current_user, hw)

    await callback.answer()

@router.callback_query(F.data.startswith("hw_toggle_"))
async def cb_hw_toggle(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    hw_id = int(callback.data.replace("hw_toggle_", ""))
    hw = await get_homework_by_id(db_session, hw_id)
    if not hw:
        await callback.answer("Задание не найдено", show_alert=True)
        return

    new_status = await toggle_homework_completion(db_session, current_user.id, hw_id)
    new_kb = get_homework_item_keyboard(hw_id, new_status)

    try:
        await callback.message.edit_reply_markup(reply_markup=new_kb)
    except Exception:
        pass

    if new_status:
        await callback.answer("✅ Отмечено как выполненное!", show_alert=False)
    else:
        await callback.answer("⬜ Отметка о выполнении снята", show_alert=False)

@router.callback_query(F.data == "hw_menu")
@router.callback_query(F.data == "main_menu")
async def cb_hw_menu(callback: CallbackQuery):

    await callback.message.edit_text(
        "📚 **Раздел Домашнего Задания:**\n\n"
        "Выберите, какое ДЗ вы хотите посмотреть:",
        reply_markup=get_homework_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()
