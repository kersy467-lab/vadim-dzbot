import os
import hashlib
import mimetypes
from datetime import date, datetime
from typing import Optional, Dict, Any, List
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.exceptions import TelegramAPIError

from backend.db.session import get_db_session
from backend.db.models import User
from backend.api.auth import get_optional_webapp_user
from backend.db.crud import has_full_access
from backend.db.crud import (
    get_bell_schedule, get_bell_schedule_for_date,
    get_all_subjects, get_current_duty_info, get_active_users
)
from backend.config import get_today, settings
from backend.bot.bot import get_current_bot

logger = logging.getLogger(__name__)

router = APIRouter(tags=["common"])


@router.get("/me")
async def get_me(user: Optional[User] = Depends(get_optional_webapp_user)):
    if user:
        # The bot middleware grants the configured ADMIN_ID admin access even
        # when an old database row still has role="student".  Mirror that
        # effective authority in the common Mini App response so the Games
        # tab can expose the separate Natbirzha entry point.  This is only a
        # presentation hint; Natbirzha API routes perform their own checks.
        is_configured_admin = bool(settings.ADMIN_ID and user.tg_id == settings.ADMIN_ID)
        effective_role = "admin" if user.role == "admin" or is_configured_admin else user.role
        effective_tester = bool(getattr(user, "is_tester", False) or effective_role == "admin")
        return {
            "id": user.id,
            "tg_id": user.tg_id,
            "full_name": user.display_name,
            "custom_name": user.custom_name,
            "role": effective_role,
            "is_classmate": bool(getattr(user, "is_classmate", False)),
            "has_full_access": bool(effective_role == "admin" or has_full_access(user)),
            "ege_nickname": getattr(user, "ege_nickname", None),
            "is_tester": effective_tester,
            "flag_b": bool(getattr(user, "flag_b", False)),
            "canteen_reminder_enabled": bool(getattr(user, "canteen_reminder_enabled", False)),
            "currency_ecosystem_enabled": bool(getattr(user, "currency_ecosystem_enabled", False)),
            "coins": int(getattr(user, "coins", 100) or 0),
            "class_name": "11 «Б»",
            "notifications_enabled": user.notifications_enabled
        }

    return {
        "id": 0,
        "tg_id": 0,
        "full_name": "",
        "role": "public",
        "is_classmate": False,
        "has_full_access": False,
        "ege_nickname": None,
        "is_tester": False,
        "flag_b": False,
        "canteen_reminder_enabled": False,
        "currency_ecosystem_enabled": False,
        "coins": 0,
        "class_name": "11 «Б»",
        "notifications_enabled": False
    }


@router.get("/bells")
async def get_bells(
    response: Response,
    target_date: Optional[str] = Query(None, description="ISO format date YYYY-MM-DD"),
    session: AsyncSession = Depends(get_db_session)
):
    response.headers["Cache-Control"] = "public, max-age=604800"
    if target_date:
        query_date = date.fromisoformat(target_date)
        bells = await get_bell_schedule_for_date(session, query_date)
    else:
        bells = await get_bell_schedule_for_date(session, get_today())
    return [
        {
            "lesson_number": b.lesson_number,
            "start_time": b.start_time,
            "end_time": b.end_time,
            "break_duration": b.break_duration
        }
        for b in bells
    ]


@router.get("/subjects")
async def get_subjects(
    response: Response,
    session: AsyncSession = Depends(get_db_session)
):
    response.headers["Cache-Control"] = "public, max-age=604800"
    subjects = await get_all_subjects(session)
    return [
        {
            "id": s.id,
            "name": s.name,
            "teacher_name": s.teacher_name
        }
        for s in subjects
    ]


@router.get("/students")
async def get_students_api(session: AsyncSession = Depends(get_db_session)):
    users = await get_active_users(session)
    return [
        {
            "id": u.id,
            "tg_id": u.tg_id,
            "name": u.display_name,
            "role": u.role
        }
        for u in users
    ]


@router.get("/duty")
async def get_duty_info(session: AsyncSession = Depends(get_db_session)):
    active_group, all_groups = await get_current_duty_info(session)
    return {
        "current_group": active_group.group_number if active_group is not None else 0,
        "name": active_group.name if active_group else "Группа 0",
        "members": active_group.members if active_group else "Не назначено",
        "all_groups": [
            {
                "group_number": g.group_number,
                "name": g.name,
                "members": g.members,
                "is_active": (active_group and g.group_number == active_group.group_number)
            }
            for g in all_groups
        ]
    }


@router.get("/facts/today")
async def get_today_fact_endpoint(
    response: Response,
    target_date: Optional[str] = Query(None, description="ISO format date YYYY-MM-DD"),
    target_hour: Optional[int] = Query(None, ge=0, le=23, description="Hour of the day 0..23"),
    target_minute: Optional[int] = Query(None, ge=0, le=59, description="Minute 0..59"),
    session: AsyncSession = Depends(get_db_session)
):
    """Возвращает единый интересный факт каждые полчаса для всех учеников."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    from backend.bot.services.facts import get_or_generate_slot_fact
    query_date = None
    if target_date:
        try:
            query_date = date.fromisoformat(target_date)
        except ValueError:
            pass
    fact = await get_or_generate_slot_fact(
        session,
        target_date=query_date,
        target_hour=target_hour,
        target_minute=target_minute
    )
    return {
        "date": fact.date.isoformat(),
        "hour": fact.hour,
        "minute": fact.minute,
        "category": fact.category,
        "title": fact.title,
        "fact": fact.fact_text
    }


MEDIA_CACHE_DIR = os.path.join("data", "media_cache")


@router.get("/media/{file_id}")
async def get_telegram_media(file_id: str):
    """
    Проксирует фотографии и файлы из Telegram Bot API в Mini App,
    кэшируя их на диске для быстрого повторного доступа и защиты от лимитов.
    """
    if not file_id or len(file_id) < 5:
        raise HTTPException(status_code=400, detail="Invalid file_id")

    os.makedirs(MEDIA_CACHE_DIR, exist_ok=True)
    file_hash = hashlib.sha256(file_id.encode("utf-8")).hexdigest()
    cache_path = os.path.join(MEDIA_CACHE_DIR, f"{file_hash}.bin")
    meta_path = os.path.join(MEDIA_CACHE_DIR, f"{file_hash}.meta")

    # 1. Быстрая отдача из локального дискового кэша (0ms задержка)
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        try:
            content_type = "image/jpeg"
            filename = f"{file_hash}.jpg"
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as mf:
                    lines = mf.read().splitlines()
                    if lines:
                        content_type = lines[0]
                    if len(lines) > 1:
                        filename = lines[1]
            with open(cache_path, "rb") as cf:
                cached_bytes = cf.read()
            return Response(
                content=cached_bytes,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=604800, immutable",
                    "Content-Disposition": f"inline; filename=\"{filename}\"",
                    "X-Media-Cache": "HIT"
                }
            )
        except Exception as e_cache:
            logger.warning(f"Error reading disk media cache for {file_id}: {e_cache}")

    # 2. Получение объекта Bot
    bot = get_current_bot()
    if bot is None:
        try:
            from backend.bot.bot import create_bot_and_dispatcher
            bot, _ = create_bot_and_dispatcher()
        except Exception as e_bot:
            logger.error(f"Cannot initialize bot for media proxy: {e_bot}")
            raise HTTPException(status_code=503, detail="Бот не инициализирован")

    # 3. Запрос пути файла в Telegram API
    try:
        file_info = await bot.get_file(file_id)
        if not file_info or not file_info.file_path:
            raise HTTPException(status_code=404, detail="File path not found in Telegram")
    except TelegramAPIError as e_tg:
        logger.warning(f"Telegram API get_file error for {file_id}: {e_tg}")
        raise HTTPException(status_code=404, detail="Media not found or expired in Telegram")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get_file from Telegram for {file_id}: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch media metadata from Telegram")

    # 4. Скачивание содержимого файла
    content_bytes = None
    try:
        bio = await bot.download_file(file_info.file_path)
        if bio is not None:
            content_bytes = bio.getvalue()
    except Exception as e_dl:
        logger.warning(f"bot.download_file failed for {file_info.file_path}: {e_dl}, attempting direct download...")

    if not content_bytes:
        # Резервный канал скачивания через HTTP
        try:
            base_api = settings.TELEGRAM_API_SERVER.rstrip("/") if settings.TELEGRAM_API_SERVER else "https://api.telegram.org"
            token_to_use = getattr(bot, "token", None) or settings.BOT_TOKEN
            file_url = f"{base_api}/file/bot{token_to_use}/{file_info.file_path}"
            async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
                tg_resp = await client.get(file_url)
                if tg_resp.status_code == 200:
                    content_bytes = tg_resp.content
                else:
                    raise HTTPException(status_code=tg_resp.status_code, detail="Failed to fetch file content from Telegram")
        except HTTPException:
            raise
        except Exception as e_direct:
            logger.error(f"Direct media download failed for {file_id}: {e_direct}")
            raise HTTPException(status_code=502, detail="Failed to download media content from Telegram")

    filename = file_info.file_path.split("/")[-1]
    guessed_type, _ = mimetypes.guess_type(filename)
    content_type = guessed_type or "image/jpeg"

    # 5. Сохранение в локальный дисковый кэш
    try:
        with open(cache_path, "wb") as cf:
            cf.write(content_bytes)
        with open(meta_path, "w", encoding="utf-8") as mf:
            mf.write(f"{content_type}\n{filename}")
    except Exception as e_write:
        logger.warning(f"Failed to write media cache for {file_id}: {e_write}")

    return Response(
        content=content_bytes,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=604800, immutable",
            "Content-Disposition": f"inline; filename=\"{filename}\"",
            "X-Media-Cache": "MISS"
        }
    )
