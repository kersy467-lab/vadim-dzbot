import os
from fastapi import APIRouter
from backend.config import settings

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/status")
async def get_debug_status():
    polling_info = "not_started"
    try:
        import backend.main as main_mod
        task = getattr(main_mod, "polling_task", None)
        if task:
            if task.done():
                try:
                    exc = task.exception()
                    polling_info = f"done_exception: {exc}" if exc else "done_no_exception"
                except Exception as ex:
                    polling_info = f"done_status_error: {ex}"
            elif task.cancelled():
                polling_info = "cancelled"
            else:
                polling_info = "running"
    except Exception as e:
        polling_info = f"error: {e}"

    recent_logs = []
    log_path = os.path.join("data", "bot.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                recent_logs = [line.strip() for line in f.readlines()[-40:]]
        except Exception as e:
            recent_logs = [f"log_read_error: {e}"]

    return {
        "status": "ok",
        "bot_token_set": bool(settings.BOT_TOKEN and ":" in settings.BOT_TOKEN),
        "bot_token_prefix": settings.BOT_TOKEN[:10] if settings.BOT_TOKEN else "",
        "admin_id": settings.ADMIN_ID,
        "base_url": settings.BASE_URL,
        "webapp_url": settings.WEBAPP_URL,
        "enable_bot_polling": settings.ENABLE_BOT_POLLING,
        "polling_task": polling_info,
        "recent_logs": recent_logs
    }
