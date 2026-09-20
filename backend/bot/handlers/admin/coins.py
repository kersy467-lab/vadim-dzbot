import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud.users import get_active_users, get_user_by_tg_id, add_user_coins
from backend.bot.handlers.admin.helpers import is_admin
from backend.bot.keyboards.admin_kb import get_admin_panel_keyboard

logger = logging.getLogger(__name__)

router = Router(name="admin_coins_router")


class AdminGiveCoinsStates(StatesGroup):
    waiting_for_amount = State()


@router.callback_query(F.data == "admin_give_coins")
async def cb_admin_give_coins_list(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        await callback.answer("⛔ Только для администраторов", show_alert=True)
        return

    users = await get_active_users(db_session)
    if not users:
        await callback.message.edit_text(
            "ℹ️ В базе пока нет зарегистрированных учеников.",
            reply_markup=get_admin_panel_keyboard()
        )
        return

    buttons = []
    for u in users:
        coins = getattr(u, "coins", 0) or 0
        buttons.append([
            InlineKeyboardButton(
                text=f"👤 {u.display_name} ({coins} 🪙)",
                callback_data=f"adm_gc_u_{u.tg_id}"
            )
        ])

    buttons.append([InlineKeyboardButton(text="🔙 В панель управления", callback_data="admin_menu_back")])

    await callback.message.edit_text(
        "🪙 <b>Выдача монет ученикам 11 «Б»</b>\n\n"
        "Выберите пользователя, которому хотите начислить или изменить баланс:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm_gc_u_"))
async def cb_admin_give_coins_user(callback: CallbackQuery, db_session: AsyncSession, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    target_tg_id = int(callback.data.replace("adm_gc_u_", ""))
    target = await get_user_by_tg_id(db_session, target_tg_id)
    if not target:
        await callback.answer("⚠️ Пользователь не найден", show_alert=True)
        return

    coins = getattr(target, "coins", 0) or 0
    uname = f" (@{target.username})" if target.username else ""

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="+50 🪙", callback_data=f"adm_gc_add_{target_tg_id}_50"),
                InlineKeyboardButton(text="+100 🪙", callback_data=f"adm_gc_add_{target_tg_id}_100")
            ],
            [
                InlineKeyboardButton(text="+250 🪙", callback_data=f"adm_gc_add_{target_tg_id}_250"),
                InlineKeyboardButton(text="+500 🪙", callback_data=f"adm_gc_add_{target_tg_id}_500")
            ],
            [
                InlineKeyboardButton(text="+1000 🪙", callback_data=f"adm_gc_add_{target_tg_id}_1000"),
                InlineKeyboardButton(text="✏️ Своя сумма", callback_data=f"adm_gc_custom_{target_tg_id}")
            ],
            [
                InlineKeyboardButton(text="👥 К списку пользователей", callback_data="admin_give_coins"),
                InlineKeyboardButton(text="🔙 В меню", callback_data="admin_menu_back")
            ]
        ]
    )

    await callback.message.edit_text(
        f"🪙 <b>Управление балансом пользователя</b>\n\n"
        f"👤 <b>{target.display_name}</b>{uname}\n"
        f"🆔 Telegram ID: <code>{target.tg_id}</code>\n"
        f"💰 Текущий баланс: <b>{coins}</b> 🪙 монет\n\n"
        "Выберите быструю сумму для пополнения или нажмите <b>«Своя сумма»</b>:",
        reply_markup=kb,
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

    new_balance = await add_user_coins(db_session, target_tg_id, amount)
    target = await get_user_by_tg_id(db_session, target_tg_id)
    if not target or new_balance is None:
        await callback.answer("⚠️ Не удалось изменить баланс", show_alert=True)
        return

    # Automatically ensure currency ecosystem is active for them
    if not getattr(target, "currency_ecosystem_enabled", False):
        target.currency_ecosystem_enabled = True
        await db_session.commit()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Выдать ещё", callback_data=f"adm_gc_u_{target_tg_id}"),
                InlineKeyboardButton(text="👥 К списку", callback_data="admin_give_coins")
            ],
            [
                InlineKeyboardButton(text="👑 В панель управления", callback_data="admin_menu_back")
            ]
        ]
    )

    await callback.message.edit_text(
        f"✅ <b>Монеты успешно начислены!</b>\n\n"
        f"👤 Пользователь: <b>{target.display_name}</b>\n"
        f"💰 Начислено: <b>+{amount}</b> 🪙 монет\n"
        f"💎 Новый баланс: <b>{new_balance}</b> 🪙 монет",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer(f"✅ Начислено +{amount} 🪙!")

    # Notify user in PM
    try:
        await bot.send_message(
            chat_id=target_tg_id,
            text=(
                f"🎁 <b>Вам начислены монеты!</b>\n\n"
                f"Администратор начислил вам <b>+{amount}</b> 🪙 монет.\n"
                f"Ваш текущий баланс: <b>{new_balance}</b> 🪙 монет.\n\n"
                "<i>Используйте монеты в игре «Дурак» в Mini App!</i>"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.warning(f"Failed to notify user {target_tg_id} about coins: {e}")


@router.callback_query(F.data.startswith("adm_gc_custom_"))
async def cb_admin_give_coins_custom_prompt(callback: CallbackQuery, state: FSMContext, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    target_tg_id = int(callback.data.replace("adm_gc_custom_", ""))
    await state.set_state(AdminGiveCoinsStates.waiting_for_amount)
    await state.update_data(target_tg_id=target_tg_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"adm_gc_u_{target_tg_id}")]
        ]
    )

    await callback.message.edit_text(
        "✏️ <b>Введите сумму для начисления:</b>\n\n"
        "Отправьте целое число сообщением:\n"
        "• Например, <code>350</code> — чтобы начислить 350 монет.\n"
        "• Или <code>-100</code> — чтобы списать 100 монет.",
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
        await message.answer("⚠️ Пожалуйста, введите целое число (например, <code>200</code> или <code>-50</code>):", parse_mode="HTML")
        return

    data = await state.get_data()
    target_tg_id = data.get("target_tg_id")
    await state.clear()

    new_balance = await add_user_coins(db_session, target_tg_id, amount)
    target = await get_user_by_tg_id(db_session, target_tg_id)

    if not target or new_balance is None:
        await message.answer("⚠️ Не удалось изменить баланс (возможно, баланс не может быть отрицательным).")
        return

    if not getattr(target, "currency_ecosystem_enabled", False):
        target.currency_ecosystem_enabled = True
        await db_session.commit()

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Выдать ещё", callback_data=f"adm_gc_u_{target_tg_id}"),
                InlineKeyboardButton(text="👥 К списку", callback_data="admin_give_coins")
            ],
            [
                InlineKeyboardButton(text="👑 В панель управления", callback_data="admin_menu_back")
            ]
        ]
    )

    op_word = "начислено" if amount >= 0 else "списано"
    sign = "+" if amount >= 0 else ""
    await message.answer(
        f"✅ <b>Баланс успешно обновлён!</b>\n\n"
        f"👤 Пользователь: <b>{target.display_name}</b>\n"
        f"💰 Операция: <b>{sign}{amount}</b> 🪙 ({op_word})\n"
        f"💎 Новый баланс: <b>{new_balance}</b> 🪙 монет",
        reply_markup=kb,
        parse_mode="HTML"
    )

    # Notify user in PM
    try:
        user_msg = (
            f"🎁 <b>Вам начислены монеты!</b>\n\nАдминистратор начислил вам <b>+{amount}</b> 🪙 монет.\nВаш текущий баланс: <b>{new_balance}</b> 🪙 монет."
            if amount >= 0 else
            f"⚠️ <b>Списание монет</b>\n\nАдминистратор списал у вас <b>{abs(amount)}</b> 🪙 монет.\nВаш текущий баланс: <b>{new_balance}</b> 🪙 монет."
        )
        await bot.send_message(chat_id=target_tg_id, text=user_msg, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Failed to notify user {target_tg_id}: {e}")
