from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.db.crud.users import perform_user_work, get_user_by_tg_id

router = Router(name="economy_router")


@router.message(Command("cash"))
@router.message(Command("balance"))
async def cmd_cash(message: Message, current_user: User, db_session: AsyncSession):
    # Refresh user to get latest coins
    user = await get_user_by_tg_id(db_session, current_user.tg_id) or current_user

    if not bool(getattr(user, "currency_ecosystem_enabled", False)):
        await message.answer(
            "⚠️ <b>Игровая экосистема выключена</b>\n\n"
            "Чтобы просматривать баланс монет, зарабатывать и играть в «Дурака» со ставками, "
            "откройте раздел <b>⚙️ Настройки</b> и включите <b>«🪙 Игровая экосистема»</b>.",
            parse_mode="HTML"
        )
        return

    coins = user.coins or 0
    await message.answer(
        f"🪙 <b>Ваш кошелёк 11 «Б»:</b>\n\n"
        f"Текущий баланс: <b>{coins}</b> 🪙 монет\n\n"
        "💡 <i>Используйте <code>/work</code> каждый день для получения зарплаты или выигрывайте монеты в игре «Дурак»!</i>",
        parse_mode="HTML"
    )


@router.message(Command("work"))
async def cmd_work(message: Message, current_user: User, db_session: AsyncSession):
    user = await get_user_by_tg_id(db_session, current_user.tg_id) or current_user

    if not bool(getattr(user, "currency_ecosystem_enabled", False)):
        await message.answer(
            "⚠️ <b>Игровая экосистема выключена</b>\n\n"
            "Чтобы работать и получать монеты, перейдите в <b>⚙️ Настройки</b> и включите <b>«🪙 Игровая экосистема»</b>.",
            parse_mode="HTML"
        )
        return

    success, coins, msg = await perform_user_work(db_session, current_user.tg_id, reward=75)

    if not success:
        await message.answer(
            f"⏳ <b>Вы уже работали сегодня!</b>\n\n"
            "Следующая смена будет доступна завтра после 00:00.\n"
            f"Текущий баланс: <b>{coins}</b> 🪙 монет.",
            parse_mode="HTML"
        )
        return

    await message.answer(
        f"💼 <b>Смена успешно завершена!</b>\n\n"
        f"Вы заработали: <b>+75</b> 🪙 монет!\n"
        f"Новый баланс: <b>{coins}</b> 🪙 монет.\n\n"
        "<i>Возвращайтесь завтра за новой порцией монет!</i>",
        parse_mode="HTML"
    )
