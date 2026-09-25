"""Admin Telegram handlers for managing Natbirzha economic sabotages and crises."""

from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User
from backend.bot.handlers.admin.helpers import is_admin
from backend.natbirzha.catalogs.sabotages import SABOTAGES_CATALOG, get_sabotage_spec
from backend.natbirzha.services.sabotage_service import SabotageService
from backend.natbirzha.config import get_game_now, normalize_dt

router = Router(name="admin_sabotages_router")


def _format_remaining_time(ends_at: datetime) -> str:
    now = get_game_now()
    diff = ends_at - now
    total_seconds = max(0, int(diff.total_seconds()))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours} ч {minutes} мин"


def _build_sabotages_menu_keyboard(active: bool = False) -> InlineKeyboardMarkup:
    rows = []
    if not active:
        items = list(SABOTAGES_CATALOG.values())
        for i in range(0, len(items), 2):
            row = []
            for spec in items[i:i + 2]:
                text = f"{spec['icon']} {spec['name'][:18]}"
                row.append(InlineKeyboardButton(text=text, callback_data=f"sab_view:{spec['id']}"))
            rows.append(row)
    else:
        rows.append([
            InlineKeyboardButton(text="🛑 Завершить саботаж досрочно", callback_data="sab_abort_confirm")
        ])
    rows.append([
        InlineKeyboardButton(text="🔄 Обновить статус", callback_data="admin_sabotages_menu")
    ])
    rows.append([
        InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_menu_back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("sabotages", "sabotage"))
async def cmd_sabotages(message: Message, current_user: User, db_session: AsyncSession):
    if not is_admin(current_user, message.from_user.id):
        return

    active = await SabotageService.get_active_sabotage(db_session)
    if active:
        ends = normalize_dt(active.ends_at)
        rem_str = _format_remaining_time(ends) if ends else "—"
        spec = get_sabotage_spec(active.sabotage_id) or {}
        text = (
            f"🎭 <b>АКТИВНЫЙ САБОТАЖ В ИГРЕ</b>\n\n"
            f"{spec.get('icon', '⚠️')} <b>«{active.title}»</b>\n"
            f"⏳ Оставшееся время: <b>{rem_str}</b>\n"
            f"📅 Окончание: <code>{active.ends_at.strftime('%d.%m.%Y %H:%M')}</code>\n\n"
            f"📝 <b>Описание:</b> {spec.get('description', '')}\n\n"
            f"<i>Одновременно может быть активен только 1 саботаж. "
            f"Вы можете досрочно нормализовать экономику.</i>"
        )
        await message.answer(text, reply_markup=_build_sabotages_menu_keyboard(active=True), parse_mode="HTML")
    else:
        text = (
            "🎭 <b>Экономические саботажи (НАТБИРЖА)</b>\n\n"
            "Саботаж — это масштабный кризис, временно меняющий рыночные цены, ставки и доходы отраслей.\n"
            "Выберите саботаж для просмотра условий и запуска:"
        )
        await message.answer(text, reply_markup=_build_sabotages_menu_keyboard(active=False), parse_mode="HTML")


@router.callback_query(F.data == "admin_sabotages_menu")
async def cb_sabotages_menu(callback: CallbackQuery, current_user: User, db_session: AsyncSession):
    if not is_admin(current_user, callback.from_user.id):
        return

    active = await SabotageService.get_active_sabotage(db_session)
    if active:
        ends = normalize_dt(active.ends_at)
        rem_str = _format_remaining_time(ends) if ends else "—"
        spec = get_sabotage_spec(active.sabotage_id) or {}
        text = (
            f"🎭 <b>АКТИВНЫЙ САБОТАЖ В ИГРЕ</b>\n\n"
            f"{spec.get('icon', '⚠️')} <b>«{active.title}»</b>\n"
            f"⏳ Оставшееся время: <b>{rem_str}</b>\n"
            f"📅 Окончание: <code>{active.ends_at.strftime('%d.%m.%Y %H:%M')}</code>\n\n"
            f"📝 <b>Описание:</b> {spec.get('description', '')}\n\n"
            f"<i>Одновременно может быть активен только 1 саботаж. "
            f"Вы можете досрочно нормализовать экономику.</i>"
        )
        await callback.message.edit_text(text, reply_markup=_build_sabotages_menu_keyboard(active=True), parse_mode="HTML")
    else:
        text = (
            "🎭 <b>Экономические саботажи (НАТБИРЖА)</b>\n\n"
            "Саботаж — это масштабный кризис, временно меняющий рыночные цены, ставки и доходы отраслей.\n"
            "Выберите саботаж для просмотра условий и запуска:"
        )
        await callback.message.edit_text(text, reply_markup=_build_sabotages_menu_keyboard(active=False), parse_mode="HTML")
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("sab_view:"))
async def cb_sabotage_view(callback: CallbackQuery, current_user: User, db_session: AsyncSession):
    if not is_admin(current_user, callback.from_user.id):
        return

    sab_id = callback.data.split(":", 1)[1]
    spec = get_sabotage_spec(sab_id)
    if not spec:
        await callback.answer("Саботаж не найден.", show_alert=True)
        return

    effects = []
    if spec.get("one_time_stock_shock"):
        effects.append(f"📉 Разовый обвал акций: {int(spec['one_time_stock_shock'] * 100)}%")
    if spec.get("credit_rate_delta"):
        effects.append(f"💳 Ставка кредитов: +{int(spec['credit_rate_delta'] * 100)}%")
    if spec.get("bond_price_mult", 1.0) != 1.0:
        pct = int(round((spec['bond_price_mult'] - 1.0) * 100))
        effects.append(f"📜 Цена гособлигаций: {pct}%")
    if spec.get("block_dividends"):
        effects.append("🚫 Выплаты дивидендов: ЗАМОРОЖЕНЫ")
    if spec.get("block_new_credits"):
        effects.append("🚫 Новые госкредиты: ЗАБЛОКИРОВАНЫ")
    for s, m in (spec.get("income_multipliers") or {}).items():
        pct = int(round((m - 1.0) * 100))
        sign = "+" if pct > 0 else ""
        effects.append(f"🏭 Доходность «{s}»: {sign}{pct}%")
    if spec.get("other_income_mult", 1.0) != 1.0:
        pct = int(round((spec['other_income_mult'] - 1.0) * 100))
        effects.append(f"🏭 Доходность остальных отраслей: {pct}%")
    for r, m in (spec.get("resource_multipliers") or {}).items():
        pct = int(round((m - 1.0) * 100))
        sign = "+" if pct > 0 else ""
        effects.append(f"📦 Цена ресурса «{r}»: {sign}{pct}%")

    effects_text = "\n".join(f"• {e}" for e in effects) if effects else "• Без дополнительных модификаторов"

    text = (
        f"{spec['icon']} <b>«{spec['name']}»</b>\n\n"
        f"⏳ Длительность: <b>{spec['duration_hours']} часов</b>\n"
        f"📝 <b>Описание:</b> {spec['description']}\n\n"
        f"⚡ <b>Эффекты кризиса:</b>\n{effects_text}\n\n"
        f"📢 <i>При запуске всем активным игрокам НАТБИРЖИ будет отправлен государственный вестник.</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚠️ Запустить саботаж", callback_data=f"sab_confirm:{sab_id}")],
        [InlineKeyboardButton(text="⬅️ К списку саботажей", callback_data="admin_sabotages_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("sab_confirm:"))
async def cb_sabotage_confirm(callback: CallbackQuery, current_user: User):
    if not is_admin(current_user, callback.from_user.id):
        return

    sab_id = callback.data.split(":", 1)[1]
    spec = get_sabotage_spec(sab_id)
    if not spec:
        return

    text = (
        f"⚠️ <b>ПОДТВЕРЖДЕНИЕ ЗАПУСКА</b>\n\n"
        f"Вы действительно хотите активировать кризис:\n"
        f"{spec['icon']} <b>«{spec['name']}»</b> на <b>{spec['duration_hours']}ч</b>?\n\n"
        f"Все экономические параметры вступят в силу немедленно, и всем игрокам придёт оповещение."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, запустить кризис!", callback_data=f"sab_start:{sab_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_sabotages_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("sab_start:"))
async def cb_sabotage_start(callback: CallbackQuery, current_user: User, db_session: AsyncSession, bot: Bot):
    if not is_admin(current_user, callback.from_user.id):
        return

    sab_id = callback.data.split(":", 1)[1]
    try:
        result = await SabotageService.start_sabotage(
            db_session,
            sabotage_id=sab_id,
            actor_id=callback.from_user.id,
            bot=bot,
        )
        await db_session.commit()
        await callback.answer("✅ Саботаж успешно запущен!", show_alert=True)
        # Show updated active card
        await cb_sabotages_menu(callback, current_user, db_session)
    except ValueError as exc:
        await callback.answer(f"❌ Ошибка: {exc}", show_alert=True)
    except Exception as exc:
        await callback.answer(f"❌ Внутренняя ошибка: {exc}", show_alert=True)


@router.callback_query(F.data == "sab_abort_confirm")
async def cb_sabotage_abort_confirm(callback: CallbackQuery, current_user: User, db_session: AsyncSession):
    if not is_admin(current_user, callback.from_user.id):
        return

    active = await SabotageService.get_active_sabotage(db_session)
    if not active:
        await callback.answer("Нет активного саботажа.", show_alert=True)
        await cb_sabotages_menu(callback, current_user, db_session)
        return

    text = (
        f"🛑 <b>ДОСРОЧНОЕ ЗАВЕРШЕНИЕ САБОТАЖА</b>\n\n"
        f"Вы хотите досрочно остановить кризис <b>«{active.title}»</b>?\n"
        f"Рыночные параметры, цены ресурсов и доходы отраслей будут немедленно возвращены в штатный режим. "
        f"Игрокам будет отправлено оповещение о преодолении кризиса."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Да, завершить досрочно", callback_data="sab_abort_do")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_sabotages_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "sab_abort_do")
async def cb_sabotage_abort_do(callback: CallbackQuery, current_user: User, db_session: AsyncSession, bot: Bot):
    if not is_admin(current_user, callback.from_user.id):
        return

    try:
        await SabotageService.stop_sabotage(
            db_session,
            actor_id=callback.from_user.id,
            reason="ADMIN_MANUAL_STOP",
            bot=bot,
        )
        await db_session.commit()
        await callback.answer("✅ Саботаж остановлен! Экономика нормализована.", show_alert=True)
        await cb_sabotages_menu(callback, current_user, db_session)
    except Exception as exc:
        await callback.answer(f"❌ Ошибка: {exc}", show_alert=True)


__all__ = ["router"]
