"""Service for broadcasting public Natbirzha game events to Telegram chat."""

import asyncio
import html
import logging
from typing import Any, Dict, Optional

from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.inventory import CANONICAL_ITEMS

logger = logging.getLogger(__name__)

SPECIALIZATION_LABELS: Dict[str, str] = {
    "energy": "Энергетика",
    "metallurgy": "Металлургия",
    "oil_gas": "Нефть и газ",
    "chemistry": "Химия и полимеры",
    "mining": "Горнодобывающая промышленность",
    "logging": "Лесопромышленность",
    "agriculture": "Сельское хозяйство и пищепром",
    "machinery": "Тяжелое машиностроение",
    "electronics": "Электроника и IT",
    "defense": "Военно-промышленный комплекс",
}


class EventBroadcaster:
    """Dispatches public game event notifications to the designated Telegram group."""

    _cached_chat_id: Optional[int] = None

    @classmethod
    def get_configured_chat_id(cls) -> int:
        configured = getattr(nat_settings, "EVENTS_CHAT_ID", -1004491945174)
        try:
            val = int(configured)
            return val if val != 0 else -1004491945174
        except Exception:
            return -1004491945174

    @classmethod
    def get_chat_id(cls) -> int:
        if cls._cached_chat_id is not None:
            return cls._cached_chat_id
        return cls.get_configured_chat_id()

    @classmethod
    def set_cached_chat_id(cls, chat_id: int) -> None:
        cls._cached_chat_id = chat_id

    @staticmethod
    def _get_bot() -> Optional[Any]:
        try:
            from backend.bot.bot import get_current_bot
            b = get_current_bot()
            if b is not None:
                return b
            from backend.bot.bot import create_bot_and_dispatcher
            b, _ = create_bot_and_dispatcher()
            return b
        except Exception as exc:
            logger.warning("Error resolving bot for EventBroadcaster: %s", exc)
            return None

    @staticmethod
    async def _get_approved_group_ids() -> list[int]:
        try:
            from backend.db.session import async_session_factory
            from backend.db.models import GroupChat
            from sqlalchemy import select
            async with async_session_factory() as session:
                res = await session.execute(
                    select(GroupChat.chat_id).where(
                        GroupChat.role == "approved",
                        GroupChat.notifications_enabled == True
                    )
                )
                return [int(row[0]) for row in res.fetchall()]
        except Exception as exc:
            logger.warning("Could not query approved groups for EventBroadcaster: %s", exc)
            return []

    @classmethod
    async def send_message(cls, text: str) -> bool:
        """
        Sends an HTML formatted message to the events group with automatic
        fallback between configured ID, known target IDs, and approved DB groups.
        """
        try:
            # Short yield to allow surrounding database commit to conclude
            await asyncio.sleep(0.05)
            bot = cls._get_bot()
            if not bot:
                logger.warning("Bot instance not available, skipping event broadcast: %s", text[:60])
                return False

            candidates: list[int] = []
            if cls._cached_chat_id is not None:
                candidates.append(cls._cached_chat_id)

            cfg_id = cls.get_configured_chat_id()
            if cfg_id not in candidates:
                candidates.append(cfg_id)

            for known_id in (-1004491945174, -4491945174, -5495179388, -1005495179388):
                if known_id not in candidates:
                    candidates.append(known_id)

            for cid in list(candidates):
                alt = cls._get_alternative_chat_id(cid)
                if alt and alt not in candidates:
                    candidates.append(alt)

            for target_id in candidates:
                if await cls._try_send(bot, target_id, text):
                    cls._cached_chat_id = target_id
                    return True

            # If none of the static targets worked, try approved groups from DB
            db_chat_ids = await cls._get_approved_group_ids()
            for db_id in db_chat_ids:
                if db_id not in candidates:
                    if await cls._try_send(bot, db_id, text):
                        cls._cached_chat_id = db_id
                        return True

            logger.warning("Event broadcast failed for all target chat candidates")
            return False
        except Exception as exc:
            logger.warning("Unexpected error during event broadcast: %s", exc)
            return False

    @classmethod
    async def _try_send(cls, bot: Any, target_chat_id: int, text: str) -> bool:
        try:
            await bot.send_message(chat_id=target_chat_id, text=text, parse_mode="HTML")
            logger.info("Successfully delivered event broadcast to chat %s", target_chat_id)
            return True
        except Exception as exc:
            logger.warning("Failed sending event broadcast to chat %s: %s", target_chat_id, exc)
            return False

    @staticmethod
    def _get_alternative_chat_id(chat_id: int) -> Optional[int]:
        s = str(chat_id)
        if s.startswith("-100"):
            remainder = s[4:]
            if remainder.isdigit():
                return -int(remainder)
        elif s.startswith("-"):
            remainder = s[1:]
            if remainder.isdigit():
                return int(f"-100{remainder}")
        return None

    # -------------------------------------------------------------------------
    # 1. Market Orders (Товарная биржа)
    # -------------------------------------------------------------------------
    @classmethod
    async def broadcast_market_order(
        cls,
        company_name: str,
        ticker: str,
        order_type: str,
        item_id: str,
        quantity: float,
        price: float,
    ) -> None:
        """Broadcast new buy or sell order placed on the commodity exchange."""
        try:
            item_meta = CANONICAL_ITEMS.get(item_id, {})
            item_name = item_meta.get("name", item_id)
            unit = item_meta.get("unit", "ед.")
            total_cost = round(price * quantity, 2)
            c_name = html.escape(str(company_name or "Компания"))
            c_tick = html.escape(str(ticker or "---"))

            if str(order_type).upper() == "BUY":
                title = "🛒 <b>Товарная биржа: Запрос на покупку</b>"
            else:
                title = "🏷 <b>Товарная биржа: Заявка на продажу</b>"

            text = (
                f"{title}\n\n"
                f"🏢 <b>Компания:</b> {c_name} (<code>{c_tick}</code>)\n"
                f"📦 <b>Товар:</b> {item_name}\n"
                f"📊 <b>Объем:</b> {quantity:,.2f} {unit}\n"
                f"💰 <b>Цена:</b> {price:,.2f} ₽/{unit}\n"
                f"💵 <b>Сумма заявки:</b> {total_cost:,.2f} ₽"
            )
            await cls.send_message(text)
        except Exception as exc:
            logger.warning("Error broadcasting market order: %s", exc)

    # -------------------------------------------------------------------------
    # 2. Sabotages (Саботажи)
    # -------------------------------------------------------------------------
    @classmethod
    async def broadcast_sabotage_start(cls, spec: Dict[str, Any]) -> None:
        """Broadcast activation of a state sabotage/crisis."""
        try:
            icon = spec.get("icon", "🎭")
            title = html.escape(str(spec.get("name", "Саботаж")))
            headline = html.escape(str(spec.get("news_headline", "Чрезвычайное положение")))
            body = html.escape(str(spec.get("news_body", spec.get("description", ""))))
            duration = spec.get("duration_hours", 24)

            text = (
                f"🎭 <b>НАТБИРЖА: ГОСУДАРСТВЕННЫЙ САБОТАЖ</b>\n\n"
                f"{icon} <b>{title}</b>\n\n"
                f"📰 <b>{headline}</b>\n\n"
                f"{body}\n\n"
                f"⏱ <b>Длительность:</b> {duration} ч.\n"
                f"<i>Следите за изменениями котировок и тарифов в игре!</i>"
            )
            await cls.send_message(text)
        except Exception as exc:
            logger.warning("Error broadcasting sabotage start: %s", exc)

    @classmethod
    async def broadcast_sabotage_end(
        cls,
        title: str,
        reason: str = "",
        headline: Optional[str] = None,
        body: Optional[str] = None,
    ) -> None:
        """Broadcast resolution or termination of an active sabotage."""
        try:
            s_title = html.escape(str(title or "Саботаж"))
            h_line = html.escape(
                headline or ("Кризис завершен досрочно" if reason == "CREATOR_ABORT" else "Кризис подошел к концу")
            )
            b_text = html.escape(
                body or "Государство нормализовало ситуацию. Экономические показатели возвращаются в штатный режим."
            )

            text = (
                f"✅ <b>НАТБИРЖА: ЗАВЕРШЕНИЕ САБОТАЖА</b>\n\n"
                f"<b>{s_title}</b>\n\n"
                f"📰 <b>{h_line}</b>\n\n"
                f"{b_text}"
            )
            await cls.send_message(text)
        except Exception as exc:
            logger.warning("Error broadcasting sabotage end: %s", exc)

    # -------------------------------------------------------------------------
    # 3. State Warnings (Предупреждения от государства)
    # -------------------------------------------------------------------------
    @classmethod
    async def broadcast_creator_warning(
        cls,
        company_name: str,
        ticker: str,
        reason: str,
        owner_tag: Optional[str] = None,
    ) -> bool:
        """Broadcast state warning issued to a company with owner tag."""
        try:
            c_name = html.escape(str(company_name or "Компания"))
            c_tick = html.escape(str(ticker or "---"))
            r_text = html.escape(str(reason or "Нарушение рыночных правил"))

            owner_line = f"👤 <b>Владелец:</b> {owner_tag}\n" if owner_tag else ""

            text = (
                f"⚠️ <b>ГОСУДАРСТВЕННОЕ ПРЕДУПРЕЖДЕНИЕ</b>\n\n"
                f"🏢 <b>Компания:</b> {c_name} (<code>{c_tick}</code>)\n"
                f"{owner_line}"
                f"🧱 <b>Причина:</b> {r_text}\n\n"
                f"<i>Предупреждение зафиксировано государственным регулятором. "
                f"Повторные нарушения могут повлечь санкции и принудительную ликвидацию.</i>"
            )
            return await cls.send_message(text)
        except Exception as exc:
            logger.warning("Error broadcasting creator warning: %s", exc)
            return False

    @classmethod
    async def broadcast_state_announcement(
        cls,
        message: str,
        owner_tag: Optional[str] = None,
        company_name: Optional[str] = None,
        ticker: Optional[str] = None,
    ) -> bool:
        """Broadcast an official state announcement into the group chat."""
        try:
            body = html.escape(str(message or "")).strip()
            lines = ["🏛 <b>ГОСУДАРСТВЕННОЕ ОБЪЯВЛЕНИЕ</b>\n"]
            if company_name:
                c_name = html.escape(str(company_name))
                c_tick = html.escape(str(ticker or "---"))
                lines.append(f"🏢 <b>Компания:</b> {c_name} (<code>{c_tick}</code>)")
            if owner_tag:
                lines.append(f"👤 <b>Адресат:</b> {owner_tag}")

            lines.append(f"\n📢 {body}\n")
            lines.append("<i>— Государственный Регулятор</i>")

            text = "\n".join(lines)
            return await cls.send_message(text)
        except Exception as exc:
            logger.warning("Error broadcasting state announcement: %s", exc)
            return False

    # -------------------------------------------------------------------------
    # 4. State Bonds (Выпуск облигаций)
    # -------------------------------------------------------------------------
    @classmethod
    async def broadcast_bond_issued(
        cls,
        title: str,
        volume: int,
        face_value: float,
        coupon_rate: float,
        maturity_days: int,
        purpose: str,
    ) -> None:
        """Broadcast issuance of state treasury bonds."""
        try:
            b_title = html.escape(str(title or "Гособлигации"))
            b_purp = html.escape(str(purpose or "Финансирование государственных программ"))

            text = (
                f"📜 <b>ВЫПУСК ГОСУДАРСТВЕННЫХ ОБЛИГАЦИЙ</b>\n\n"
                f"🏛 <b>Выпуск:</b> {b_title}\n"
                f"📦 <b>Объем эмиссии:</b> {volume:,} шт.\n"
                f"💵 <b>Номинал:</b> {face_value:,.2f} ₽\n"
                f"📈 <b>Купонная ставка:</b> {coupon_rate:g}% в день\n"
                f"⏳ <b>Срок погашения:</b> {maturity_days} дн.\n"
                f"🎯 <b>Цель займа:</b> {b_purp}\n\n"
                f"<i>Облигации доступны к покупке в государственном реестре.</i>"
            )
            await cls.send_message(text)
        except Exception as exc:
            logger.warning("Error broadcasting bond issuance: %s", exc)

    # -------------------------------------------------------------------------
    # 5. Bankruptcies & Defaults (Банкротства)
    # -------------------------------------------------------------------------
    @classmethod
    async def broadcast_bankruptcy(
        cls,
        company_name: str,
        ticker: str,
        reason: str,
        details: str = "",
    ) -> None:
        """Broadcast corporate bankruptcy, liquidation, or restructuring filing."""
        try:
            c_name = html.escape(str(company_name or "Компания"))
            c_tick = html.escape(str(ticker or "---"))
            r_text = html.escape(str(reason or "Банкротство"))
            d_text = html.escape(str(details or ""))

            det_block = f"\n📋 <b>Подробности:</b> {d_text}" if d_text else ""
            text = (
                f"🚨 <b>БАНКРОТСТВО КОМПАНИИ</b>\n\n"
                f"🏢 <b>Компания:</b> {c_name} (<code>{c_tick}</code>)\n"
                f"⚖️ <b>Статус:</b> {r_text}"
                f"{det_block}\n\n"
                f"<i>Активы переданы в конкурсную массу/государственный фонд.</i>"
            )
            await cls.send_message(text)
        except Exception as exc:
            logger.warning("Error broadcasting bankruptcy: %s", exc)

    @classmethod
    async def broadcast_bond_default(cls, title: str, details: str = "") -> None:
        """Broadcast default on state bonds."""
        try:
            b_title = html.escape(str(title or "Облигации"))
            d_text = html.escape(str(details or "Объявлен дефолт по выпуску."))

            text = (
                f"🚨 <b>ДЕФОЛТ ПО ОБЛИГАЦИЯМ</b>\n\n"
                f"🏛 <b>Выпуск:</b> {b_title}\n"
                f"⚖️ <b>Статус:</b> Объявлен дефолт\n"
                f"📋 <b>Подробности:</b> {d_text}"
            )
            await cls.send_message(text)
        except Exception as exc:
            logger.warning("Error broadcasting bond default: %s", exc)

    # -------------------------------------------------------------------------
    # 6. Stocks & IPO (Выход новых акций на биржу)
    # -------------------------------------------------------------------------
    @classmethod
    async def broadcast_ipo(
        cls,
        company_name: str,
        ticker: str,
        specialization: Optional[str],
        total_shares: int,
        float_shares: int,
        sale_pct: float,
        share_price: float,
        valuation: float,
        dividend_rate_pct: float,
    ) -> None:
        """Broadcast company initial public offering (IPO) on stock exchange."""
        try:
            c_name = html.escape(str(company_name or "Компания"))
            c_tick = html.escape(str(ticker or "---"))
            spec_name = SPECIALIZATION_LABELS.get(str(specialization or "").lower(), specialization or "Общий сектор")
            spec_name = html.escape(str(spec_name))

            text = (
                f"🔔 <b>НОВЫЙ ВЫХОД НА БИРЖУ (IPO)</b>\n\n"
                f"🏢 <b>Компания:</b> {c_name}\n"
                f"🏷 <b>Тикер:</b> ${c_tick}\n"
                f"🏭 <b>Отрасль:</b> {spec_name}\n"
                f"📊 <b>Всего акций:</b> {total_shares:,} шт.\n"
                f"🌐 <b>В свободном обращении (Float):</b> {float_shares:,} шт. ({sale_pct:g}%)\n"
                f"💰 <b>Цена размещения:</b> {share_price:,.2f} ₽\n"
                f"💎 <b>Оценка компании:</b> {valuation:,.2f} ₽\n"
                f"📈 <b>Дивидендная доходность:</b> {dividend_rate_pct:g}%\n\n"
                f"<i>Акции доступны для торговли в разделе «Фондовая биржа»!</i>"
            )
            await cls.send_message(text)
        except Exception as exc:
            logger.warning("Error broadcasting IPO: %s", exc)

    @classmethod
    async def broadcast_state_share_issued(
        cls,
        title: str,
        purpose: str,
        volume: int,
        issue_price: float,
        dividend_rate_pct: float,
    ) -> None:
        """Broadcast issuance of state enterprise shares."""
        try:
            s_title = html.escape(str(title or "Госакции"))
            s_purp = html.escape(str(purpose or "Развитие государственной инфраструктуры"))

            text = (
                f"🏛 <b>ВЫПУСК ГОСУДАРСТВЕННЫХ АКЦИЙ</b>\n\n"
                f"🏷 <b>Выпуск:</b> {s_title}\n"
                f"📦 <b>Объем эмиссии:</b> {volume:,} шт.\n"
                f"💰 <b>Цена размещения:</b> {issue_price:,.2f} ₽\n"
                f"📈 <b>Дивидендная ставка:</b> {dividend_rate_pct:g}%\n"
                f"🎯 <b>Назначение:</b> {s_purp}\n\n"
                f"<i>Инвестируйте в государственные предприятия через раздел «Государство»!</i>"
            )
            await cls.send_message(text)
        except Exception as exc:
            logger.warning("Error broadcasting state share issuance: %s", exc)


__all__ = ["EventBroadcaster"]
