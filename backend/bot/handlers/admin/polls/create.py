import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud.polls import (
    create_poll,
    get_poll_results_data,
    format_poll_message_text,
    add_dispatched_message
)
from backend.db.crud.users import get_approved_group_chats
from backend.bot.keyboards.admin_kb import get_cancel_keyboard
from backend.bot.handlers.polls import get_poll_voting_keyboard
from backend.bot.handlers.admin.helpers import is_admin
from backend.bot.handlers.admin.polls.states import PollWizardStates

logger = logging.getLogger(__name__)

router = Router(name="admin_polls_create_router")


def get_poll_settings_keyboard(is_anon: bool, allow_revote: bool) -> InlineKeyboardMarkup:
    anon_icon = "✅ Да" if is_anon else "⬜ Нет"
    revote_icon = "✅ Да" if allow_revote else "⬜ Нет"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"🔒 Анонимный: {anon_icon}", callback_data="adm_poll_tog_anon"),
            ],
            [
                InlineKeyboardButton(text=f"🔄 Разрешить переголосование: {revote_icon}", callback_data="adm_poll_tog_revote"),
            ],
            [
                InlineKeyboardButton(text="🚀 Опубликовать в «Важные объявления»", callback_data="adm_poll_publish")
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_polls_menu")
            ]
        ]
    )


@router.callback_query(F.data == "admin_polls_create")
async def cb_admin_polls_create_start(callback: CallbackQuery, state: FSMContext, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    await state.clear()
    await state.set_state(PollWizardStates.entering_question)
    await state.update_data(is_anonymous=False, allow_revote=True)

    await callback.message.edit_text(
        "📊 **Создание нового опроса класса**\n\n"
        "**Шаг 1 из 3:** Введите текст вопроса для опроса.\n"
        "_(например: «Переносим репетицию вальса на 16:00?»)_",
        reply_markup=get_cancel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(PollWizardStates.entering_question)
async def msg_admin_poll_question(message: Message, state: FSMContext):
    question = (message.text or "").strip()
    if not question or len(question) < 3:
        await message.answer("⚠️ Введите осмысленный вопрос (не менее 3 символов):", reply_markup=get_cancel_keyboard())
        return

    await state.update_data(question=question)
    await state.set_state(PollWizardStates.entering_options)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚡ Быстрый шаблон: Да / Нет", callback_data="adm_poll_tpl_yesno")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_polls_menu")]
        ]
    )

    await message.answer(
        f"❓ Вопрос: **«{question}»**\n\n"
        "**Шаг 2 из 3:** Введите варианты ответов.\n"
        "Отправьте их одним сообщением (каждый с новой строки или через точку с запятой `;`):\n"
        "```\nДа, в 16:00\nНет, лучше в 17:00\nНе смогу прийти\n```\n"
        "Или нажмите кнопку шаблона **«Да / Нет»** ниже:",
        reply_markup=kb,
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "adm_poll_tpl_yesno", PollWizardStates.entering_options)
async def cb_admin_poll_tpl_yesno(callback: CallbackQuery, state: FSMContext):
    await state.update_data(options=["Да", "Нет"])
    await show_poll_preview(callback.message, state, is_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(PollWizardStates.entering_options)
async def msg_admin_poll_options(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    raw_opts = [opt.strip() for opt in text.split("\n") if opt.strip()]
    if len(raw_opts) == 1 and ";" in text:
        raw_opts = [opt.strip() for opt in text.split(";") if opt.strip()]

    # Убираем ведущие цифры/дефисы, если пользователь пронумеровал варианты вручную
    import re
    cleaned = []
    for r in raw_opts:
        c = re.sub(r"^(\d+[\.\)\-]\s*|[\-\*\•]\s*)", "", r).strip()
        if c:
            cleaned.append(c)

    if len(cleaned) < 2:
        await message.answer("⚠️ Введите как минимум 2 варианта ответа:", reply_markup=get_cancel_keyboard())
        return
    if len(cleaned) > 10:
        await message.answer("⚠️ Максимум 10 вариантов ответа. Попробуйте еще раз:", reply_markup=get_cancel_keyboard())
        return

    await state.update_data(options=cleaned)
    await show_poll_preview(message, state, is_edit=False)


async def show_poll_preview(msg_or_cb_msg, state: FSMContext, is_edit: bool = False):
    await state.set_state(PollWizardStates.configuring_settings)
    data = await state.get_data()
    q = data.get("question", "")
    opts = data.get("options", [])
    is_anon = data.get("is_anonymous", False)
    allow_revote = data.get("allow_revote", True)

    lines = [
        "📊 **Предпросмотр опроса**\n",
        f"**Вопрос:** {q}\n",
        "**Варианты ответов:**"
    ]
    for idx, opt in enumerate(opts, 1):
        lines.append(f"  {idx}. {opt}")

    lines.append("\n**Шаг 3 из 3:** Настройте параметры опроса и нажмите **«Опубликовать»**:")
    kb = get_poll_settings_keyboard(is_anon, allow_revote)

    if is_edit:
        await msg_or_cb_msg.edit_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")
    else:
        await msg_or_cb_msg.answer("\n".join(lines), reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data == "adm_poll_tog_anon", PollWizardStates.configuring_settings)
async def cb_admin_poll_toggle_anon(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    new_anon = not data.get("is_anonymous", False)
    await state.update_data(is_anonymous=new_anon)
    await show_poll_preview(callback.message, state, is_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "adm_poll_tog_revote", PollWizardStates.configuring_settings)
async def cb_admin_poll_toggle_revote(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    new_revote = not data.get("allow_revote", True)
    await state.update_data(allow_revote=new_revote)
    await show_poll_preview(callback.message, state, is_edit=True)
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "adm_poll_publish", PollWizardStates.configuring_settings)
async def cb_admin_poll_publish(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    data = await state.get_data()
    question = data.get("question")
    options = data.get("options", [])
    is_anon = data.get("is_anonymous", False)
    allow_revote = data.get("allow_revote", True)

    if not question or not options:
        await callback.answer("Ошибка данных опроса.", show_alert=True)
        return

    poll = await create_poll(
        session=db_session,
        question=question,
        options_texts=options,
        creator_tg_id=callback.from_user.id,
        is_anonymous=is_anon,
        allow_revote=allow_revote
    )

    # Публикуем строго в топик «Важные объявления» групп класса
    groups = await get_approved_group_chats(db_session)
    results = await get_poll_results_data(db_session, poll.id)
    msg_text = format_poll_message_text(results)
    voting_kb = get_poll_voting_keyboard(poll)

    sent_count = 0
    for g in groups:
        target_thread = g.topic_announcements_id
        kwargs = {"message_thread_id": target_thread} if target_thread else {}
        try:
            sent_msg = await callback.bot.send_message(
                chat_id=g.chat_id,
                text=msg_text,
                reply_markup=voting_kb,
                parse_mode="Markdown",
                **kwargs
            )
            await add_dispatched_message(db_session, poll.id, g.chat_id, sent_msg.message_id)
            sent_count += 1
        except Exception as e:
            logger.warning(f"Could not send poll to group {g.chat_id}: {e}")
            if target_thread:
                try:
                    sent_msg2 = await callback.bot.send_message(
                        chat_id=g.chat_id,
                        text=msg_text,
                        reply_markup=voting_kb,
                        parse_mode="Markdown"
                    )
                    await add_dispatched_message(db_session, poll.id, g.chat_id, sent_msg2.message_id)
                    sent_count += 1
                except Exception as ex2:
                    logger.error(f"Fallback poll dispatch failed: {ex2}")

    await state.clear()

    kb_done = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Управление опросами", callback_data="admin_polls_menu")],
            [InlineKeyboardButton(text="🔙 В панель управления", callback_data="admin_menu_back")]
        ]
    )

    await callback.message.edit_text(
        f"✅ **Опрос успешно создан и опубликован!**\n\n"
        f"📢 Отправлен в «Важные объявления» ({sent_count} групп(ы)).\n"
        "Ученики могут голосовать прямо сейчас через инлайн-кнопки в беседе.\n"
        "Следить за результатами и напоминать не проголосовавшим можно в разделе «Опросы класса».",
        reply_markup=kb_done,
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Опрос опубликован!")
    except Exception:
        pass
