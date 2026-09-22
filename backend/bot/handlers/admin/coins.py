import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud.users import get_active_users, get_user_by_tg_id, get_user_by_username, add_user_coins
from backend.bot.handlers.admin.helpers import is_admin
from backend.bot.keyboards.admin_kb import get_admin_panel_keyboard

logger = logging.getLogger(__name__)

router = Router(name="admin_coins_router")


class AdminGiveCoinsStates(StatesGroup):
    waiting_for_amount = State()


def _build_user_coins_keyboard(target_tg_id: int, silent: bool = False) -> InlineKeyboardMarkup:
    s_suffix = "_1" if silent else ""
    toggle_text = "🔕 Уведомление: ВЫКЛ ⚪" if silent else "🔔 Уведомление: ВКЛ 🟢"
    new_s_flag = "0" if silent else "1"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="+50 🪙", callback_data=f"adm_gc_add_{target_tg_id}_50{s_suffix}"),
                InlineKeyboardButton(text="+100 🪙", callback_data=f"adm_gc_add_{target_tg_id}_100{s_suffix}")
            ],
            [
                InlineKeyboardButton(text="+250 🪙", callback_data=f"adm_gc_add_{target_tg_id}_250{s_suffix}"),
                InlineKeyboardButton(text="+500 🪙", callback_data=f"adm_gc_add_{target_tg_id}_500{s_suffix}")
            ],
            [
                InlineKeyboardButton(text="+1000 🪙", callback_data=f"adm_gc_add_{target_tg_id}_1000{s_suffix}"),
                InlineKeyboardButton(text="✏️ Своя сумма", callback_data=f"adm_gc_custom_{target_tg_id}{s_suffix}")
            ],
            [
                InlineKeyboardButton(text=toggle_text, callback_data=f"adm_gc_toggle_{target_tg_id}_{new_s_flag}")
            ],
            [
                InlineKeyboardButton(text="👥 К списку пользователей", callback_data="admin_give_coins"),
                InlineKeyboardButton(text="🔙 В меню", callback_data="admin_menu_back")
            ]
        ]
    )


def _render_user_coins_text(target: User, silent: bool = False) -> str:
    coins = getattr(target, "coins", 0) or 0
    uname = f" (@{target.username})" if target.username else ""
    status_text = (
        "🔕 <b>Режим:</b> Без уведомления <i>(тихое начисление)</i>"
        if silent else
        "🔔 <b>Режим:</b> С уведомлением <i>(отправка в ЛС)</i>"
    )
    return (
        f"🪙 <b>Управление балансом пользователя</b>\n\n"
        f"👤 <b>{target.display_name}</b>{uname}\n"
        f"🆔 Telegram ID: <code>{target.tg_id}</code>\n"
        f"💰 Текущий баланс: <b>{coins}</b> 🪙 монет\n\n"
        f"{status_text}\n\n"
        "Выберите быструю сумму или нажмите <b>«Своя сумма»</b>:"
    )


def _build_result_keyboard(target_tg_id: int, silent: bool) -> InlineKeyboardMarkup:
    s_suffix = "_1" if silent else ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Выдать ещё", callback_data=f"adm_gc_u_{target_tg_id}{s_suffix}"),
                InlineKeyboardButton(text="👥 К списку", callback_data="admin_give_coins")
            ],
            [InlineKeyboardButton(text="👑 В панель управления", callback_data="admin_menu_back")]
        ]
    )


def _render_success_text(target: User, amount: int, new_balance: int, silent: bool) -> str:
    op_word = "начислено" if amount >= 0 else "списано"
    sign = "+" if amount >= 0 else ""
    notif = "🔕 <i>Уведомление: Не отправлялось (тихий режим).</i>" if silent else "🔔 <i>Пользователю отправлено уведомление в ЛС.</i>"
    return (
        f"✅ <b>Баланс успешно обновлён!</b>\n\n"
        f"👤 Пользователь: <b>{target.display_name}</b>\n"
        f"💰 Операция: <b>{sign}{amount}</b> 🪙 ({op_word})\n"
        f"💎 Новый баланс: <b>{new_balance}</b> 🪙 монет\n\n"
        f"{notif}"
    )


async def _notify_user_coins(bot: Bot, target_tg_id: int, amount: int, new_balance: int, silent: bool):
    if silent:
        return
    try:
        msg = (
            f"🎁 <b>Вам начислены монеты!</b>\n\n"
            f"Администратор начислил вам <b>+{amount}</b> 🪙 монет.\n"
            f"Ваш текущий баланс: <b>{new_balance}</b> 🪙 монет.\n\n"
            "<i>Используйте монеты в игре «Дурак» в Mini App!</i>"
            if amount >= 0 else
            f"⚠️ <b>Списание монет</b>\n\n"
            f"Администратор списал у вас <b>{abs(amount)}</b> 🪙 монет.\n"
            f"Ваш текущий баланс: <b>{new_balance}</b> 🪙 монет."
        )
        await bot.send_message(chat_id=target_tg_id, text=msg, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Failed to notify user {target_tg_id}: {e}")


def _build_users_list_keyboard(users: list) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"👤 {u.display_name} ({getattr(u, 'coins', 0) or 0} 🪙)", callback_data=f"adm_gc_u_{u.tg_id}")]
        for u in users
    ]
    buttons.append([InlineKeyboardButton(text="🔙 В панель управления", callback_data="admin_menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "admin_give_coins")
async def cb_admin_give_coins_list(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        await callback.answer("⛔ Только для администраторов", show_alert=True)
        return

    users = await get_active_users(db_session)
    if not users:
        await callback.message.edit_text("ℹ️ В базе пока нет зарегистрированных учеников.", reply_markup=get_admin_panel_keyboard())
        return

    await callback.message.edit_text(
        "🪙 <b>Выдача монет ученикам 11 «Б»</b>\n\nВыберите пользователя:",
        reply_markup=_build_users_list_keyboard(users),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_gc_toggle_"))
async def cb_admin_give_coins_toggle(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    parts = callback.data.split("_")
    target_tg_id = int(parts[3])
    new_silent = bool(int(parts[4]))

    target = await get_user_by_tg_id(db_session, target_tg_id)
    if not target:
        await callback.answer("⚠️ Пользователь не найден", show_alert=True)
        return

    await callback.message.edit_text(
        _render_user_coins_text(target, silent=new_silent),
        reply_markup=_build_user_coins_keyboard(target_tg_id, silent=new_silent),
        parse_mode="HTML"
    )
    toast = "🔕 Режим без уведомления ВКЛЮЧЕН" if new_silent else "🔔 Режим с уведомлением ВКЛЮЧЕН"
    await callback.answer(toast)


@router.callback_query(F.data.startswith("adm_gc_u_"))
async def cb_admin_give_coins_user(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    raw = callback.data.replace("adm_gc_u_", "")
    parts = raw.split("_")
    target_tg_id = int(parts[0])
    silent = bool(int(parts[1])) if len(parts) > 1 else False

    target = await get_user_by_tg_id(db_session, target_tg_id)
    if not target:
        await callback.answer("⚠️ Пользователь не найден", show_alert=True)
        return

    await callback.message.edit_text(
        _render_user_coins_text(target, silent=silent),
        reply_markup=_build_user_coins_keyboard(target_tg_id, silent=silent),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_gc_add_"))
async def cb_admin_give_coins_fast(callback: CallbackQuery, db_session: AsyncSession, current_user: User, bot: Bot):
    if not is_admin(current_user, callback.from_user.id):
        return

    parts = callback.data.split("_")
    target_tg_id = int(parts[3])
    amount = int(parts[4])
    silent = bool(int(parts[5])) if len(parts) > 5 else False

    new_balance = await add_user_coins(db_session, target_tg_id, amount)
    target = await get_user_by_tg_id(db_session, target_tg_id)
    if not target or new_balance is None:
        await callback.answer("⚠️ Не удалось изменить баланс", show_alert=True)
        return

    if not getattr(target, "currency_ecosystem_enabled", False):
        target.currency_ecosystem_enabled = True
        await db_session.commit()

    await callback.message.edit_text(
        _render_success_text(target, amount, new_balance, silent),
        reply_markup=_build_result_keyboard(target_tg_id, silent),
        parse_mode="HTML"
    )
    alert = f"✅ Начислено +{amount} 🪙 (без уведомления)!" if silent else f"✅ Начислено +{amount} 🪙!"
    await callback.answer(alert)
    await _notify_user_coins(bot, target_tg_id, amount, new_balance, silent)


@router.callback_query(F.data.startswith("adm_gc_custom_"))
async def cb_admin_give_coins_custom_prompt(callback: CallbackQuery, state: FSMContext, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    raw = callback.data.replace("adm_gc_custom_", "")
    parts = raw.split("_")
    target_tg_id = int(parts[0])
    silent = bool(int(parts[1])) if len(parts) > 1 else False

    await state.set_state(AdminGiveCoinsStates.waiting_for_amount)
    await state.update_data(target_tg_id=target_tg_id, silent=silent)

    s_suffix = "_1" if silent else ""
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data=f"adm_gc_u_{target_tg_id}{s_suffix}")]])
    mode = "🔕 <i>Режим: без уведомления пользователю</i>\n\n" if silent else "🔔 <i>Режим: с уведомлением пользователю в ЛС</i>\n\n"

    await callback.message.edit_text(
        f"✏️ <b>Введите сумму для начисления:</b>\n\n{mode}"
        "Отправьте целое число сообщением:\n• Например, <code>350</code> или <code>-100</code>:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AdminGiveCoinsStates.waiting_for_amount)
async def msg_admin_give_coins_custom_input(message: Message, state: FSMContext, db_session: AsyncSession, current_user: User, bot: Bot):
    if not is_admin(current_user, message.from_user.id):
        return

    text = message.text.strip().replace(" ", "").replace("+", "")
    try:
        amount = int(text)
    except ValueError:
        await message.answer("⚠️ Введите целое число (например, <code>200</code> или <code>-50</code>):", parse_mode="HTML")
        return

    data = await state.get_data()
    target_tg_id = data.get("target_tg_id")
    silent = bool(data.get("silent", False))
    await state.clear()

    new_balance = await add_user_coins(db_session, target_tg_id, amount)
    target = await get_user_by_tg_id(db_session, target_tg_id)
    if not target or new_balance is None:
        await message.answer("⚠️ Не удалось изменить баланс.")
        return

    if not getattr(target, "currency_ecosystem_enabled", False):
        target.currency_ecosystem_enabled = True
        await db_session.commit()

    await message.answer(
        _render_success_text(target, amount, new_balance, silent),
        reply_markup=_build_result_keyboard(target_tg_id, silent),
        parse_mode="HTML"
    )
    await _notify_user_coins(bot, target_tg_id, amount, new_balance, silent)


@router.message(Command("give_coins"))
@router.message(Command("givecoins"))
async def cmd_admin_give_coins(message: Message, current_user: User, db_session: AsyncSession, bot: Bot):
    if not is_admin(current_user, message.from_user.id):
        return

    text = (message.text or "").strip()
    parts = text.split()

    if len(parts) == 1:
        users = await get_active_users(db_session)
        if not users:
            await message.answer("ℹ️ В базе пока нет зарегистрированных учеников.")
            return
        await message.answer(
            "🪙 <b>Выдача монет ученикам 11 «Б»</b>\n\nВыберите пользователя:",
            reply_markup=_build_users_list_keyboard(users),
            parse_mode="HTML"
        )
        return

    if len(parts) < 3:
        await message.answer(
            "⚠️ <b>Использование:</b>\n"
            "• <code>/givecoins @username 500</code> — с уведомлением\n"
            "• <code>/givecoins @username 500 тихо</code> — <b>без уведомления</b> (или <code>silent</code>)\n"
            "• <code>/givecoins 123456789 250 тихо</code>",
            parse_mode="HTML"
        )
        return

    try:
        amount = int(parts[2].replace("+", ""))
    except ValueError:
        await message.answer("⚠️ Сумма должна быть целым числом.", parse_mode="HTML")
        return

    silent = False
    if len(parts) >= 4 and parts[3].lower() in ("тихо", "silent", "-s", "--silent", "тихий", "mute", "off"):
        silent = True

    target_ident = parts[1]
    if target_ident.isdigit():
        target = await get_user_by_tg_id(db_session, int(target_ident))
    else:
        target = await get_user_by_username(db_session, target_ident.lstrip("@").strip().lower())

    if not target:
        await message.answer(f"⚠️ Пользователь <code>{target_ident}</code> не найден.", parse_mode="HTML")
        return

    new_balance = await add_user_coins(db_session, target.tg_id, amount)
    if new_balance is None:
        await message.answer("⚠️ Не удалось изменить баланс.")
        return

    if not getattr(target, "currency_ecosystem_enabled", False):
        target.currency_ecosystem_enabled = True
        await db_session.commit()

    await message.answer(
        _render_success_text(target, amount, new_balance, silent),
        reply_markup=_build_result_keyboard(target.tg_id, silent),
        parse_mode="HTML"
    )
    await _notify_user_coins(bot, target.tg_id, amount, new_balance, silent)
