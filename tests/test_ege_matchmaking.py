import asyncio
from types import SimpleNamespace

from backend.api.game_rooms import GameRoomManager
from backend.api.public_access import is_public_arena_path
from backend.api.ege_matchmaking import (
    get_matchmaking_candidate_ids,
    send_matchmaking_notifications,
)
from backend.ege import ranking


class _CandidateSession:
    def __init__(self, notification_enabled_ids):
        self.notification_enabled_ids = notification_enabled_ids

    async def execute(self, _query):
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(all=lambda: self.notification_enabled_ids)
        )


def test_matchmaking_is_on_public_arena_api_surface():
    assert is_public_arena_path("/api/ege/matchmaking/search")


def test_candidate_ids_come_from_ranked_arena_roster_and_respect_notifications(monkeypatch):
    async def fake_leaderboard(_session):
        return [
            {"tg_id": 101, "nickname": "First"},
            {"tg_id": 202, "nickname": "Second"},
            {"tg_id": 303, "nickname": "Third"},
        ]

    monkeypatch.setattr(ranking, "get_leaderboard", fake_leaderboard)
    session = _CandidateSession([202, 303])

    assert asyncio.run(get_matchmaking_candidate_ids(session, host_tg_id=101)) == [202, 303]


def test_matchmaking_notification_opens_searching_player_room():
    manager = GameRoomManager()
    room = manager.create_room(
        host_tg_id=101,
        host_name="Ищущий",
        game_type="ege_stress_duel",
    )
    room.matchmaking_search = True
    sent = []

    class FakeBot:
        async def send_message(self, **kwargs):
            sent.append(kwargs)

    asyncio.run(send_matchmaking_notifications(FakeBot(), room, [202], "https://example.test/app"))

    assert len(sent) == 1
    assert "Ищущий" in sent[0]["text"]
    assert "ударения" in sent[0]["text"]
    button = sent[0]["reply_markup"].inline_keyboard[0][0]
    assert button.web_app.url == (
        f"https://example.test/app?room={room.room_id}"
        "&game=ege_stress_duel&tg_user_id=202"
    )
    assert room.matchmaking_recipient_count == 1


def test_only_first_invited_player_can_join_matchmaking_room():
    manager = GameRoomManager()
    room = manager.create_room(
        host_tg_id=101,
        host_name="Ищущий",
        game_type="ege_stress_duel",
    )
    room.matchmaking_search = True

    assert manager.join_room(room.room_id, 202, "Первый") == (True, "Успешное подключение")
    assert manager.join_room(room.room_id, 303, "Второй")[0] is False
    assert room.opponent_tg_id == 202
    assert room.status == "playing"


def test_ege_duel_lobby_has_single_find_duel_button():
    from pathlib import Path

    frontend = Path(__file__).parents[1] / "frontend"
    source = (frontend / "js/ege/ege_duel.js").read_text(encoding="utf-8")
    index = (frontend / "index.html").read_text(encoding="utf-8")
    assert "Найти дуэль" in source
    assert "window.EGE.findDuel()" in source
    assert "ege_duel.js?v=20260923_duel_matchmaking" in index
    assert "api.js?v=20260923_duel_matchmaking" in index


def test_search_endpoint_creates_search_room_and_schedules_broadcast(monkeypatch):
    from fastapi import BackgroundTasks
    from starlette.requests import Request

    from backend.api import ege_matchmaking
    from backend.api.routers import ege_arena
    from backend.bot import bot as bot_module

    manager = ege_arena.game_manager
    host_tg_id = 90909091
    async def fake_candidates(_session, requester_id):
        assert requester_id == host_tg_id
        return [202, 303]

    async def fake_payload(_session, room, viewer_tg_id):
        return room.to_dict(viewer_tg_id)

    class FakeBot:
        pass

    monkeypatch.setattr(ege_arena, "get_matchmaking_candidate_ids", fake_candidates)
    monkeypatch.setattr(ege_arena, "build_ege_room_payload", fake_payload)
    monkeypatch.setattr(ege_arena, "get_public_webapp_url", lambda _request: "https://example.test/app")
    monkeypatch.setattr(bot_module, "get_current_bot", lambda: FakeBot())
    request = Request({
        "type": "http",
        "method": "POST",
        "scheme": "https",
        "path": "/api/ege/matchmaking/search",
        "headers": [(b"host", b"example.test")],
        "query_string": b"",
        "server": ("example.test", 443),
        "client": ("127.0.0.1", 1234),
    })
    tasks = BackgroundTasks()
    user = SimpleNamespace(tg_id=host_tg_id, ege_nickname="MatchMe")

    response = asyncio.run(ege_arena.search_ege_duel(
        request, tasks, {"game_type": "ege_stress_duel"}, user, object()
    ))

    assert response["status"] == "waiting"
    assert response["matchmaking_search"] is True
    assert response["notifications_queued"] == 2
    assert len(tasks.tasks) == 1
    assert tasks.tasks[0].func is ege_matchmaking.send_matchmaking_notifications
    room_id = response["room_id"]
    reused_response = asyncio.run(ege_arena.search_ege_duel(
        request, BackgroundTasks(), {"game_type": "ege_stress_duel"}, user, object()
    ))
    assert reused_response["room_id"] == room_id
    assert len(tasks.tasks) == 1
    manager.rooms.pop(room_id, None)
