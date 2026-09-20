from datetime import date, datetime
from typing import Optional, Dict, Any, List
import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Response, Request
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.db.models import User
from backend.api.auth import get_optional_webapp_user
from backend.db.crud import (
    get_bell_schedule, get_bell_schedule_for_date,
    get_all_subjects, get_current_duty_info, get_active_users
)
from backend.config import get_today, settings

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
            "is_tester": effective_tester,
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
        "role": "student",
        "is_tester": False,
        "canteen_reminder_enabled": False,
        "currency_ecosystem_enabled": False,
        "coins": 0,
        "class_name": "11 «Б»",
        "notifications_enabled": False
    }


@router.get("/bells")
async def get_bells(
    target_date: Optional[str] = Query(None, description="ISO format date YYYY-MM-DD"),
    session: AsyncSession = Depends(get_db_session)
):
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
async def get_subjects(session: AsyncSession = Depends(get_db_session)):
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


@router.get("/media/{file_id}")
async def get_telegram_media(file_id: str):
    """
    Проксирует фотографии и файлы из Telegram Bot API в Mini App,
    позволяя просматривать их в полном качестве и скачивать без раскрытия токена.
    """
    from backend.main import bot
    from backend.config import settings

    try:
        file_info = await bot.get_file(file_id)
        if not file_info.file_path:
            raise HTTPException(status_code=404, detail="File path not found in Telegram")

        base_api = settings.TELEGRAM_API_SERVER.rstrip("/") if settings.TELEGRAM_API_SERVER else "https://api.telegram.org"
        file_url = f"{base_api}/file/bot{settings.BOT_TOKEN}/{file_info.file_path}"
        async with httpx.AsyncClient() as client:
            tg_resp = await client.get(file_url, timeout=25.0)
            if tg_resp.status_code != 200:
                raise HTTPException(status_code=tg_resp.status_code, detail="Failed to fetch media from Telegram")

            content_type = tg_resp.headers.get("content-type", "image/jpeg")
            filename = file_info.file_path.split("/")[-1]
            return Response(
                content=tg_resp.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Content-Disposition": f"inline; filename=\"{filename}\""
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
