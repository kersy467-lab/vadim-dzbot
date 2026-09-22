"""Backward-compatible facade for EGE Arena ranking helpers."""
from backend.ege.ranking import (
    LOSS_RATING,
    MAX_RATING,
    MIN_RATING,
    WIN_RATING,
    build_room_payload as build_ege_room_payload,
    clamp_rating,
    medal_for_rating,
    rating_payload,
    settle_duel as settle_ege_duel_rating,
)

__all__ = [
    "LOSS_RATING", "MAX_RATING", "MIN_RATING", "WIN_RATING", "build_ege_room_payload",
    "clamp_rating", "medal_for_rating", "rating_payload", "settle_ege_duel_rating",
]
