import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from backend.natbirzha.services.event_broadcaster import EventBroadcaster


def setup_function():
    EventBroadcaster._cached_chat_id = None


def teardown_function():
    EventBroadcaster._cached_chat_id = None


def test_get_alternative_chat_id():
    # Regular group -> supergroup
    assert EventBroadcaster._get_alternative_chat_id(-5495179388) == -1005495179388
    # Supergroup -> regular group
    assert EventBroadcaster._get_alternative_chat_id(-1005495179388) == -5495179388
    # Positive ID has no group alternative
    assert EventBroadcaster._get_alternative_chat_id(123456) is None


def test_broadcast_when_bot_is_none():
    async def run():
        with patch.object(EventBroadcaster, "_get_bot", return_value=None):
            sent = await EventBroadcaster.send_message("Test message")
            assert sent is False

    asyncio.run(run())


def test_broadcast_market_order_buy():
    async def run():
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=True)

        with patch.object(EventBroadcaster, "_get_bot", return_value=mock_bot):
            await EventBroadcaster.broadcast_market_order(
                company_name="Северный Газ",
                ticker="NVGZ",
                order_type="BUY",
                item_id="oil_crude",
                quantity=100.0,
                price=55.0,
            )

        mock_bot.send_message.assert_awaited_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] in (-1004491945174, -5495179388)
        assert "Запрос на покупку" in call_kwargs["text"]
        assert "Северный Газ" in call_kwargs["text"]
        assert "NVGZ" in call_kwargs["text"]
        assert "Сырая нефть" in call_kwargs["text"]
        assert "100.00 барр." in call_kwargs["text"]
        assert "55.00 ₽" in call_kwargs["text"]

    asyncio.run(run())


def test_broadcast_market_order_sell():
    async def run():
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=True)

        with patch.object(EventBroadcaster, "_get_bot", return_value=mock_bot):
            await EventBroadcaster.broadcast_market_order(
                company_name="СтальПром & Co",
                ticker="STAL",
                order_type="SELL",
                item_id="steel",
                quantity=50.0,
                price=110.0,
            )

        mock_bot.send_message.assert_awaited_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert "Заявка на продажу" in call_kwargs["text"]
        assert "СтальПром &amp; Co" in call_kwargs["text"]  # HTML escaped
        assert "Конструкционная сталь" in call_kwargs["text"]
        assert "50.00 т" in call_kwargs["text"]

    asyncio.run(run())


def test_broadcast_sabotage_start_and_end():
    async def run():
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=True)

        spec = {
            "id": "key_rate",
            "name": "Повышение ключевой ставки",
            "icon": "📈",
            "duration_hours": 24,
            "news_headline": "ЦБ повышает ставку до максимума!",
            "news_body": "Кредиты подорожали на 10%, доходность облигаций упала.",
        }

        with patch.object(EventBroadcaster, "_get_bot", return_value=mock_bot):
            await EventBroadcaster.broadcast_sabotage_start(spec)
            assert mock_bot.send_message.await_count == 1
            text_start = mock_bot.send_message.call_args.kwargs["text"]
            assert "ГОСУДАРСТВЕННЫЙ САБОТАЖ" in text_start
            assert "Повышение ключевой ставки" in text_start
            assert "ЦБ повышает ставку" in text_start

            await EventBroadcaster.broadcast_sabotage_end(
                title="Повышение ключевой ставки",
                reason="CREATOR_ABORT",
                headline="Кризис завершен досрочно",
                body="Ставка возвращена к норме.",
            )
            assert mock_bot.send_message.await_count == 2
            text_end = mock_bot.send_message.call_args.kwargs["text"]
            assert "ЗАВЕРШЕНИЕ САБОТАЖА" in text_end
            assert "Ставка возвращена к норме." in text_end

    asyncio.run(run())


def test_broadcast_creator_warning():
    async def run():
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=True)

        with patch.object(EventBroadcaster, "_get_bot", return_value=mock_bot):
            await EventBroadcaster.broadcast_creator_warning(
                company_name="НефтеТех",
                ticker="NTEX",
                reason="Манипулирование ценами на дизельное топливо",
            )

        mock_bot.send_message.assert_awaited_once()
        text = mock_bot.send_message.call_args.kwargs["text"]
        assert "ГОСУДАРСТВЕННОЕ ПРЕДУПРЕЖДЕНИЕ" in text
        assert "НефтеТех" in text
        assert "NTEX" in text
        assert "Манипулирование ценами" in text

    asyncio.run(run())


def test_broadcast_bond_issued():
    async def run():
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=True)

        with patch.object(EventBroadcaster, "_get_bot", return_value=mock_bot):
            await EventBroadcaster.broadcast_bond_issued(
                title="ОФЗ 2026 Серия 1",
                volume=1000,
                face_value=1000.0,
                coupon_rate=5.0,
                maturity_days=30,
                purpose="Строительство транспортных развязок",
            )

        mock_bot.send_message.assert_awaited_once()
        text = mock_bot.send_message.call_args.kwargs["text"]
        assert "ВЫПУСК ГОСУДАРСТВЕННЫХ ОБЛИГАЦИЙ" in text
        assert "ОФЗ 2026 Серия 1" in text
        assert "1,000 шт." in text
        assert "5% в день" in text
        assert "Строительство транспортных развязок" in text

    asyncio.run(run())


def test_broadcast_bankruptcy_and_default():
    async def run():
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=True)

        with patch.object(EventBroadcaster, "_get_bot", return_value=mock_bot):
            await EventBroadcaster.broadcast_bankruptcy(
                company_name="УралМеталл",
                ticker="UMET",
                reason="Принудительная ликвидация",
                details="Активы выставлены на торги.",
            )
            await EventBroadcaster.broadcast_bond_default(
                title="ОФЗ Серия 2",
                details="Объявлен дефолт по выпуску.",
            )

        assert mock_bot.send_message.await_count == 2
        text1 = mock_bot.send_message.call_args_list[0].kwargs["text"]
        assert "БАНКРОТСТВО КОМПАНИИ" in text1
        assert "УралМеталл" in text1

        text2 = mock_bot.send_message.call_args_list[1].kwargs["text"]
        assert "ДЕФОЛТ ПО ОБЛИГАЦИЯМ" in text2
        assert "ОФЗ Серия 2" in text2

    asyncio.run(run())


def test_broadcast_ipo_and_state_share():
    async def run():
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=True)

        with patch.object(EventBroadcaster, "_get_bot", return_value=mock_bot):
            await EventBroadcaster.broadcast_ipo(
                company_name="ИТ Технологии",
                ticker="ITEC",
                specialization="electronics",
                total_shares=100000,
                float_shares=40000,
                sale_pct=40.0,
                share_price=25.50,
                valuation=2550000.0,
                dividend_rate_pct=15.0,
            )
            await EventBroadcaster.broadcast_state_share_issued(
                title="ГосЭнерго",
                purpose="Модернизация электросетей",
                volume=5000,
                issue_price=200.0,
                dividend_rate_pct=12.0,
            )

        assert mock_bot.send_message.await_count == 2
        text_ipo = mock_bot.send_message.call_args_list[0].kwargs["text"]
        assert "НОВЫЙ ВЫХОД НА БИРЖУ (IPO)" in text_ipo
        assert "ИТ Технологии" in text_ipo
        assert "$ITEC" in text_ipo
        assert "Электроника и IT" in text_ipo
        assert "100,000 шт." in text_ipo
        assert "40,000 шт. (40%)" in text_ipo
        assert "25.50 ₽" in text_ipo

        text_share = mock_bot.send_message.call_args_list[1].kwargs["text"]
        assert "ВЫПУСК ГОСУДАРСТВЕННЫХ АКЦИЙ" in text_share
        assert "ГосЭнерго" in text_share
        assert "Модернизация электросетей" in text_share

    asyncio.run(run())


def test_fallback_to_supergroup_chat_id():
    async def run():
        mock_bot = MagicMock()

        async def mock_send(chat_id, text, parse_mode="HTML"):
            if chat_id == -1004491945174:
                raise Exception("TelegramBadRequest: chat not found")
            return True

        mock_bot.send_message = AsyncMock(side_effect=mock_send)

        with patch.object(EventBroadcaster, "_get_bot", return_value=mock_bot):
            success = await EventBroadcaster.send_message("Test message")

        assert success is True
        assert mock_bot.send_message.await_count >= 2
        assert mock_bot.send_message.call_args_list[0].kwargs["chat_id"] == -1004491945174
        # Should be cached now to the succeeding ID
        assert EventBroadcaster._cached_chat_id is not None
        assert EventBroadcaster._cached_chat_id != -1004491945174

    asyncio.run(run())


def test_broadcast_creator_warning_with_owner_tag():
    async def run():
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=True)

        with patch.object(EventBroadcaster, "_get_bot", return_value=mock_bot):
            await EventBroadcaster.broadcast_creator_warning(
                company_name="Кериковские Залежи",
                ticker="KZMI",
                reason="Не закрытый кредит",
                owner_tag="@kerik",
            )

        mock_bot.send_message.assert_awaited_once()
        text = mock_bot.send_message.call_args.kwargs["text"]
        assert "ГОСУДАРСТВЕННОЕ ПРЕДУПРЕЖДЕНИЕ" in text
        assert "Кериковские Залежи" in text
        assert "KZMI" in text
        assert "@kerik" in text
        assert "Владелец:" in text
        assert "Не закрытый кредит" in text

    asyncio.run(run())


def test_broadcast_state_announcement():
    async def run():
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=True)

        with patch.object(EventBroadcaster, "_get_bot", return_value=mock_bot):
            await EventBroadcaster.broadcast_state_announcement(
                message="Срочная проверка налоговой инспекцией!",
                owner_tag="@ivan",
                company_name="СтройТрест",
                ticker="STR",
            )

        mock_bot.send_message.assert_awaited_once()
        text = mock_bot.send_message.call_args.kwargs["text"]
        assert "ГОСУДАРСТВЕННОЕ ОБЪЯВЛЕНИЕ" in text
        assert "СтройТрест" in text
        assert "STR" in text
        assert "@ivan" in text
        assert "Срочная проверка" in text
        assert "Государственный Регулятор" in text

    asyncio.run(run())


if __name__ == "__main__":
    print("Running tests manually...")
    test_get_alternative_chat_id()
    test_broadcast_when_bot_is_none()
    test_broadcast_market_order_buy()
    test_broadcast_market_order_sell()
    test_broadcast_sabotage_start_and_end()
    test_broadcast_creator_warning()
    test_broadcast_creator_warning_with_owner_tag()
    test_broadcast_state_announcement()
    test_broadcast_bond_issued()
    test_broadcast_bankruptcy_and_default()
    test_broadcast_ipo_and_state_share()
    test_fallback_to_supergroup_chat_id()
    print("All EventBroadcaster tests passed!")
