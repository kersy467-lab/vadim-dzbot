import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User, ClassPoll
from backend.db.crud.polls import (
    get_poll_by_id,
    record_or_update_vote,
    get_poll_results_data,
    format_poll_message_text,
)

logger = logging.getLogger(__name__)

router = Router(name="public_polls_router")


def get_poll_voting_keyboard(poll: ClassPoll) -> InlineKeyboardMarkup:
    """Генерирует инлайн-кнопки вариантов ответа для учеников (без лишних админских кнопок)."""
    buttons = []
    for opt in sorted(poll.options, key=lambda x: x.order_index):
        buttons.append([
            InlineKeyboardButton(
                text=f"{opt.order_index}. {opt.option_text}",
                callback_data=f"poll_vote_{poll.id}_{opt.id}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data.startswith("poll_vote_"))
async def cb_poll_vote(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    """Обрабатывает нажатие на вариант ответа в опросе."""
    if not current_user or current_user.role not in ("student", "admin"):
        await callback.answer("⚠️ Голосовать могут только авторизованные ученики класса!", show_alert=True)
        return

    parts = callback.data.split("_")
    if len(parts) != 4:
        await callback.answer()
        return

    try:
        poll_id = int(parts[2])
        option_id = int(parts[3])
    except ValueError:
        await callback.answer()
        return

    success, status, poll = await record_or_update_vote(
        session=db_session,
        poll_id=poll_id,
        option_id=option_id,
        user_tg_id=callback.from_user.id
    )

    if status == "not_found":
        await callback.answer("⚠️ Опрос не найден или удален.", show_alert=True)
        return

    if status == "closed":
        await callback.answer("🏁 Этот опрос уже завершён администратором!", show_alert=True)
        return

    if status == "no_revote":
        await callback.answer("❌ В этом опросе запрещено изменять свой выбор!", show_alert=True)
        return

    if status == "already_voted_same":
        await callback.answer("ℹ️ Вы уже проголосовали за этот вариант!")
        return

    # Голос успешно учтён или изменён
    opt_name = ""
    for opt in poll.options:
        if opt.id == option_id:
            opt_name = opt.option_text
            break

    toast_text = f"🔄 Голос изменён на: {opt_name}" if status == "revoted" else f"✅ Голос учтён: {opt_name}"
    await callback.answer(toast_text)

    # Динамически обновляем результаты в сообщении
    results = await get_poll_results_data(db_session, poll.id)
    if results and callback.message:
        new_text = format_poll_message_text(results)
        kb = get_poll_voting_keyboard(poll)
        try:
            await callback.message.edit_text(
                new_text,
                reply_markup=kb,
                parse_mode="Markdown"
            )
        except Exception as e:
            # Игнорируем ошибку, если текст не изменился (например, при параллельных кликах)
            if "message is not modified" not in str(e).lower():
                logger.warning(f"Failed to edit poll message {poll.id}: {e}")
