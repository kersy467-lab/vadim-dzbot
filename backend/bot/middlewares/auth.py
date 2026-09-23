from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, ChatMemberUpdated, Update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.session import async_session_factory
from backend.db.crud import (
    get_user_by_tg_id, create_user,
    get_group_chat_by_id, has_full_access
)
from backend.bot.keyboards.inline import get_admin_approval_keyboard

class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Handle chat member updates (bot added to group)
        if isinstance(event, ChatMemberUpdated):
            async with async_session_factory() as session:
                data["db_session"] = session
                return await handler(event, data)

        user_tg = None
        chat_tg = None
        bot = data.get("bot")

        if isinstance(event, Message):
            user_tg = event.from_user
            chat_tg = event.chat
        elif isinstance(event, CallbackQuery):
            user_tg = event.from_user
            chat_tg = event.message.chat if event.message else None
        elif isinstance(event, Update):
            if event.message:
                user_tg = event.message.from_user
                chat_tg = event.message.chat
            elif event.callback_query:
                user_tg = event.callback_query.from_user
                chat_tg = event.callback_query.message.chat if event.callback_query.message else None

        if not user_tg:
            async with async_session_factory() as session:
                data["db_session"] = session
                return await handler(event, data)

        for attempt in range(2):
            try:
                async with async_session_factory() as session:
                    data["db_session"] = session
                    user = await get_user_by_tg_id(session, user_tg.id)

                    # Check if this user is the ADMIN configured in settings
                    if settings.ADMIN_ID and user_tg.id == settings.ADMIN_ID:
                        if not user:
                            user = await create_user(
                                session=session,
                                tg_id=user_tg.id,
                                full_name=user_tg.full_name or "Admin",
                                username=user_tg.username,
                                role="admin"
                            )
                        elif user.role != "admin":
                            user.role = "admin"
                            await session.commit()
                            await session.refresh(user)

                    data["current_user"] = user

                    # Забаненным пользователям (role == "rejected") бот молча не отвечает
                    if user and user.role == "rejected":
                        return

                    # Allow admin approval callbacks always
                    if isinstance(event, CallbackQuery):
                        cb_data = event.data or ""
                        if (
                            cb_data.startswith("admin_approve_") or
                            cb_data.startswith("admin_reject_") or
                            cb_data.startswith("adm_appr_") or
                            cb_data.startswith("admin_chat_approve_") or
                            cb_data.startswith("admin_chat_reject_")
                        ):
                            return await handler(event, data)

                    # ----------------- GROUP CHAT LOGIC -----------------
                    if chat_tg and chat_tg.type in ["group", "supergroup"]:
                        group_chat = await get_group_chat_by_id(session, chat_tg.id)
                        data["group_chat"] = group_chat

                        if isinstance(event, Message):
                            text = event.text or ""
                            # Allow /start or /auth in group to trigger registration request
                            if text.startswith("/start") or text.startswith("/auth"):
                                try:
                                    from backend.bot.handlers.admin.logging import log_user_action
                                    await log_user_action(bot, event, user)
                                except Exception:
                                    pass
                                return await handler(event, data)

                        if not group_chat or group_chat.role != "approved":
                            if isinstance(event, Message) and event.text and event.text.startswith("/"):
                                await event.answer(
                                    "⏳ **Этот групповой чат ожидает одобрения администратора.**\n\n"
                                    "Администратор должен подтвердить подключение чата через личные сообщения с ботом.",
                                    parse_mode="Markdown"
                                )
                            return
                        # If group is approved, execute handler with live-logging
                        try:
                            from backend.bot.handlers.admin.logging import log_user_action
                            await log_user_action(bot, event, user)
                        except Exception:
                            pass
                        return await handler(event, data)

                    # ----------------- PRIVATE CHAT LOGIC -----------------
                    if isinstance(event, Message):
                        text = event.text or ""
                        if text.startswith("/start"):
                            try:
                                from backend.bot.handlers.admin.logging import log_user_action
                                await log_user_action(bot, event, user)
                            except Exception:
                                pass
                            return await handler(event, data)

                    # Public EGE Arena users no longer require approval.
                    if not user:
                        if isinstance(event, Message):
                            await event.answer("🎓 Сначала отправьте /start, чтобы войти в ЕГЭ Арену.")
                        elif isinstance(event, CallbackQuery):
                            await event.answer("Сначала отправьте /start", show_alert=True)
                        return

                    # Public accounts can use only EGE Arena bot commands and nickname flow.
                    if not has_full_access(user):
                        allowed = False
                        if isinstance(event, Message):
                            text = (event.text or "").strip()
                            allowed = (
                                text.startswith("/stats")
                                or text.startswith("/nick")
                                or text in {"📊 Моя статистика", "✏️ Сменить ник"}
                            )
                            state = data.get("state")
                            if state is not None:
                                try:
                                    state_name = await state.get_state()
                                    allowed = allowed or bool(state_name and state_name.endswith("NicknameSetupStates:entering_nickname"))
                                except Exception:
                                    pass
                        elif isinstance(event, CallbackQuery):
                            allowed = (event.data or "").startswith("game_reject:")

                        if not allowed:
                            from backend.bot.keyboards.main_menu import get_arena_keyboard
                            if isinstance(event, Message):
                                await event.answer(
                                    "🎓 Вам доступна <b>ЕГЭ Арена</b>: дуэли, рейтинг и статистика.",
                                    reply_markup=get_arena_keyboard(user.tg_id),
                                    parse_mode="HTML",
                                )
                            elif isinstance(event, CallbackQuery):
                                await event.answer("Доступна только ЕГЭ Арена", show_alert=True)
                            return


                    # Live-логирование действий пользователя
                    try:
                        from backend.bot.handlers.admin.logging import log_user_action
                        await log_user_action(bot, event, user)
                    except Exception:
                        pass

                    try:
                        return await handler(event, data)
                    except Exception as handler_err:
                        from aiogram.exceptions import TelegramBadRequest
                        if isinstance(handler_err, TelegramBadRequest) and "message is not modified" in str(handler_err).lower():
                            if isinstance(event, CallbackQuery):
                                try:
                                    await event.answer("Данные уже актуальны ⏳")
                                except Exception:
                                    pass
                            return
                        if isinstance(event, CallbackQuery):
                            try:
                                await event.answer("⚠️ Произошла ошибка. Попробуйте снова.", show_alert=True)
                            except Exception:
                                pass
                        raise handler_err

            except Exception as e:
                # If network or database connection dropped from idle state, retry once with a clean connection
                if attempt == 0 and any(err_str in str(e).lower() for err_str in ["connection", "ssl", "closed", "reset", "timeout", "eof"]):
                    import asyncio
                    await asyncio.sleep(0.15)
                    continue
                raise e

