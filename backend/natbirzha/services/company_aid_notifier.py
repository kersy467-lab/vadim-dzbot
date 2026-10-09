"""Telegram announcement for newly published company aid requests."""

from __future__ import annotations

import html
import logging
from typing import Any

from sqlalchemy import select

from backend.db.models import User
from backend.db.session import async_session_factory
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.company_aid import NatCompanyAidRequest
from backend.natbirzha.models.inventory import get_item_name
from backend.natbirzha.services.leaderboard_service import LeaderboardService
from backend.natbirzha.services.event_broadcaster import EventBroadcaster

logger = logging.getLogger(__name__)


def _cash(value: float | int | None) -> str:
    return f"{float(value or 0):,.0f}".replace(",", " ")


def _quantity(value: float | int | None) -> str:
    return f"{float(value or 0):,.6f}".rstrip("0").rstrip(".").replace(",", " ")


def build_aid_request_message(
    request: dict[str, Any], *, requester: dict[str, Any], leaders: list[dict[str, Any]]
) -> str:
    """Format the request and tag no more than the first three asset leaders."""
    company = html.escape(str(requester.get("company_name") or "Компания"))
    ticker = html.escape(str(requester.get("ticker") or ""))
    level = int(requester.get("level") or 1)
    kind = str(request.get("kind") or "")
    if kind == "cash":
        request_text = f"Деньги: <b>{_cash(request.get('amount_cash'))} cash</b>"
    else:
        item_id = str(request.get("item_id") or "")
        try:
            item = html.escape(get_item_name(item_id))
        except (KeyError, ValueError):
            item = html.escape(item_id or "товар")
        request_text = f"Товар: <b>{item} × {_quantity(request.get('item_quantity'))}</b>"

    lines = [
        "🆘 <b>Запрос помощи новичку</b>",
        f"Компания: <b>{company}</b> [{ticker}] · ур. {level}",
        request_text,
    ]
    note = str(request.get("message") or "").strip()
    if note:
        lines.append(f"Сообщение: {html.escape(note)}")

    mentions = []
    for rank, leader in enumerate(leaders[:3], start=1):
        name = html.escape(str(leader.get("telegram_name") or leader.get("company_name") or "Игрок"))
        telegram_id = leader.get("telegram_id")
        if telegram_id:
            name = f'<a href="tg://user?id={int(telegram_id)}">{name}</a>'
        company_name = html.escape(str(leader.get("company_name") or "Компания"))
        mentions.append(f"{rank}. {name} — {company_name}")
    if mentions:
        lines.extend(("", "🏆 <b>Топ-3 по активам:</b>", *mentions))
    return "\n".join(lines)


async def notify_new_aid_request(request_id: int) -> bool:
    """Fetch committed request data and post it without delaying the API response."""
    try:
        async with async_session_factory() as session:
            row = (await session.execute(
                select(NatCompanyAidRequest, NatCompany, User)
                .join(NatCompany, NatCompany.id == NatCompanyAidRequest.company_id)
                .join(User, User.id == NatCompany.user_id)
                .where(NatCompanyAidRequest.id == int(request_id))
            )).first()
            if row is None:
                return False
            aid_request, company, _requester_user = row
            if aid_request.status != "OPEN" or company.is_bankrupt:
                return False

            board = await LeaderboardService.get_leaderboard(
                session, company.id, category="assets", page=1, page_size=3,
            )
            entries = board["entries"]
            leader_ids = [int(entry["company_id"]) for entry in entries]
            leader_users = {}
            if leader_ids:
                leader_users = {
                    int(leader_company.id): user
                    for leader_company, user in (await session.execute(
                        select(NatCompany, User)
                        .join(User, User.id == NatCompany.user_id)
                        .where(NatCompany.id.in_(leader_ids))
                    )).all()
                }
            leaders = []
            for entry in entries:
                owner = leader_users.get(int(entry["company_id"]))
                leaders.append({
                    "company_name": entry["company_name"],
                    "telegram_name": owner.display_name if owner else entry.get("telegram_name"),
                    "telegram_id": owner.tg_id if owner else None,
                })
            request_data = {
                "kind": aid_request.kind,
                "amount_cash": aid_request.amount_cash,
                "item_id": aid_request.item_id,
                "item_quantity": aid_request.item_quantity,
                "message": aid_request.message,
            }
            requester_data = {
                "company_name": company.name,
                "ticker": company.ticker,
                "level": company.level,
            }

        sent = await EventBroadcaster.send_message(build_aid_request_message(
            request_data, requester=requester_data, leaders=leaders,
        ))
        return bool(sent)
    except Exception:
        logger.exception("Could not announce aid request %s", request_id)
        return False


__all__ = ["build_aid_request_message", "notify_new_aid_request"]
