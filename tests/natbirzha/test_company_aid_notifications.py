"""Public aid-request notices mention the three wealth leaders."""

import os
import sys

sys.path.insert(0, os.path.abspath("."))

from backend.natbirzha.services.company_aid_notifier import build_aid_request_message


def test_aid_notice_mentions_top_three_in_asset_rank_order():
    request = {
        "kind": "cash",
        "amount_cash": 25_000,
        "message": "Нужна помощь <срочно>",
    }
    leaders = [
        {"company_name": "Первый & Co", "telegram_name": "Аня <3", "telegram_id": 101},
        {"company_name": "Второй", "telegram_name": "Борис", "telegram_id": 102},
        {"company_name": "Третий", "telegram_name": None, "telegram_id": 103},
        {"company_name": "Четвёртый", "telegram_name": "Не тегать", "telegram_id": 104},
    ]

    message = build_aid_request_message(
        request,
        requester={"company_name": "Новичок", "ticker": "NEW", "level": 3},
        leaders=leaders,
    )

    assert "tg://user?id=101" in message
    assert "tg://user?id=102" in message
    assert "tg://user?id=103" in message
    assert "tg://user?id=104" not in message
    assert "Первый &amp; Co" in message
    assert "Аня &lt;3" in message
    assert "Нужна помощь &lt;срочно&gt;" in message
    assert message.index("tg://user?id=101") < message.index("tg://user?id=102")


if __name__ == "__main__":
    test_aid_notice_mentions_top_three_in_asset_rank_order()
    print("Aid request announcement formatting: PASS")
