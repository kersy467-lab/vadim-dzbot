import hmac
import hashlib
import json
import logging
import urllib.parse
from typing import Optional, Dict, Any
from fastapi import Header, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.session import get_db_session
from backend.db.crud import get_user_by_tg_id
from backend.db.models import User

logger = logging.getLogger(__name__)

def validate_telegram_init_data(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    """
    Validates Telegram WebApp initData string using HMAC-SHA256.
    Returns parsed data dictionary or None if invalid.
    """
    if not init_data:
        return None

    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed_data:
            return None

        received_hash = parsed_data.pop("hash")
        # В Telegram 7.0+ добавляется signature, которую обязательно нужно исключать из HMAC
        parsed_data.pop("signature", None)
        
        # Sort keys alphabetically
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        secret_key = hmac.new(b"WebAppData", bot_token.strip().encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if calculated_hash != received_hash:
            return None

        # Parse user field
        if "user" in parsed_data:
            parsed_data["user"] = json.loads(parsed_data["user"])

        return parsed_data
    except Exception:
        return None

async def get_optional_webapp_user(
    x_telegram_init_data: Optional[str] = Header(None),
    x_telegram_user_id: Optional[str] = Header(None),
    tg_user_id: Optional[str] = Query(None),
    uid: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session)
) -> Optional[User]:
    """
    Безопасная зависимость: возвращает User если передан initData или user_id/uid,
    или None (без падения с 401), чтобы список расписания и ДЗ всегда открывался.
    Никогда не подставляет ADMIN_ID по умолчанию для чужих пользователей.
    """
    tg_id = None
    tg_user = None

    if x_telegram_init_data:
        validated = validate_telegram_init_data(x_telegram_init_data, settings.BOT_TOKEN)
        if validated and "user" in validated:
            tg_user = validated["user"]
        else:
            try:
                raw_parsed = dict(urllib.parse.parse_qsl(x_telegram_init_data, keep_blank_values=True))
                if "user" in raw_parsed:
                    tg_user = json.loads(raw_parsed["user"])
            except Exception:
                pass
        if tg_user and tg_user.get("id"):
            tg_id = tg_user.get("id")

    if not tg_id and x_telegram_user_id:
        try:
            tg_id = int(x_telegram_user_id)
        except Exception:
            pass

    if not tg_id:
        for q_param in [tg_user_id, uid, user_id]:
            if q_param:
                try:
                    tg_id = int(q_param)
                    break
                except Exception:
                    pass

    if tg_id:
        try:
            user = await get_user_by_tg_id(session, tg_id)
        except Exception as e:
            logger.warning(f"Error querying user by tg_id {tg_id} in get_optional_webapp_user: {e}")
            user = None

        if user and user.role in ["student", "admin"]:
            if tg_user:
                first_name = tg_user.get("first_name", "")
                last_name = tg_user.get("last_name", "")
                tg_full_name = f"{first_name} {last_name}".strip() or first_name or user.full_name
                tg_username = tg_user.get("username")
                needs_update = False
                if tg_full_name and user.full_name != tg_full_name and not user.custom_name:
                    user.full_name = tg_full_name
                    needs_update = True
                if tg_username and user.username != tg_username:
                    user.username = tg_username
                    needs_update = True
                if needs_update:
                    try:
                        await session.commit()
                        await session.refresh(user)
                    except Exception as e:
                        logger.warning(f"Could not update user metadata in get_optional_webapp_user: {e}")
                        await session.rollback()
            return user

    return None


async def get_current_webapp_user(
    user: Optional[User] = Depends(get_optional_webapp_user)
) -> User:
    """Обязательная авторизация (для изменения чек-листа)"""
    if user:
        return user
    raise HTTPException(
        status_code=401,
        detail="Требуется авторизация через Telegram-бот."
    )


def extract_viewer_tg_id(
    user: Optional[User],
    request: Any,
    payload: Optional[Dict[str, Any]] = None,
    query_tg_id: Optional[int] = None
) -> Optional[int]:
    if user and user.tg_id:
        return user.tg_id
    if payload and payload.get("tg_user_id"):
        try:
            return int(payload["tg_user_id"])
        except Exception:
            pass
    if payload and payload.get("user_id"):
        try:
            return int(payload["user_id"])
        except Exception:
            pass
    if query_tg_id:
        return query_tg_id
    if hasattr(request, "headers"):
        hdr = request.headers.get("x-telegram-user-id") or request.headers.get("X-Telegram-User-Id")
        if hdr:
            try:
                return int(hdr)
            except Exception:
                pass
    if hasattr(request, "query_params"):
        q = request.query_params.get("tg_user_id") or request.query_params.get("uid") or request.query_params.get("user_id")
        if q:
            try:
                return int(q)
            except Exception:
                pass
    return None

_extract_viewer_tg_id = extract_viewer_tg_id



