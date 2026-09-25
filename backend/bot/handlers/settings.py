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


from backend.bot.handlers.admin.helpers import is_admin
from backend.natbirzha.services.maintenance_service import MaintenanceService


def build_settings_keyboard(
    canteen_on: bool,
    currency_on: bool,
    is_admin_user: bool = False,
    maint_on: bool = False,
) -> InlineKeyboardMarkup:
    canteen_icon = "✅ Вкл" if canteen_on else "⬜ Выкл"
    currency_icon = "✅ Вкл" if currency_on else "⬜ Выкл"

    buttons = [
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
        ],
    ]

    if is_admin_user:
        maint_icon = "🔴 ВКЛ" if maint_on else "⬜ Выкл"
        buttons.append([
            InlineKeyboardButton(
                text=f"🛠 Техперерыв (НАТБИРЖА): {maint_icon}",
                callback_data="set_natbirzha_maint_toggle"
            )
        ])

    buttons.extend([
        [
            InlineKeyboardButton(
                text="📅 Добавить своё расписание",
                callback_data="custom_sched_add"
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Моё расписание",
                callback_data="custom_sched_view"
            )
        ]
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_settings_text(
    canteen_on: bool,
    currency_on: bool,
    coins: int,
    is_admin_user: bool = False,
    maint_on: bool = False,
) -> str:
    canteen_status = "🟢 <b>Включено</b> (3 сообщения после 5 урока)" if canteen_on else "⚪ <b>Выключено</b>"
    currency_status = f"🟢 <b>Включена</b> (баланс: <code>{coins}</code> 🪙)" if currency_on else "⚪ <b>Выключена</b>"

    admin_part = ""
    if is_admin_user:
        maint_status = "🔴 <b>Включен</b> (плашка активна для игроков)" if maint_on else "⚪ <b>Выключен</b>"
        admin_part = (
            f"🛠 <b>Техперерыв (НАТБИРЖА):</b> {maint_status}\n"
            "<i>Отображает плашку «Технический перерыв» в игре для всех игроков, кроме админов.</i>\n\n"
        )

    return (
        "⚙️ <b>Настройки профиля 11 «Б»</b>\n\n"
        f"🍽 <b>Напоминание о столовой:</b> {canteen_status}\n"
        "<i>После окончания 5-го урока вам в ЛС придут 3 напоминания, что пора идти обедать.</i>\n\n"
        f"🪙 <b>Внутриигровая экосистема:</b> {currency_status}\n"
        "<i>Разблокирует игры «Дурак», «21 Очко», «Рулетка» и «Кости», команды <code>/cash</code> и <code>/work</code>, ставки на монеты и рейтинг игроков в Mini App.</i>\n\n"
        + admin_part +
        "📅 <b>Персональное расписание:</b>\n"
        "<i>Настройте автоматическую отправку личного расписания по дням недели в выбранное вами время.</i>\n\n"
        "👇 <i>Выберите действие ниже:</i>"
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
async def show_settings(message: Message, current_user: User, db_session: AsyncSession):
    canteen_on = bool(getattr(current_user, "canteen_reminder_enabled", False))
    currency_on = bool(getattr(current_user, "currency_ecosystem_enabled", False))
    coins = getattr(current_user, "coins", 100) or 0
    admin = is_admin(current_user, message.from_user.id)
    maint_on = await MaintenanceService.is_maintenance_active(db_session) if admin else False

    await message.answer(
        format_settings_text(canteen_on, currency_on, coins, admin, maint_on),
        reply_markup=build_settings_keyboard(canteen_on, currency_on, admin, maint_on),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "open_settings")
async def cb_open_settings(callback: CallbackQuery, current_user: User, db_session: AsyncSession):
    canteen_on = bool(getattr(current_user, "canteen_reminder_enabled", False))
    currency_on = bool(getattr(current_user, "currency_ecosystem_enabled", False))
    coins = getattr(current_user, "coins", 100) or 0
    admin = is_admin(current_user, callback.from_user.id)
    maint_on = await MaintenanceService.is_maintenance_active(db_session) if admin else False

    await callback.message.edit_text(
        format_settings_text(canteen_on, currency_on, coins, admin, maint_on),
        reply_markup=build_settings_keyboard(canteen_on, currency_on, admin, maint_on),
        parse_mode="HTML"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "set_canteen_toggle")
async def cb_toggle_canteen(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    new_val = await toggle_user_canteen_reminder(db_session, current_user.tg_id)
    user = await get_user_by_tg_id(db_session, current_user.tg_id) or current_user
    currency_on = bool(getattr(user, "currency_ecosystem_enabled", False))
    coins = getattr(user, "coins", 100) or 0
    admin = is_admin(user, callback.from_user.id)
    maint_on = await MaintenanceService.is_maintenance_active(db_session) if admin else False

    await callback.message.edit_text(
        format_settings_text(new_val, currency_on, coins, admin, maint_on),
        reply_markup=build_settings_keyboard(new_val, currency_on, admin, maint_on),
        parse_mode="HTML"
    )
    status_msg = "✅ Напоминание о столовой включено!" if new_val else "⬜ Напоминание о столовой выключено"
    await callback.answer(status_msg)


@router.callback_query(F.data == "set_currency_toggle")
async def cb_toggle_currency(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    new_val = await toggle_user_currency_ecosystem(db_session, current_user.tg_id)
    user = await get_user_by_tg_id(db_session, current_user.tg_id) or current_user
    canteen_on = bool(getattr(user, "canteen_reminder_enabled", False))
    coins = getattr(user, "coins", 100) or 0
    admin = is_admin(user, callback.from_user.id)
    maint_on = await MaintenanceService.is_maintenance_active(db_session) if admin else False

    await callback.message.edit_text(
        format_settings_text(canteen_on, new_val, coins, admin, maint_on),
        reply_markup=build_settings_keyboard(canteen_on, new_val, admin, maint_on),
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


@router.callback_query(F.data == "set_natbirzha_maint_toggle")
async def cb_toggle_natbirzha_maint(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        await callback.answer("⛔ Только для администраторов", show_alert=True)
        return

    new_maint = await MaintenanceService.toggle_maintenance(db_session)
    user = await get_user_by_tg_id(db_session, current_user.tg_id) or current_user
    canteen_on = bool(getattr(user, "canteen_reminder_enabled", False))
    currency_on = bool(getattr(user, "currency_ecosystem_enabled", False))
    coins = getattr(user, "coins", 100) or 0

    await callback.message.edit_text(
        format_settings_text(canteen_on, currency_on, coins, is_admin_user=True, maint_on=new_maint),
        reply_markup=build_settings_keyboard(canteen_on, currency_on, is_admin_user=True, maint_on=new_maint),
        parse_mode="HTML"
    )
    msg = "🔴 Техперерыв включен (плашка видна всем игрокам)" if new_maint else "⚪ Техперерыв выключен (плашка скрыта)"
    await callback.answer(msg, show_alert=True)
