"""
Модуль логирования действий пользователей.
Состояние хранится в RAM (dict), не сохраняется в БД.
При перезапуске сервера логирование сбрасывается.
"""
import logging
from typing import Dict, Set, Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

from backend.config import settings
from backend.bot.handlers.admin.helpers import is_admin
from backend.db.models import User
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = Router(name="admin_logging_router")

# Хранилище: tg_id -> набор включённых режимов
# Режимы: "messages", "buttons", "inline"
_log_targets: Dict[int, Set[str]] = {}

# ========================
# Публичное API
# ========================

def start_logging(tg_id: int, modes: Set[str]) -> None:
    """Включить логирование для пользователя с заданными режимами."""
    _log_targets[tg_id] = modes.copy()


def stop_logging(tg_id: int) -> None:
    """Полностью отключить логирование для пользователя."""
    _log_targets.pop(tg_id, None)


def toggle_mode(tg_id: int, mode: str) -> bool:
    """Переключить режим. Возвращает True если режим теперь включён."""
    if tg_id not in _log_targets:
        _log_targets[tg_id] = set()
    if mode in _log_targets[tg_id]:
        _log_targets[tg_id].discard(mode)
        if not _log_targets[tg_id]:
            del _log_targets[tg_id]
        return False
    else:
        _log_targets[tg_id].add(mode)
        return True


def get_log_modes(tg_id: int) -> Set[str]:
    """Вернуть активные режимы логирования для пользователя."""
    return _log_targets.get(tg_id, set())


def is_logged(tg_id: int) -> bool:
    """Проверить, ведётся ли логирование для пользователя."""
    return tg_id in _log_targets and bool(_log_targets[tg_id])


def get_all_logged_users() -> Dict[int, Set[str]]:
    """Вернуть всех логируемых пользователей и их режимы."""
    return dict(_log_targets)


# ========================
import html

# ========================
# Live-отправка событий
# ========================

async def log_user_action(bot: Bot, event, user: Optional[User]) -> None:
    """
    Вызывается из middleware после каждого события.
    Отправляет информацию о действии напрямую в чат администратора.
    """
    if not user or not settings.ADMIN_ID:
        return
    if user.tg_id == settings.ADMIN_ID:
        return  # Не логировать самого администратора-получателя (предотвращение зацикливания)
    if not is_logged(user.tg_id):
        return

    modes = get_log_modes(user.tg_id)
    name = user.display_name
    tg_id = user.tg_id

    try:
        safe_name = html.escape(str(name or "Пользователь"))
        if isinstance(event, Message):
            text = event.text or event.caption or ""
            media_tag = ""
            if event.photo:
                media_tag = "[📷 Фото]"
            elif event.voice:
                media_tag = "[🎤 Голосовое]"
            elif event.video_note:
                media_tag = "[📹 Кружочек]"
            elif event.video:
                media_tag = "[🎥 Видео]"
            elif event.document:
                doc_name = html.escape(event.document.file_name or "файл")
                media_tag = f"[📄 Документ: {doc_name}]"
            elif event.sticker:
                stk_emoji = event.sticker.emoji or ""
                media_tag = f"[🎭 Стикер {stk_emoji}]"

            # Полный актуальный список текстов кнопок постоянного меню
            button_texts = {
                "📅 Расписание", "📚 Домашка", "📚 Домашнее задание",
                "🔔 Звонки", "🧹 График дежурств", "🏠 Дежурства",
                "🎂 Дни рождения", "💡 Интересный факт", "ℹ️ Факт дня",
                "⏳ Сейчас", "☀️ До лета осталось", "🎮 Мини-приложение",
                "📱 Mini App 11 «Б»", "⚙️ Настройки", "👑 Панель управления",
                "👑 Панель админа", "❌ Отмена", "Назад"
            }

            if text in button_texts and not media_tag:
                if "buttons" in modes:
                    await bot.send_message(
                        chat_id=settings.ADMIN_ID,
                        text=f"🔍 <b>{safe_name}</b> (<code>{tg_id}</code>) нажал кнопку меню: <b>{html.escape(text)}</b>",
                        parse_mode="HTML"
                    )
            elif "messages" in modes:
                msg_content = ""
                if media_tag and text:
                    msg_content = f"{media_tag}\n{html.escape(text)}"
                elif media_tag:
                    msg_content = media_tag
                elif text:
                    msg_content = html.escape(text)

                if msg_content:
                    chat_info = ""
                    if event.chat and event.chat.type in ["group", "supergroup"]:
                        chat_title = html.escape(event.chat.title or "Группа")
                        chat_info = f" [в группе: <i>{chat_title}</i>]"

                    await bot.send_message(
                        chat_id=settings.ADMIN_ID,
                        text=f"🔍 <b>{safe_name}</b> (<code>{tg_id}</code>){chat_info}:\n{msg_content}",
                        parse_mode="HTML"
                    )

        elif hasattr(event, 'data') and event.data is not None:
            # CallbackQuery — нажатие на инлайн-кнопку
            if "inline" in modes:
                cb_data = event.data or ""
                if cb_data.startswith("adm_log_"):
                    return
                label = event.message.text[:40] if event.message and event.message.text else "?"
                await bot.send_message(
                    chat_id=settings.ADMIN_ID,
                    text=f"🔍 <b>{safe_name}</b> (<code>{tg_id}</code>) нажал инлайн-кнопку:\n<code>{html.escape(cb_data)}</code>\n📄 На сообщении: {html.escape(label)}",
                    parse_mode="HTML"
                )
    except Exception as e:
        logger.warning(f"log_user_action error for {tg_id}: {e}")


# ========================
# Клавиатура управления логированием
# ========================

def _build_log_keyboard(target_tg_id: int) -> InlineKeyboardMarkup:
    modes = get_log_modes(target_tg_id)
    active = is_logged(target_tg_id)

    def icon(mode: str) -> str:
        return "✅" if mode in modes else "⬜"

    rows = [
        [
            InlineKeyboardButton(
                text=f"{icon('messages')} Сообщения",
                callback_data=f"adm_log_toggle_messages_{target_tg_id}"
            ),
            InlineKeyboardButton(
                text=f"{icon('buttons')} Кнопки меню",
                callback_data=f"adm_log_toggle_buttons_{target_tg_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text=f"{icon('inline')} Инлайн-кнопки",
                callback_data=f"adm_log_toggle_inline_{target_tg_id}"
            ),
        ],
    ]
    if active:
        rows.append([
            InlineKeyboardButton(
                text="🛑 Остановить лог",
                callback_data=f"adm_log_stop_{target_tg_id}"
            )
        ])
    rows.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_view_students")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ========================
# Handlers — панель логирования
# ========================

@router.callback_query(F.data.startswith("adm_log_open_"))
async def cb_log_open(callback: CallbackQuery, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        await callback.answer("⛔ Только для администраторов", show_alert=True)
        return
    target_tg_id = int(callback.data.replace("adm_log_open_", ""))
    active = is_logged(target_tg_id)
    status = "🔴 активно" if active else "⬜ не ведётся"
    await callback.message.edit_text(
        f"🔍 <b>Логирование пользователя</b> <code>{target_tg_id}</code>\n"
        f"Статус: {status}\n\n"
        "Выберите режимы (можно несколько):",
        reply_markup=_build_log_keyboard(target_tg_id),
        parse_mode="HTML"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_log_toggle_"))
async def cb_log_toggle(callback: CallbackQuery, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        await callback.answer("⛔ Только для администраторов", show_alert=True)
        return

    # Формат: adm_log_toggle_{mode}_{tg_id}
    # mode может содержать '_', поэтому разбираем с конца
    parts = callback.data.replace("adm_log_toggle_", "").rsplit("_", 1)
    if len(parts) != 2:
        await callback.answer("Ошибка данных", show_alert=True)
        return
    mode, tg_id_str = parts
    target_tg_id = int(tg_id_str)

    if mode not in ("messages", "buttons", "inline"):
        await callback.answer("Неизвестный режим", show_alert=True)
        return

    enabled = toggle_mode(target_tg_id, mode)
    mode_labels = {"messages": "Сообщения", "buttons": "Кнопки меню", "inline": "Инлайн-кнопки"}
    await callback.answer(
        f"{'✅ Включено' if enabled else '⬜ Выключено'}: {mode_labels.get(mode, mode)}"
    )

    active = is_logged(target_tg_id)
    status = "🔴 активно" if active else "⬜ не ведётся"
    try:
        await callback.message.edit_text(
            f"🔍 <b>Логирование пользователя</b> <code>{target_tg_id}</code>\n"
            f"Статус: {status}\n\n"
            "Выберите режимы (можно несколько):",
            reply_markup=_build_log_keyboard(target_tg_id),
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("adm_log_stop_"))
async def cb_log_stop(callback: CallbackQuery, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        await callback.answer("⛔ Только для администраторов", show_alert=True)
        return
    target_tg_id = int(callback.data.replace("adm_log_stop_", ""))
    stop_logging(target_tg_id)
    await callback.answer("🛑 Логирование остановлено")
    try:
        await callback.message.edit_text(
            f"🔍 <b>Логирование пользователя</b> <code>{target_tg_id}</code>\n"
            "Статус: ⬜ не ведётся\n\n"
            "Выберите режимы (можно несколько):",
            reply_markup=_build_log_keyboard(target_tg_id),
            parse_mode="HTML"
        )
    except Exception:
        pass


# ========================
# Команда /say — отправить сообщение пользователю
# Доступна ТОЛЬКО в ЛС с ботом и ТОЛЬКО администраторам
# Поддерживает как числовой ID, так и @username
# ========================

@router.message(Command("say"))
async def cmd_say(message: Message, bot: Bot, current_user: User, db_session: AsyncSession):
    # Строго только в личных сообщениях с ботом
    if message.chat.type != "private":
        return

    # Строго только для администраторов
    if not is_admin(current_user, message.from_user.id):
        return

    # Формат: /say @username текст  ИЛИ  /say 123456789 текст
    text = message.text or ""
    parts = text.split(None, 2)
    if len(parts) < 3:
        await message.answer(
            "⚠️ <b>Использование:</b> <code>/say &lt;@username|tg_id&gt; текст</code>\n\n"
            "Примеры:\n"
            "• <code>/say @ivan_smirnov Привет!</code>\n"
            "• <code>/say 111111111 Привет!</code>",
            parse_mode="HTML"
        )
        return

    target_raw = parts[1].strip()
    msg_text = parts[2].strip()

    if not msg_text:
        await message.answer("⚠️ Текст сообщения не может быть пустым.", parse_mode="HTML")
        return

    from backend.db.crud.users import get_user_by_username, get_user_by_tg_id

    target_id = None
    target_display = target_raw

    # Проверяем, передан username (@username или просто текст без цифр) или числовой ID
    if target_raw.startswith("@") or not target_raw.lstrip("-").isdigit():
        uname = target_raw.lstrip("@")
        user = await get_user_by_username(db_session, uname)
        if not user:
            await message.answer(f"❌ Пользователь <b>@{uname}</b> не найден в базе данных бота.", parse_mode="HTML")
            return
        target_id = user.tg_id
        target_display = f"{user.display_name} (@{user.username or uname})"
    else:
        try:
            target_id = int(target_raw)
            user = await get_user_by_tg_id(db_session, target_id)
            if user:
                uname_str = f" (@{user.username})" if user.username else ""
                target_display = f"{user.display_name}{uname_str} (<code>{target_id}</code>)"
            else:
                target_display = f"<code>{target_id}</code>"
        except ValueError:
            await message.answer("⚠️ Неверный формат ID или username.", parse_mode="HTML")
            return

    try:
        # Отправляем пользователю чистый текст (без пометок от кого)
        await bot.send_message(chat_id=target_id, text=msg_text)
        await message.answer(f"✅ Сообщение успешно отправлено {target_display}", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить сообщение: <code>{e}</code>", parse_mode="HTML")

