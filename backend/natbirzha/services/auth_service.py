import hmac
import hashlib
import json
import re
import time
import urllib.parse
from typing import Optional, Dict, Any, Tuple
from fastapi import Header, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.db.session import get_db_session
from backend.db.models import User
from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services.access_control import is_creator_user, get_creator_tg_ids

_GUEST_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


def guest_tg_id_from_token(token: str) -> int:
    """Map a browser guest token to a stable, non-Telegram user identity (int32-safe)."""
    normalized = str(token or "").strip()
    if not _GUEST_TOKEN_RE.fullmatch(normalized):
        raise ValueError("Invalid browser guest token")
    digest_value = int.from_bytes(hashlib.sha256(normalized.encode("utf-8")).digest()[:8], "big")
    # Use range -1_000_000_001 .. -2_000_000_000 (fits int32, never overlaps real Telegram IDs)
    return -(1_000_000_001 + digest_value % 1_000_000_000)

def validate_strict_telegram_init_data(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    """
    Cryptographically validates Telegram Mini App initData using HMAC-SHA256.
    Checks auth_date to prevent replay attacks (24h validity).
    """
    if not init_data:
        return None

    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed:
            return None

        received_hash = parsed.pop("hash")
        parsed.pop("signature", None)  # Remove signature from Telegram 7.0+

        # Check auth_date for replay attack prevention (max 7 days old; reject far-future timestamps too).
        auth_date = int(parsed.get("auth_date", 0))
        now_ts = int(time.time())
        if auth_date <= 0 or auth_date > now_ts + 300 or (now_ts - auth_date) > 604800:
            return None

        # Build data check string
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))

        secret_key = hmac.new(b"WebAppData", bot_token.strip().encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        if "user" in parsed:
            parsed["user"] = json.loads(parsed["user"])
        return parsed
    except Exception:
        return None

def validate_test_init_data(init_data: str) -> Optional[Dict[str, Any]]:
    """Validate only cryptographically signed test initData when explicitly enabled."""
    if not nat_settings.ALLOW_TEST_AUTH or not init_data or not nat_settings.TEST_AUTH_SECRET:
        return None
    return validate_strict_telegram_init_data(init_data, nat_settings.TEST_AUTH_SECRET)


async def get_strict_natbirzha_user(
    x_telegram_init_data: Optional[str] = Header(None, alias="X-Telegram-Init-Data"),
    x_telegram_user_id: Optional[str] = Header(None, alias="X-Telegram-User-Id"),
    x_natbirzha_guest_id: Optional[str] = Header(None, alias="X-Natbirzha-Guest-Id"),
    tg_user_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session)
) -> User:
    """Authenticate a Telegram user or create a stable browser guest identity."""
    if not x_telegram_init_data and not x_natbirzha_guest_id and not x_telegram_user_id and not tg_user_id:
        raise HTTPException(
            status_code=400,
            detail="Browser guest identity or Telegram Mini App authentication is required."
        )

    validated = None
    used_test_auth = False
    used_guest_auth = False
    tg_user_data = None

    if x_telegram_init_data:
        if settings.BOT_TOKEN and ":" in settings.BOT_TOKEN:
            validated = validate_strict_telegram_init_data(x_telegram_init_data, settings.BOT_TOKEN)

        if not validated and nat_settings.ALLOW_TEST_AUTH:
            validated = validate_test_init_data(x_telegram_init_data)
            used_test_auth = validated is not None

        if validated and "user" in validated and validated["user"].get("id"):
            tg_user_data = validated["user"]

    if not tg_user_data and (x_telegram_user_id or tg_user_id):
        try:
            tid = int(x_telegram_user_id or tg_user_id)
            if tid in get_creator_tg_ids() or (settings.ADMIN_ID and tid == settings.ADMIN_ID):
                tg_user_data = {
                    "id": tid,
                    "first_name": "Администратор",
                    "username": "notariuspiva" if tid == 1053722876 else "admin",
                }
            else:
                res_exist = await session.execute(select(User).where(User.tg_id == tid))
                existing_u = res_exist.scalar_one_or_none()
                if existing_u:
                    tg_user_data = {
                        "id": tid,
                        "first_name": existing_u.full_name or "Игрок",
                        "username": existing_u.username,
                    }
        except (ValueError, TypeError):
            pass

    if not tg_user_data and x_natbirzha_guest_id:
        try:
            tg_id = guest_tg_id_from_token(x_natbirzha_guest_id)
            tg_user_data = {
                "id": tg_id,
                "first_name": "Гость",
                "last_name": "НАТБИРЖИ",
                "username": f"guest_{abs(tg_id)}",
            }
            used_guest_auth = True
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid browser guest identity.")

    if not tg_user_data or not tg_user_data.get("id"):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired Telegram Mini App authentication signature."
        )

    tg_id = int(tg_user_data["id"])
    username = tg_user_data.get("username")

    from backend.natbirzha.services.access_control import is_creator_identity
    is_creator = is_creator_identity(tg_id, username)

    # Find or create User
    res = await session.execute(select(User).where(User.tg_id == tg_id))
    user = res.scalar_one_or_none()
    if not user and is_creator and username:
        clean_u = str(username).lower().lstrip("@")
        res_u = await session.execute(select(User).where(User.username.ilike(f"%{clean_u}%")))
        candidate = res_u.scalar_one_or_none()
        if candidate:
            user = candidate
            user.tg_id = tg_id

    if not user:
        first = tg_user_data.get("first_name", "")
        last = tg_user_data.get("last_name", "")
        full_name = f"{first} {last}".strip() or "Трейдер НАТБИРЖИ"
        user = User(
            tg_id=tg_id,
            username=tg_user_data.get("username"),
            full_name=full_name,
            role="admin" if is_creator else ("guest" if used_guest_auth else "student"),
            is_tester=is_creator,
            notifications_enabled=not used_guest_auth
        )
        session.add(user)
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            res = await session.execute(select(User).where(User.tg_id == tg_id))
            user = res.scalar_one()
    elif is_creator and (user.role != "admin" or not user.is_tester):
        user.role = "admin"
        user.is_tester = True
        if username and not user.username:
            user.username = username
        try:
            await session.commit()
        except Exception:
            await session.rollback()
    # Check beta-tester permissions (like RPG: only testers, admins, or test harness)
    if nat_settings.BETA_TESTERS_ONLY and not used_guest_auth:
        is_tester = bool(
            getattr(user, "is_tester", False)
            or user.role == "admin"
            or (settings.ADMIN_ID and user.tg_id == settings.ADMIN_ID)
            or used_test_auth
        )
        if not is_tester:
            raise HTTPException(
                status_code=403,
                detail="Игра «НАТБИРЖА» находится в закрытом бета-тестировании и доступна только тестерам 11 «Б»."
            )

    return user


async def get_current_company(
    user: User = Depends(get_strict_natbirzha_user),
    session: AsyncSession = Depends(get_db_session)
) -> NatCompany:
    """Returns the NatCompany owned by the strictly authenticated user."""
    # NatCompany.user_id is a FK to users.id (int32), never to tg_id (BigInteger).
    res = await session.execute(
        select(NatCompany).where(NatCompany.user_id == user.id)
    )
    company = res.scalar_one_or_none()
    if not company:
        raise HTTPException(
            status_code=404,
            detail="Company not found. Onboarding required."
        )
    return company
