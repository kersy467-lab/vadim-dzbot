from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.crud import (
    toggle_user_canteen_reminder,
    toggle_user_currency_ecosystem,
    get_user_by_tg_id
)
from backend.db.models import User

router = Router(name="settings_router")


def build_settings_keyboard(canteen_on: bool, currency_on: bool) -> InlineKeyboardMarkup:
    canteen_icon = "✅ Вкл" if canteen_on else "⬜ Выкл"
    currency_icon = "✅ Вкл" if currency_on else "⬜ Выкл"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🍽 Столовая (после 5 урока): {canteen_icon}",
                    callback_data="set_canteen_toggle"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🪙 Игровая экосистема: {currency_icon}",
                    callback_data="set_currency_toggle"
                )
            ]
        ]
    )


def format_settings_text(canteen_on: bool, currency_on: bool, coins: int) -> str:
    canteen_status = "🟢 <b>Включено</b> (3 сообщения после 5 урока)" if canteen_on else "⚪ <b>Выключено</b>"
    currency_status = f"🟢 <b>Включена</b> (баланс: <code>{coins}</code> 🪙)" if currency_on else "⚪ <b>Выключена</b>"

    return (
        "⚙️ <b>Настройки профиля 11 «Б»</b>\n\n"
        f"🍽 <b>Напоминание о столовой:</b> {canteen_status}\n"
        "<i>После окончания 5-го урока вам в ЛС придут 3 напоминания, что пора идти обедать.</i>\n\n"
        f"🪙 <b>Внутриигровая экосистема:</b> {currency_status}\n"
        "<i>Разблокирует игры «Дурак», «21 Очко», «Рулетка» и «Кости», команды <code>/cash</code> и <code>/work</code>, ставки на монеты и рейтинг игроков в Mini App.</i>\n\n"
        "👇 <i>Нажмите на кнопку ниже, чтобы переключить режим:</i>"
    )


ECOSYSTEM_GUIDE_TEXT = (
    "🎉 <b>Игровая экосистема 11 «Б» активирована!</b>\n\n"
    "Вам стали доступны внутриклассная экономика, монеты и игры казино:\n\n"
    "🃏 <b>Игры на монеты в Mini App:</b>\n"
    "• Нажмите кнопку <b>«📱 Mini App 11 «Б»</b> внизу экрана → перейдите во вкладку <b>«Игры»</b>.\n"
    "• <b>«Дурак»:</b> классическая игра на 36 карт против бота или онлайн с одноклассниками.\n"
    "• <b>«21 Очко» (Блэкджек):</b> игра против дилера (Блэкджек 3:2, удвоение Double Down).\n"
    "• <b>«Рулетка»:</b> европейская рулетка (37 секторов, красное/чёрное 1:1, дюжины 2:1, число 35:1).\n"
    "• <b>«Кости»:</b> броски кубиков («Дуэль с дилером» и «Больше / Меньше / 7» с бонусами за дубли).\n"
    "• <b>Ставки:</b> быстрые суммы (10, 25, 50, 100, 250 🪙), ввод любой ставки или кнопка «🔥 Ва-банк».\n\n"
    "💰 <b>Команды бота:</b>\n"
    "• <code>/cash</code> (или <code>/balance</code>) — проверить текущий баланс монет.\n"
    "• <code>/work</code> — ежедневная подработка (+75 🪙 раз в сутки).\n\n"
    "🏆 <b>Рейтинг богачей:</b>\n"
    "• В меню Дурака нажмите «🏆 Рейтинг богачей», чтобы увидеть лидеров класса по балансу монет.\n\n"
    "<i>Удачи в играх! Экосистему всегда можно отключить здесь же в настройках.</i>"
)




@router.message(F.text == "⚙️ Настройки")
@router.message(Command("settings"))
async def show_settings(message: Message, current_user: User):
    canteen_on = bool(getattr(current_user, "canteen_reminder_enabled", False))
    currency_on = bool(getattr(current_user, "currency_ecosystem_enabled", False))
    coins = getattr(current_user, "coins", 100) or 0

    await message.answer(
        format_settings_text(canteen_on, currency_on, coins),
        reply_markup=build_settings_keyboard(canteen_on, currency_on),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "open_settings")
async def cb_open_settings(callback: CallbackQuery, current_user: User):
    canteen_on = bool(getattr(current_user, "canteen_reminder_enabled", False))
    currency_on = bool(getattr(current_user, "currency_ecosystem_enabled", False))
    coins = getattr(current_user, "coins", 100) or 0

    await callback.message.edit_text(
        format_settings_text(canteen_on, currency_on, coins),
        reply_markup=build_settings_keyboard(canteen_on, currency_on),
        parse_mode="HTML"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "set_canteen_toggle")
async def cb_toggle_canteen(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    new_val = await toggle_user_canteen_reminder(db_session, current_user.tg_id)
    # Refresh user
    user = await get_user_by_tg_id(db_session, current_user.tg_id) or current_user
    currency_on = bool(getattr(user, "currency_ecosystem_enabled", False))
    coins = getattr(user, "coins", 100) or 0

    await callback.message.edit_text(
        format_settings_text(new_val, currency_on, coins),
        reply_markup=build_settings_keyboard(new_val, currency_on),
        parse_mode="HTML"
    )
    status_msg = "✅ Напоминание о столовой включено!" if new_val else "⬜ Напоминание о столовой выключено"
    await callback.answer(status_msg)


@router.callback_query(F.data == "set_currency_toggle")
async def cb_toggle_currency(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    new_val = await toggle_user_currency_ecosystem(db_session, current_user.tg_id)
    # Refresh user
    user = await get_user_by_tg_id(db_session, current_user.tg_id) or current_user
    canteen_on = bool(getattr(user, "canteen_reminder_enabled", False))
    coins = getattr(user, "coins", 100) or 0

    await callback.message.edit_text(
        format_settings_text(canteen_on, new_val, coins),
        reply_markup=build_settings_keyboard(canteen_on, new_val),
        parse_mode="HTML"
    )
    status_msg = (
        "🪙 Игровая экосистема включена!"
        if new_val else
        "⬜ Игровая экосистема выключена"
    )
    await callback.answer(status_msg)

    if new_val:
        await callback.message.answer(ECOSYSTEM_GUIDE_TEXT, parse_mode="HTML")
