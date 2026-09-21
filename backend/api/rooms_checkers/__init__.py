# backend/api/rooms_checkers/__init__.py
from backend.api.rooms_checkers.engine import CheckersBoard
from backend.api.rooms_checkers.room import CheckersRoom

__all__ = ["CheckersBoard", "CheckersRoom"]
