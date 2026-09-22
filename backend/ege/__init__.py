"""EGE Arena domain services."""

from backend.ege.ranking import (
    LEADERBOARD_TTL_SECONDS,
    LOSS_RATING,
    MAX_RATING,
    MIN_RATING,
    WIN_RATING,
    build_room_payload,
    get_leaderboard,
    get_player_profile,
    medal_for_rating,
    normalize_nickname,
    rating_payload,
    settle_duel,
    validate_nickname,
)

__all__ = [
    "LEADERBOARD_TTL_SECONDS", "LOSS_RATING", "MAX_RATING", "MIN_RATING", "WIN_RATING",
    "build_room_payload", "get_leaderboard", "get_player_profile", "medal_for_rating",
    "normalize_nickname", "rating_payload", "settle_duel", "validate_nickname",
]
