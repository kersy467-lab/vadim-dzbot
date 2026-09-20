from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models import User
from backend.db.crud import get_user_by_tg_id, create_user, update_user_role, update_user_name_and_role
from backend.bot.keyboards.main_menu import get_main_keyboard
from backend.bot.keyboards.admin_kb import get_admin_panel_keyboard
from backend.bot.keyboards.inline import get_admin_approval_keyboard
from backend.bot.handlers.admin.states import ApproveUserStates

router = Router(name="start_router")

async def register_pending_user_and_notify_admin(
    bot: Bot,
    session: AsyncSession,
    user_id: int,
    full_name: str,
    username: str | None
) -> User:
    user = await get_user_by_tg_id(session, user_id)
    is_reapply = False

    if not user:
        user = await create_user(
            session=session,
            tg_id=user_id,
            full_name=full_name,
            username=username,
            role="pending"
        )
    elif user.role in ["rejected", "pending"]:
        user.role = "pending"
        user.full_name = full_name
        user.username = username
        await session.commit()
        await session.refresh(user)
        is_reapply = True
    else:
        return user

    # Notify all admins about registration request
    from backend.bot.services.notifier import notify_all_admins
    uname_str = f"@{username}" if username else "без @username"
    title = "🔔 **Повторная заявка на доступ к боту!**" if is_reapply else "🔔 **Новая заявка на доступ к боту!**"
    admin_text = (
        f"{title}\n\n"
        f"👤 **Пользователь:** {full_name}\n"
        f"🔗 **Telegram:** {uname_str}"
    )
    await notify_all_admins(
        bot=bot,
        session=session,
        text=admin_text,
        reply_markup=get_admin_approval_keyboard(user_id)
    )
    return user


@router.message(CommandStart())
async def cmd_start(message: Message, db_session: AsyncSession, bot: Bot, current_user: User | None = None):
    user_id = message.from_user.id
    username = message.from_user.username
    full_name = message.from_user.full_name or "Ученик"

    is_user_adm = bool((current_user and current_user.role == "admin") or (settings.ADMIN_ID and user_id == settings.ADMIN_ID))
    is_tester = bool(getattr(current_user, "is_tester", False)) if current_user else False

    local_app_link = ""
    if not settings.WEBAPP_URL.startswith("https://"):
        local_app_link = f"\n\n💻 **Mini App 11 «Б»:** http://localhost:{settings.PORT}/app?tg_user_id={user_id}"
        if is_user_adm or is_tester:
            local_app_link += f"\n📈 **Игра «НАТБИРЖА» (Beta):** http://localhost:{settings.PORT}/app/natbirzha"

    # If user is admin
    if settings.ADMIN_ID and user_id == settings.ADMIN_ID:
        await message.answer(
            f"👋 **Здравствуйте, Администратор ({full_name})!**\n\n"
            "Вам доступно полное управление ботом класса, расписанием, ДЗ и заявками учеников."
            f"{local_app_link}",
            reply_markup=get_main_keyboard(is_admin=True, user_id=user_id, is_tester=True),
            parse_mode="Markdown"
        )
        return

    # If user is already registered and approved
    if current_user and current_user.role in ["student", "admin"]:
        role_label = " (Администратор)" if is_user_adm else ""
        await message.answer(
            f"👋 **Привет, {current_user.display_name}!**{role_label}\n\n"
            "Добро пожаловать в бот класса! Выберите нужный раздел в меню ниже:"
            f"{local_app_link}",
            reply_markup=get_main_keyboard(is_admin=is_user_adm, user_id=user_id, is_tester=is_tester),
            parse_mode="Markdown"
        )
        return


    # If not registered, create pending and notify admin
    await register_pending_user_and_notify_admin(
        bot=bot,
        session=db_session,
        user_id=user_id,
        full_name=full_name,
        username=username
    )

    await message.answer(
        "👋 **Добро пожаловать в бот 11 «Б»!**\n\n"
        "⏳ **Ваша заявка отправлена администратору.**\n"
        "Как только администратор подтвердит ваш доступ, вам откроется меню, расписание и Mini App.",
        parse_mode="Markdown"
    )


# Admin approve callback
@router.callback_query(F.data.startswith("admin_approve_"))
async def callback_admin_approve(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession):
    target_tg_id = int(callback.data.replace("admin_approve_", ""))
    target_user = await get_user_by_tg_id(db_session, target_tg_id)
    if not target_user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    if target_user.role not in ["pending", "rejected"]:
        await callback.answer(f"Пользователь уже одобрен и имеет доступ (статус: {target_user.role})!", show_alert=True)
        return

    await state.set_state(ApproveUserStates.entering_name)
    await state.update_data(approve_target_tg_id=target_tg_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"👌 Оставить «{target_user.full_name}»",
                    callback_data=f"adm_appr_keep_{target_tg_id}"
                )
            ],
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")
            ]
        ]
    )

    await callback.message.edit_text(
        f"👤 **Одобрение заявки: {target_user.full_name}**\n\n"
        "✍️ **Введите имя и фамилию ученика**, как они будут отображаться в боте, Mini App и списке дежурных (например: `Иван Иванов`):\n\n"
        f"Либо нажмите кнопку ниже, чтобы оставить имя из Telegram:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_appr_keep_"))
async def callback_admin_approve_keep(callback: CallbackQuery, state: FSMContext, db_session: AsyncSession, bot: Bot):
    target_tg_id = int(callback.data.replace("adm_appr_keep_", ""))
    user = await update_user_role(db_session, target_tg_id, "student")
    await state.clear()

    display_name = user.display_name if user else "Ученик"
    await callback.message.edit_text(
        f"✅ **Заявка одобрена!**\n\n"
        f"👤 Ученик: **{display_name}**\n"
        f"👑 Одобрил: {callback.from_user.full_name}",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer("Заявка одобрена!")
    except Exception:
        pass

    # Notify student
    try:
        await bot.send_message(
            chat_id=target_tg_id,
            text=(
                f"🎉 **Ваш доступ подтвержден администратором!**\n\n"
                f"👤 Ваше имя в системе: **{display_name}**\n\n"
                "Теперь вам доступно расписание, домашние задания и Mini App класса."
            ),
            reply_markup=get_main_keyboard(
                is_admin=False,
                user_id=target_tg_id,
                is_tester=bool(getattr(user, "is_tester", False))
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Failed to notify user {target_tg_id}: {e}")


@router.message(ApproveUserStates.entering_name)
async def msg_admin_approve_custom_name(message: Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    name = message.text.strip()
    if not name or len(name) < 2:
        await message.answer("⚠️ Введите корректное имя и фамилию ученика:")
        return

    data = await state.get_data()
    target_tg_id = data.get("approve_target_tg_id")
    if not target_tg_id:
        await state.clear()
        return

    user = await update_user_name_and_role(db_session, target_tg_id, custom_name=name, role="student")
    await state.clear()

    await message.answer(
        f"✅ **Ученик успешно зарегистрирован и одобрен!**\n\n"
        f"👤 Официальное имя: **{name}**\n"
        f"Это имя будет отображаться в Mini App и списках дежурных.",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )

    # Notify student
    try:
        await bot.send_message(
            chat_id=target_tg_id,
            text=(
                f"🎉 **Ваш доступ подтвержден администратором!**\n\n"
                f"👤 Ваше имя в системе: **{name}**\n\n"
                "Теперь вам доступно расписание, домашние задания и Mini App класса."
            ),
            reply_markup=get_main_keyboard(
                is_admin=False,
                user_id=target_tg_id,
                is_tester=bool(getattr(user, "is_tester", False))
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Failed to notify user {target_tg_id}: {e}")


# Admin reject callback
@router.callback_query(F.data.startswith("admin_reject_"))
async def callback_admin_reject(callback: CallbackQuery, db_session: AsyncSession, bot: Bot):
    target_tg_id = int(callback.data.replace("admin_reject_", ""))
    target_user = await get_user_by_tg_id(db_session, target_tg_id)
    if not target_user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    if target_user.role != "pending":
        await callback.answer(f"Заявка уже обработана (статус: {target_user.role})!", show_alert=True)
        return

    await update_user_role(db_session, target_tg_id, "rejected")
    
    await callback.message.edit_text(
        f"{callback.message.text}\n\n❌ **ОТКЛОНЕНО** администратором {callback.from_user.full_name}",
        parse_mode="Markdown"
    )
    await callback.answer("Заявка отклонена!")

    try:
        await bot.send_message(
            chat_id=target_tg_id,
            text=(
                "❌ **Доступ к боту класса был отклонен администратором.**\n\n"
                "Если это произошло по ошибке или вам требуется доступ, вы можете отправить заявку повторно с помощью команды /start."
            ),
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Failed to notify user {target_tg_id}: {e}")


# Game challenge reject callback
@router.callback_query(F.data.startswith("game_reject:"))
async def callback_game_reject(callback: CallbackQuery, bot: Optional[Bot] = None):
    room_id = callback.data.split(":", 1)[1]
    from backend.api.game_rooms import game_manager
    from backend.bot.bot import get_current_bot
    bot = bot or get_current_bot()
    room = game_manager.get_room(room_id)
    game_name = "Шахматы" if (room and getattr(room, "game_type", "") == "chess") else "Крестики-нолики"
    if room:
        game_manager.reject_room(room_id, callback.from_user.id)
        if bot:
            try:
                await bot.send_message(
                    chat_id=room.host_tg_id,
                    text=f"❌ <b>{callback.from_user.full_name}</b> отклонил(а) ваш вызов в {game_name}."
                )
            except Exception:
                pass

    try:
        await callback.message.edit_text(
            f"❌ <b>Вызов в {game_name} отклонен.</b>",
            reply_markup=None
        )
    except Exception:
        pass
    await callback.answer("Вызов отклонен")

