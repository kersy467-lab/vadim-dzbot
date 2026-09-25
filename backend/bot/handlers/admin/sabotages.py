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


def _build_sabotages_menu_keyboard(
    actives: list = None, show_catalog: bool = False
) -> InlineKeyboardMarkup:
    actives = actives or []
    rows = []
    if not actives or show_catalog:
        active_ids = {getattr(a, "sabotage_id", "") for a in actives}
        items = [s for s in SABOTAGES_CATALOG.values() if s["id"] not in active_ids]
        for i in range(0, len(items), 2):
            row = []
            for spec in items[i:i + 2]:
                text = f"{spec['icon']} {spec['name'][:18]}"
                row.append(InlineKeyboardButton(text=text, callback_data=f"sab_view:{spec['id']}"))
            rows.append(row)
        if actives:
            rows.append([
                InlineKeyboardButton(text="⬅️ К активным саботажам", callback_data="admin_sabotages_menu")
            ])
    else:
        for a in actives:
            title = getattr(a, "title", "Саботаж")
            sab_id = getattr(a, "sabotage_id", "")
            rows.append([
                InlineKeyboardButton(
                    text=f"🛑 Завершить: {title[:20]}",
                    callback_data=f"sab_abort_confirm:{sab_id}"
                )
            ])
        if len(actives) < SabotageService.MAX_ACTIVE_SABOTAGES:
            rows.append([
                InlineKeyboardButton(
                    text=f"➕ Запустить 2-й саботаж ({len(actives)}/{SabotageService.MAX_ACTIVE_SABOTAGES})",
                    callback_data="sab_catalog_open"
                )
            ])
        if len(actives) > 1:
            rows.append([
                InlineKeyboardButton(
                    text="🛑 Завершить ВСЕ саботажи",
                    callback_data="sab_abort_all_confirm"
                )
            ])

    rows.append([
        InlineKeyboardButton(text="🔄 Обновить статус", callback_data="admin_sabotages_menu")
    ])
    rows.append([
        InlineKeyboardButton(text="⬅️ Назад в админку", callback_data="admin_menu_back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _render_actives_text(actives: list) -> str:
    lines = [
        f"🎭 <b>АКТИВНЫЕ САБОТАЖИ В ИГРЕ ({len(actives)}/{SabotageService.MAX_ACTIVE_SABOTAGES})</b>\n"
    ]
    for idx, a in enumerate(actives, 1):
        ends = normalize_dt(a.ends_at)
        rem_str = _format_remaining_time(ends) if ends else "—"
        spec = get_sabotage_spec(a.sabotage_id) or {}
        lines.append(
            f"<b>{idx}. {spec.get('icon', '⚠️')} «{a.title}»</b>\n"
            f"⏳ Оставшееся время: <b>{rem_str}</b>\n"
            f"📅 Окончание: <code>{a.ends_at.strftime('%d.%m.%Y %H:%M')}</code>\n"
            f"📝 <i>{spec.get('description', '')}</i>\n"
        )
    if len(actives) < SabotageService.MAX_ACTIVE_SABOTAGES:
        lines.append(
            f"<i>Разрешено запустить ещё 1 саботаж одновременно. "
            f"Их эффекты и модификаторы суммируются/перемножаются.</i>"
        )
    else:
        lines.append(
            f"<i>Достигнут максимум активных саботажей (2/2). "
            f"Для запуска другого завершите один из действующих.</i>"
        )
    return "\n".join(lines)


def _build_sabotage_view_card(spec: dict, actives: list) -> tuple[str, InlineKeyboardMarkup]:
    is_active_now = any(a.sabotage_id == spec["id"] for a in actives)
    is_limit_reached = len(actives) >= SabotageService.MAX_ACTIVE_SABOTAGES and not is_active_now

    effects = []
    if spec.get("one_time_stock_shock"):
        pct = int(round(spec['one_time_stock_shock'] * 100))
        sign = "+" if pct > 0 else ""
        effects.append(f"📊 Разовый шок акций: {sign}{pct}%")
    if spec.get("credit_rate_delta"):
        pct = int(round(spec['credit_rate_delta'] * 100))
        sign = "+" if pct > 0 else ""
        effects.append(f"💳 Ставка кредитов: {sign}{pct}%")
    if spec.get("tax_rate_delta"):
        pct = int(round(spec['tax_rate_delta'] * 100))
        sign = "+" if pct > 0 else ""
        new_rate = 13 + pct
        effects.append(f"🧾 Налог на прибыль: <b>{new_rate}%</b> ({sign}{pct}% к базовым 13%)")
    if spec.get("bond_price_mult", 1.0) != 1.0:
        pct = int(round((spec['bond_price_mult'] - 1.0) * 100))
        sign = "+" if pct > 0 else ""
        effects.append(f"📜 Цена гособлигаций: {sign}{pct}%")
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
        sign = "+" if pct > 0 else ""
        effects.append(f"🏭 Доходность остальных отраслей: {sign}{pct}%")
    for r, m in (spec.get("resource_multipliers") or {}).items():
        pct = int(round((m - 1.0) * 100))
        sign = "+" if pct > 0 else ""
        effects.append(f"📦 Цена ресурса «{r}»: {sign}{pct}%")

    effects_text = "\n".join(f"• {e}" for e in effects) if effects else "• Без дополнительных модификаторов"

    status_note = ""
    if is_active_now:
        status_note = "🔴 <b>Этот саботаж действует прямо сейчас!</b>\n\n"
    elif is_limit_reached:
        status_note = "⚠️ <b>Уже активны 2 саботажа одновременно. Дождитесь окончания или завершите один.</b>\n\n"

    text = (
        f"{spec['icon']} <b>«{spec['name']}»</b>\n\n"
        f"{status_note}"
        f"⏳ Длительность: <b>{spec['duration_hours']} часов</b>\n"
        f"📝 <b>Описание:</b> {spec['description']}\n\n"
        f"⚡ <b>Эффекты:</b>\n{effects_text}\n\n"
        f"📢 <i>При запуске всем активным игрокам НАТБИРЖИ будет отправлен государственный вестник.</i>"
    )

    kb_rows = []
    sab_id = spec["id"]
    if not is_active_now and not is_limit_reached:
        btn_text = "⚠️ Запустить саботаж" if not actives else "⚠️ Запустить как 2-й саботаж"
        kb_rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"sab_confirm:{sab_id}")])
    if actives:
        kb_rows.append([InlineKeyboardButton(text="⬅️ К каталогу саботажей", callback_data="sab_catalog_open")])
        kb_rows.append([InlineKeyboardButton(text="⬅️ К активным саботажам", callback_data="admin_sabotages_menu")])
    else:
        kb_rows.append([InlineKeyboardButton(text="⬅️ К списку саботажей", callback_data="admin_sabotages_menu")])

    return text, InlineKeyboardMarkup(inline_keyboard=kb_rows)


@router.message(Command("sabotages", "sabotage"))
async def cmd_sabotages(message: Message, current_user: User, db_session: AsyncSession):
    if not is_admin(current_user, message.from_user.id):
        return

    actives = await SabotageService.get_active_sabotages(db_session)

    # Check if a specific sabotage ID or name was requested as argument
    raw_args = (message.text or "").strip().split(maxsplit=1)
    if len(raw_args) > 1 and raw_args[1].strip():
        query = raw_args[1].strip().lower()
        matched = None
        for s_id, s_spec in SABOTAGES_CATALOG.items():
            if s_id.lower() == query or s_spec["name"].lower() == query or query in s_id.lower() or query in s_spec["name"].lower():
                matched = s_spec
                break
        if matched:
            text, kb = _build_sabotage_view_card(matched, actives)
            await message.answer(text, reply_markup=kb, parse_mode="HTML")
            return

    if actives:
        text = _render_actives_text(actives)
        await message.answer(text, reply_markup=_build_sabotages_menu_keyboard(actives=actives), parse_mode="HTML")
    else:
        text = (
            "🎭 <b>Экономические саботажи (НАТБИРЖА)</b>\n\n"
            "Саботаж — это масштабный кризис, временно меняющий рыночные цены, ставки и доходы отраслей.\n"
            "Сейчас активно: <b>0/2</b>. Выберите саботаж для просмотра условий и запуска:"
        )
        await message.answer(text, reply_markup=_build_sabotages_menu_keyboard(actives=[]), parse_mode="HTML")


@router.callback_query(F.data == "admin_sabotages_menu")
async def cb_sabotages_menu(callback: CallbackQuery, current_user: User, db_session: AsyncSession):
    if not is_admin(current_user, callback.from_user.id):
        return

    actives = await SabotageService.get_active_sabotages(db_session)
    if actives:
        text = _render_actives_text(actives)
        await callback.message.edit_text(text, reply_markup=_build_sabotages_menu_keyboard(actives=actives), parse_mode="HTML")
    else:
        text = (
            "🎭 <b>Экономические саботажи (НАТБИРЖА)</b>\n\n"
            "Саботаж — это масштабный кризис, временно меняющий рыночные цены, ставки и доходы отраслей.\n"
            "Сейчас активно: <b>0/2</b>. Выберите саботаж для просмотра условий и запуска:"
        )
        await callback.message.edit_text(text, reply_markup=_build_sabotages_menu_keyboard(actives=[]), parse_mode="HTML")
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "sab_catalog_open")
async def cb_sabotage_catalog_open(callback: CallbackQuery, current_user: User, db_session: AsyncSession):
    if not is_admin(current_user, callback.from_user.id):
        return

    actives = await SabotageService.get_active_sabotages(db_session)
    text = (
        f"🎭 <b>Каталог саботажей (Активно: {len(actives)}/{SabotageService.MAX_ACTIVE_SABOTAGES})</b>\n\n"
        f"Выберите саботаж для запуска:"
    )
    await callback.message.edit_text(
        text,
        reply_markup=_build_sabotages_menu_keyboard(actives=actives, show_catalog=True),
        parse_mode="HTML"
    )
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

    actives = await SabotageService.get_active_sabotages(db_session)
    text, kb = _build_sabotage_view_card(spec, actives)
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
        f"Все экономические параметры вступят в силу немедленно, и игрокам придёт оповещение."
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
        await SabotageService.start_sabotage(
            db_session,
            sabotage_id=sab_id,
            actor_id=callback.from_user.id,
            bot=bot,
        )
        await db_session.commit()
        await callback.answer("✅ Саботаж успешно запущен!", show_alert=True)
        await cb_sabotages_menu(callback, current_user, db_session)
    except ValueError as exc:
        await callback.answer(f"❌ Ошибка: {exc}", show_alert=True)
    except Exception as exc:
        await callback.answer(f"❌ Внутренняя ошибка: {exc}", show_alert=True)


@router.callback_query(F.data.startswith("sab_abort_confirm:"))
async def cb_sabotage_abort_confirm(callback: CallbackQuery, current_user: User, db_session: AsyncSession):
    if not is_admin(current_user, callback.from_user.id):
        return

    sab_id = callback.data.split(":", 1)[1]
    actives = await SabotageService.get_active_sabotages(db_session)
    target = next((a for a in actives if a.sabotage_id == sab_id), None)
    if not target:
        await callback.answer("Саботаж не активен.", show_alert=True)
        await cb_sabotages_menu(callback, current_user, db_session)
        return

    text = (
        f"🛑 <b>ДОСРОЧНОЕ ЗАВЕРШЕНИЕ САБОТАЖА</b>\n\n"
        f"Вы хотите досрочно остановить кризис <b>«{target.title}»</b>?\n"
        f"Его модификаторы цен и доходов будут немедленно сняты, "
        f"а игрокам будет отправлено оповещение."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Да, завершить досрочно", callback_data=f"sab_abort_do:{sab_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_sabotages_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data == "sab_abort_all_confirm")
async def cb_sabotage_abort_all_confirm(callback: CallbackQuery, current_user: User, db_session: AsyncSession):
    if not is_admin(current_user, callback.from_user.id):
        return

    actives = await SabotageService.get_active_sabotages(db_session)
    if not actives:
        await callback.answer("Нет активных саботажей.", show_alert=True)
        await cb_sabotages_menu(callback, current_user, db_session)
        return

    names = ", ".join(f"«{a.title}»" for a in actives)
    text = (
        f"🛑 <b>ЗАВЕРШЕНИЕ ВСЕХ САБОТАЖЕЙ</b>\n\n"
        f"Вы действительно хотите досрочно остановить ВСЕ действующие саботажи ({names})?\n"
        f"Все экономические параметры вернутся в базовое состояние."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛑 Да, остановить все!", callback_data="sab_abort_all_do")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_sabotages_menu")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    try:
        await callback.answer()
    except Exception:
        pass


@router.callback_query(F.data.startswith("sab_abort_do:"))
async def cb_sabotage_abort_do(callback: CallbackQuery, current_user: User, db_session: AsyncSession, bot: Bot):
    if not is_admin(current_user, callback.from_user.id):
        return

    sab_id = callback.data.split(":", 1)[1]
    try:
        await SabotageService.stop_sabotage(
            db_session,
            actor_id=callback.from_user.id,
            sabotage_id=sab_id,
            reason="ADMIN_MANUAL_STOP",
            bot=bot,
        )
        await db_session.commit()
        await callback.answer("✅ Саботаж остановлен!", show_alert=True)
        await cb_sabotages_menu(callback, current_user, db_session)
    except Exception as exc:
        await callback.answer(f"❌ Ошибка: {exc}", show_alert=True)


@router.callback_query(F.data == "sab_abort_all_do")
async def cb_sabotage_abort_all_do(callback: CallbackQuery, current_user: User, db_session: AsyncSession, bot: Bot):
    if not is_admin(current_user, callback.from_user.id):
        return

    try:
        actives = await SabotageService.get_active_sabotages(db_session)
        for a in list(actives):
            await SabotageService.stop_sabotage(
                db_session,
                actor_id=callback.from_user.id,
                sabotage_id=a.sabotage_id,
                reason="ADMIN_MANUAL_STOP_ALL",
                bot=bot,
            )
        await db_session.commit()
        await callback.answer("✅ Все саботажи остановлены!", show_alert=True)
        await cb_sabotages_menu(callback, current_user, db_session)
    except Exception as exc:
        await callback.answer(f"❌ Ошибка: {exc}", show_alert=True)


__all__ = ["router"]
