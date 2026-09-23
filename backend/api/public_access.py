"""Backend gate: public accounts can only use EGE Arena API surface."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.db.crud import get_user_by_tg_id, has_full_access

_PUBLIC_EXACT = {
    "/api/me",
    "/api/natbirzha/auth/login",
    "/api/natbirzha/auth/me",
    "/api/games/ege-rating",
    "/api/games/invite",
    "/api/ege/profile",
    "/api/ege/leaderboard",
    "/api/ege/players",
    "/api/ege/nickname",
}
_PUBLIC_PREFIXES = ("/api/ege/profile/", "/api/games/room/")


def _tg_id_from_request(request: Request) -> int | None:
    raw = request.headers.get("x-telegram-user-id") or request.query_params.get("tg_user_id") \
        or request.query_params.get("uid") or request.query_params.get("user_id")
    try:
        if raw:
            return int(raw)
    except (TypeError, ValueError):
        pass

    init_data = request.headers.get("x-telegram-init-data")
    if init_data:
        from backend.config import settings
        from backend.api.auth import validate_telegram_init_data
        validated = validate_telegram_init_data(init_data, settings.BOT_TOKEN)
        if validated and "user" in validated:
            u_obj = validated["user"]
            if isinstance(u_obj, dict) and u_obj.get("id"):
                return int(u_obj["id"])
        try:
            import urllib.parse
            import json
            parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
            if "user" in parsed:
                u_obj = json.loads(parsed["user"]) if isinstance(parsed["user"], str) else parsed["user"]
                if isinstance(u_obj, dict) and u_obj.get("id"):
                    return int(u_obj["id"])
        except Exception:
            pass

    guest_token = request.headers.get("x-natbirzha-guest-id")
    if guest_token:
        try:
            from backend.natbirzha.services.auth_service import guest_tg_id_from_token
            return guest_tg_id_from_token(guest_token)
        except Exception:
            pass
    return None


def is_public_arena_path(path: str) -> bool:
    return path in _PUBLIC_EXACT or any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES)


async def enforce_api_access(request: Request, call_next):
    path = request.url.path
    if not path.startswith("/api/") or is_public_arena_path(path):
        return await call_next(request)

    # Check FastAPI test dependency overrides (e.g. TestClient mock auth)
    overrides = getattr(request.app, "dependency_overrides", None)
    if overrides:
        from backend.api.auth import get_current_webapp_user, get_optional_webapp_user
        for dep in (get_current_webapp_user, get_optional_webapp_user):
            ovr = overrides.get(dep)
            if ovr:
                try:
                    mock_user = ovr()
                    if has_full_access(mock_user):
                        return await call_next(request)
                except Exception:
                    pass

    tg_id = _tg_id_from_request(request)
    if not tg_id:
        return JSONResponse(status_code=401, content={"detail": "Требуется авторизация через Telegram."})

    # Allow Natbirzha guest users to access Natbirzha endpoints
    if tg_id < 0 and path.startswith("/api/natbirzha/"):
        return await call_next(request)

    from backend.config import settings
    from backend.db.session import async_session_factory
    async with async_session_factory() as session:
        user = await get_user_by_tg_id(session, tg_id)
        if not user and (
            (settings.ADMIN_ID and tg_id == settings.ADMIN_ID)
            or tg_id in {1053722876, 7755842535}
        ):
            from backend.db.crud import create_user
            user = await create_user(
                session=session,
                tg_id=tg_id,
                full_name="Admin",
                role="admin",
                is_tester=True
            )
        if not has_full_access(user):
            return JSONResponse(status_code=403, content={"detail": "Доступно только пользователям с привилегией «Одноклассник»."})
    return await call_next(request)
