from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from backend.db.models import User
from backend.bot.keyboards.admin_kb import get_admin_panel_keyboard
from backend.bot.handlers.admin.helpers import is_admin

router = Router(name="admin_menu_router")


@router.message(F.text.in_(["👑 Панель управления", "👑 Панель админа"]))
async def show_admin_panel(message: Message, current_user: User):
    if not is_admin(current_user, message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора.")
        return

    await message.answer(
        "👑 **Панель управления 11 «Б»:**\n\n"
        "Выберите раздел для управления расписанием, ДЗ, звонками, предметами и доступом:",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "admin_menu_back")
async def cb_admin_menu_back(callback: CallbackQuery, state: FSMContext, current_user: User):
    await state.clear()
    if not is_admin(current_user, callback.from_user.id):
        return
    await callback.message.edit_text(
        "👑 **Панель управления 11 «Б»:**\n\n"
        "Выберите нужное действие:",
        reply_markup=get_admin_panel_keyboard(),
        parse_mode="Markdown"
    )
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "admin_cancel")
async def cb_admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.", reply_markup=get_admin_panel_keyboard())
    try:
        await callback.answer()
    except Exception:
        pass


@router.message(F.text.in_(["/test_digest", "/digest"]))
async def cmd_test_digest(message: Message, bot: Bot, current_user: User):
    if not is_admin(current_user, message.from_user.id):
        return
    await message.answer("⏳ Запускаю тестовую рассылку вечернего напоминания в ЛС...")
    from backend.bot.services.notifier import send_evening_digest
    count = await send_evening_digest(bot, force=True)
    await message.answer(f"✅ Персональные напоминания с чек-листом успешно разосланы в ЛС {count} ученикам!")


@router.message(F.text.in_(["/test_canteen", "/canteen"]))
async def cmd_test_canteen(message: Message, bot: Bot, current_user: User):
    if not is_admin(current_user, message.from_user.id):
        return
    await message.answer("⏳ Запускаю тестовую отправку 3 сообщений о столовой в ЛС...")
    from backend.bot.services.canteen import send_canteen_reminder
    count = await send_canteen_reminder(bot, force=True)
    await message.answer(f"✅ Напоминание о столовой (3 сообщения) успешно отправлено {count} пользователям с включённой настройкой!")


@router.message(F.text.in_(["/logs", "/log", "/error_logs"]))
async def cmd_view_logs(message: Message, current_user: User):
    if not is_admin(current_user, message.from_user.id):
        return

    import os
    import html
    log_path = os.path.join("data", "bot.log")
    if not os.path.exists(log_path):
        await message.answer("ℹ️ Файл логов пока пуст или не создан.")
        return

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        last_lines = lines[-35:] if len(lines) > 35 else lines
        text = "".join(last_lines)
        if not text.strip():
            await message.answer("ℹ️ В файле логов пока нет записей.")
            return

        escaped = html.escape(text)
        if len(escaped) > 3500:
            escaped = escaped[-3500:]

        await message.answer(
            f"📋 <b>Последние записи логов бота:</b>\n\n<pre><code>{escaped}</code></pre>",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"⚠️ Ошибка при чтении логов: {e}")

