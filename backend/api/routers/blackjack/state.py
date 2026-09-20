import time
from typing import Dict, Any, Optional
from backend.bot.game_blackjack import BlackjackGame

# Хранилище сессий игры Блэкджек: user_tg_id -> {"game": BlackjackGame, "settled": bool, "updated_at": float}
_blackjack_sessions: Dict[int, Dict[str, Any]] = {}


def get_session(user_tg_id: int) -> Optional[Dict[str, Any]]:
    """Получить активную сессию игрока."""
    session = _blackjack_sessions.get(user_tg_id)
    if session:
        # Проверяем, не устарела ли сессия (старше 1 часа)
        if time.time() - session.get("updated_at", 0) > 3600:
            _blackjack_sessions.pop(user_tg_id, None)
            return None
        session["updated_at"] = time.time()
    return session


def create_session(user_tg_id: int, stake: int) -> Dict[str, Any]:
    """Создать новую партию для игрока."""
    game = BlackjackGame(stake=stake)
    session = {
        "game": game,
        "settled": False,
        "updated_at": time.time(),
    }
    _blackjack_sessions[user_tg_id] = session
    return session


def clear_session(user_tg_id: int) -> None:
    """Удалить сессию после завершения или при выходе."""
    _blackjack_sessions.pop(user_tg_id, None)


def cleanup_expired_sessions(max_age_seconds: int = 3600) -> None:
    """Очистка заброшенных сессий старше указанного времени."""
    now = time.time()
    expired = [
        uid for uid, s in _blackjack_sessions.items()
        if now - s.get("updated_at", 0) > max_age_seconds
    ]
    for uid in expired:
        _blackjack_sessions.pop(uid, None)
