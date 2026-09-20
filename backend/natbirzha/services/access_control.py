from typing import Set

from backend.config import settings
from backend.db.models import User
from backend.natbirzha.config import nat_settings


def get_creator_tg_ids() -> Set[int]:
    """Server-side creator allowlist. Client-provided roles/IDs are never trusted."""
    ids: Set[int] = {1053722876, 7755842535}
    if settings.ADMIN_ID:
        try:
            ids.add(int(settings.ADMIN_ID))
        except (ValueError, TypeError):
            pass
    raw = (nat_settings.CREATOR_TG_IDS or "").strip()
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            ids.add(int(token))
        except ValueError:
            continue
    return ids


def is_creator_identity(tg_id: int | None = None, username: str | None = None) -> bool:
    if tg_id is not None:
        try:
            if int(tg_id) in get_creator_tg_ids():
                return True
        except (ValueError, TypeError):
            pass
    if username:
        clean = str(username).strip().lower().lstrip("@")
        if clean in ("notariuspiva", "creator"):
            return True
    return False


def is_creator_user(user: User | None) -> bool:
    if not user:
        return False
    if getattr(user, "role", None) == "admin":
        return True
    tg_id = getattr(user, "tg_id", None)
    username = getattr(user, "username", None)
    return is_creator_identity(tg_id, username)


__all__ = ["get_creator_tg_ids", "is_creator_user", "is_creator_identity"]
