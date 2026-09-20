from datetime import date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db_session
from backend.db.models import User
from backend.api.auth import get_optional_webapp_user, get_current_webapp_user
from backend.db.crud import (
    get_homework_for_date, get_user_homework_status,
    toggle_homework_completion
)
from backend.config import get_today

router = APIRouter(tags=["homework"])


@router.get("/homework")
async def get_homework(
    target_date: Optional[str] = Query(None, description="ISO format date YYYY-MM-DD"),
    user: Optional[User] = Depends(get_optional_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    if target_date:
        query_date = date.fromisoformat(target_date)
    else:
        query_date = get_today()

    homeworks = await get_homework_for_date(session, query_date)

    result = []
    for hw in homeworks:
        status = None
        if user:
            status = await get_user_homework_status(session, user.id, hw.id)
        enriched_atts = []
        for a in (hw.attachments or []):
            item = dict(a)
            if item.get("file_id"):
                item["url"] = f"/api/media/{item['file_id']}"
            enriched_atts.append(item)

        result.append({
            "id": hw.id,
            "subject_name": hw.subject.name,
            "due_date": hw.due_date.isoformat(),
            "title": hw.title,
            "description": hw.description,
            "attachments": enriched_atts,
            "is_completed": status.is_completed if status else False
        })
    return result


@router.post("/homework/{hw_id}/toggle")
async def toggle_homework(
    hw_id: int,
    user: User = Depends(get_current_webapp_user),
    session: AsyncSession = Depends(get_db_session)
):
    new_status = await toggle_homework_completion(session, user.id, hw_id)
    return {"id": hw_id, "is_completed": new_status}
