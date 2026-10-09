"""One-time delivery of the NATBIRZHA 1.5 release notes to players."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import ClassSetting, User
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.player_registry_service import PlayerRegistryService


RELEASE_KEY = "natbirzha_release_1_5_delivery"
RELEASE_MESSAGE = """🚀 <b>НАТБИРЖА 1.5 — экономика, которая держит удар</b>

За последнюю неделю биржа прошла длинный путь: сначала научилась быстрее открывать нужные разделы, потом получила новый облик, а теперь — более живую экономику и новый путь развития компаний.

<b>Глава I. Биржа перестала заставлять ждать</b>
Переработали загрузку разделов и сократили лишние запросы. Данные тяжёлых вкладок подгружаются по необходимости, поэтому рынку, прокачке, рейтингу и другим экранам требуется меньше лишней работы.

<b>Глава II. Новый облик</b>
НАТБИРЖА получила светлую премиальную тему: тёплый айвори, шалфейный и изумрудный оттенки, золотые акценты и собственные SVG-иконки. Обновили основные экраны и навигацию. Отдельно поправили контраст текста на зелёных плашках.

<b>Глава III. Деньги государства снова участвуют в игре</b>
В казне теперь резерв в 10 триллионов cash. Покупка у NPC перечисляет деньги в казну, продажа NPC оплачивается из неё, а покупать у NPC ресурсы можно без прежних лимитов. Если резерв опускается ниже 1 триллиона, включается фискальный режим: налог становится 30%, NPC продаёт дороже и выкупает дешевле. Государство также может включить экспорт: раз в 15 минут продаётся часть реально накопленных ресурсов, и казна получает за них деньги.

Лимит выплат при продаже NPC оставлен только для воды и электроэнергии: до 300 000 cash в сутки на каждую компанию по каждому из этих ресурсов. В обычном режиме электроэнергия у NPC стоит 12,5 cash за МВт·ч.

<b>Глава IV. Помощь и мастерство</b>
Попросить помощь теперь можно на любом уровне компании. Игроки могут добровольно передать cash или ресурсы; выдача проходит с подтверждением и учитывается в истории.

Каждый ранг мастерства даёт <b>+1% к выпуску товаров</b>. Дополнительный расход сырья за этот бонус не начисляется.

<b>Глава V. Перерождение — новый круг, а не конец истории</b>
Подготовку к перерождению упростили и вынесли в более заметный интерфейс. Перед сбросом можно объявить о нём игрокам. Акции и права на дивиденды сохраняются, котировка начинает новый путь с 1% прежней цены и продолжает торговаться через обычную биржу. Продажа облигаций больше не обязательна.

Перерождений пока не больше десяти. Каждое умножает выпуск на 1,25, поэтому бонусы нарастают сложным процентом: первое перерождение даёт 125% от базы, второе — 156,25%, третье — 195,31%. PVC-прокачка отрасли применяется поверх этого множителя. После перерождения открывается новая ступень: для каждой отрасли подготовлена цепочка из десяти новых предприятий.

<b>Глава VI. Исправления рынка и интерфейса</b>
Исправили отображение купонного дохода по облигациям. Обновили экраны биржи, акций, помощи, предприятий и военной вкладки; переработали карточки, иконки, заголовки и состояния загрузки. Бонусы мастерства и перерождения показаны отдельно от расхода ресурсов.

<b>Глава VII. Если компания обанкротилась</b>
Теперь игрок увидит отдельный полноэкранный выбор: продолжить с уже списанным имуществом или начать заново с <b>+100 000 cash</b>. При банкротстве открытые кредиты автоматически списываются, а заявки на кредит отменяются. Баланс Pivocoins переносится на новую компанию.

Удачной игры — и пусть в этот раз казна выдержит."""
BONUS_MESSAGE = "🎁 Всем выдали в честь обновления 2 000 Пивокоинов (PVC)."


def _decode_state(value: str | None) -> dict[str, Any]:
    try:
        decoded = json.loads(value or "{}")
    except (TypeError, ValueError):
        decoded = {}
    return decoded if isinstance(decoded, dict) else {}


async def _persist_state(session_factory, state: dict[str, Any], owner: str) -> bool:
    async with session_factory() as session:
        marker = await session.scalar(
            select(ClassSetting).where(ClassSetting.key == RELEASE_KEY)
            .with_for_update().execution_options(populate_existing=True)
        )
        if marker is None:
            return False
        current = _decode_state(marker.value)
        if current.get("owner") != owner:
            return False
        marker.value = json.dumps(state, ensure_ascii=False)
        await session.commit()
        return True


async def _recipient_ids(session: AsyncSession) -> list[int]:
    company_ids = await session.execute(
        select(User.tg_id)
        .join(NatCompany, NatCompany.user_id == User.id)
        .distinct()
    )
    recipients = {int(tg_id) for tg_id in company_ids.scalars().all() if tg_id and int(tg_id) > 0}
    recipients.update(await PlayerRegistryService.get_registered_tg_ids(session))
    return sorted(recipients)


async def send_natbirzha_v1_5_announcement(
    bot: Any,
    session_factory,
    *,
    logger: logging.Logger | None = None,
) -> dict[str, int | bool]:
    """Send the group patch and its separate bonus notice once per recipient."""
    logger = logger or logging.getLogger(__name__)
    owner = uuid4().hex
    now = datetime.now(timezone.utc)
    async with session_factory() as session:
        marker = await session.scalar(
            select(ClassSetting).where(ClassSetting.key == RELEASE_KEY)
            .with_for_update().execution_options(populate_existing=True)
        )
        if marker is None:
            marker = ClassSetting(key=RELEASE_KEY, value="{}")
            session.add(marker)
            try:
                await session.flush()
            except Exception:
                await session.rollback()
                return {"group_sent": False, "dms_sent": 0, "dms_failed": 0, "skipped": True}

        state = _decode_state(marker.value)
        if state.get("status") == "COMPLETE":
            return {
                "group_sent": len(state.get("group_sent", [])) == 2,
                "dms_sent": sum(value == 2 for value in state.get("deliveries", {}).values()),
                "dms_failed": 0,
                "skipped": True,
            }
        started = state.get("started_at")
        if state.get("status") == "RUNNING" and started:
            try:
                if now - datetime.fromisoformat(started) < timedelta(minutes=20):
                    return {"group_sent": False, "dms_sent": 0, "dms_failed": 0, "skipped": True}
            except (TypeError, ValueError):
                pass

        state.setdefault("group_sent", [])
        state.setdefault("deliveries", {})
        state["status"] = "RUNNING"
        state["started_at"] = now.isoformat()
        state["owner"] = owner
        marker.value = json.dumps(state, ensure_ascii=False)
        await session.commit()
        recipient_ids = await _recipient_ids(session)

    async def record() -> bool:
        return await _persist_state(session_factory, state, owner)

    group_id = int(nat_settings.EVENTS_CHAT_ID)
    messages = [("patch", RELEASE_MESSAGE, "HTML"), ("bonus", BONUS_MESSAGE, None)]
    failures = 0
    for message_key, text, parse_mode in messages:
        if message_key in state["group_sent"]:
            continue
        try:
            await bot.send_message(chat_id=group_id, text=text, parse_mode=parse_mode)
            state["group_sent"].append(message_key)
            await record()
        except Exception:
            failures += 1
            logger.exception("NATBIRZHA 1.5 group announcement failed")

    delivered = 0
    for tg_id in recipient_ids:
        progress = int(state["deliveries"].get(str(tg_id), 0) or 0)
        for step, (message_key, text, parse_mode) in enumerate(messages, start=1):
            if progress >= step:
                continue
            try:
                await bot.send_message(chat_id=tg_id, text=text, parse_mode=parse_mode)
                progress = step
                state["deliveries"][str(tg_id)] = progress
                await record()
            except Exception:
                failures += 1
                logger.warning("NATBIRZHA 1.5 DM failed for Telegram user %s", tg_id, exc_info=True)
                break
        if progress == 2:
            delivered += 1

    all_sent = len(state["group_sent"]) == 2 and all(
        int(state["deliveries"].get(str(tg_id), 0) or 0) == 2 for tg_id in recipient_ids
    )
    state["status"] = "COMPLETE" if all_sent else "PARTIAL"
    state["attempted_at"] = datetime.now(timezone.utc).isoformat()
    state.pop("owner", None)
    await _persist_state(session_factory, state, owner)
    return {
        "group_sent": len(state["group_sent"]) == 2,
        "dms_sent": delivered,
        "dms_failed": max(0, len(recipient_ids) - delivered) + failures,
        "skipped": False,
    }


__all__ = ["BONUS_MESSAGE", "RELEASE_MESSAGE", "send_natbirzha_v1_5_announcement"]
