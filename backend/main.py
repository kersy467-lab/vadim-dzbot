import os
import sys

# Ensure root directory is always in sys.path regardless of how main.py is called
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Ensure console supports UTF-8 emojis without crashing on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.config import settings
from backend.db.session import init_db, async_session_factory
from backend.db.seed import seed_initial_data
from backend.api.routes import api_router
from backend.bot.bot import create_bot_and_dispatcher
from backend.bot.services.scheduler import setup_scheduler

# Configure logging with console and file handler
from logging.handlers import RotatingFileHandler
os.makedirs("data", exist_ok=True)
_file_handler = RotatingFileHandler(
    os.path.join("data", "bot.log"),
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8"
)
_file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        _file_handler
    ]
)
logger = logging.getLogger("botdz")

bot, dp = create_bot_and_dispatcher()
polling_task: asyncio.Task | None = None

from backend.bot.services.commands import setup_bot_commands

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("Initializing database...")
    await init_db()

    async with async_session_factory() as session:
        await seed_initial_data(session)
        from backend.db.crud.homework import cleanup_past_homework_statuses
        cleaned = await cleanup_past_homework_statuses(session)
        if cleaned > 0:
            logger.info(f"Startup checklist cleanup: deleted {cleaned} obsolete records from past homework.")

        # Clean up any obsolete schedules on or before 2026-09-01
        from datetime import date
        from sqlalchemy import delete
        from backend.db.models import Schedule
        res_del = await session.execute(
            delete(Schedule).where(Schedule.specific_date <= date(2026, 9, 1))
        )
        if res_del.rowcount and res_del.rowcount > 0:
            await session.commit()
            logger.info(f"Purged {res_del.rowcount} obsolete schedule records on or before 2026-09-01.")

        # Automatic startup world reset is removed so companies persist across deploys.
        # Admins can trigger world reset on-demand via the Creator Moderation panel.

        # Sync pug prank setting from DB so it survives deploys
        try:
            from backend.db.crud.duty import get_class_setting, set_class_setting
            from backend.bot.handlers.admin.pug_prank import set_pug_mode, is_pug_mode_active
            pug_val = await get_class_setting(session, "pug_prank_active")
            if pug_val is not None:
                set_pug_mode(pug_val == "1")
            else:
                await set_class_setting(session, "pug_prank_active", "1" if is_pug_mode_active() else "0")
        except Exception as e_pug:
            logger.warning(f"Could not sync pug mode setting on startup: {e_pug}")

    logger.info("Setting up background scheduler...")
    setup_scheduler(bot)

    # Check duty notification on startup
    from backend.bot.services.notifier import check_and_send_duty_reminder
    asyncio.create_task(check_and_send_duty_reminder(bot))

    # Catch-up evening digest on startup if 19:00 has already passed today
    async def check_and_send_evening_digest_on_startup():
        try:
            await asyncio.sleep(3)
            from backend.config import get_current_date_and_hour
            today, current_hour = get_current_date_and_hour()
            if today.isoweekday() in (5, 6):
                # По пятницам и субботам вечером уведомления не отправляются
                return
            if current_hour >= 19:
                from backend.db.crud import get_class_setting, set_class_setting
                async with async_session_factory() as session:
                    last_sent = await get_class_setting(session, "last_evening_digest_date")
                    if last_sent != str(today):
                        logger.info(f"Startup: 19:00 passed and evening digest not yet sent for {today}. Sending now...")
                        await set_class_setting(session, "last_evening_digest_date", str(today))
                        from backend.bot.services.notifier import send_evening_digest
                        await send_evening_digest(bot)
                        logger.info(f"Startup: evening digest for {today} sent successfully.")
        except Exception as ex:
            logger.warning(f"Error checking evening digest on startup: {ex}")

    asyncio.create_task(check_and_send_evening_digest_on_startup())

    # Catch-up birthday greetings on startup if not yet checked/sent today
    async def check_and_send_birthdays_on_startup():
        try:
            await asyncio.sleep(4)
            from backend.bot.services.birthdays import check_and_send_birthday_greetings
            await check_and_send_birthday_greetings(bot)
        except Exception as ex:
            logger.warning(f"Error checking birthday greetings on startup: {ex}")

    asyncio.create_task(check_and_send_birthdays_on_startup())

    # Start HTTPS Tunnel in background once uvicorn server is listening
    port = int(os.environ.get("PORT", settings.PORT))
    if getattr(settings, "AUTO_TUNNEL", True) and not settings.WEBAPP_URL.startswith("https://"):
        async def _init_tunnel():
            await asyncio.sleep(1.0)
            try:
                from backend.tunnel import start_tunnel, register_url_change_callback

                async def _on_tunnel_update(new_url: str):
                    settings.WEBAPP_URL = f"{new_url}/app"
                    settings.BASE_URL = new_url
                    logger.info(f"Dynamic tunnel updated: {settings.WEBAPP_URL}")
                    try:
                        await setup_bot_commands(bot)
                    except Exception as ex:
                        logger.warning(f"Could not reconfigure bot commands on tunnel change: {ex}")

                register_url_change_callback(_on_tunnel_update)

                tunnel_url = await start_tunnel(port)
                if tunnel_url:
                    settings.WEBAPP_URL = f"{tunnel_url}/app"
                    settings.BASE_URL = tunnel_url
                    print("\n" + "=" * 64)
                    print(f"🚀 ПУБЛИЧНЫЙ HTTPS ТУННЕЛЬ АКТИВЕН!")
                    print(f"📱 Ссылка на Mini App: {settings.WEBAPP_URL}")
                    print("=" * 64 + "\n", flush=True)
                    try:
                        await setup_bot_commands(bot)
                    except Exception as ex:
                        logger.warning(f"Could not update bot commands on initial tunnel start: {ex}")
            except Exception as e:
                logger.warning(f"Could not start tunnel: {e}")

        asyncio.create_task(_init_tunnel())

    # Start Aiogram polling and register command hints in background task
    global polling_task
    if settings.ENABLE_BOT_POLLING and settings.BOT_TOKEN and not settings.BOT_TOKEN.startswith("1234567890:ABCdef"):
        async def init_telegram_bot():
            try:
                logger.info("Registering Telegram command autocomplete hints and menu button...")
                await asyncio.wait_for(setup_bot_commands(bot), timeout=20.0)
            except Exception as e:
                logger.warning(f"Could not setup Telegram commands (offline or timeout): {e}")
            logger.info("Starting Telegram Bot long-polling...")
            while True:
                try:
                    if bot.session and getattr(bot.session, "closed", False):
                        from aiogram.client.session.aiohttp import AiohttpSession
                        bot.session = AiohttpSession()
                    await dp.start_polling(bot, handle_signals=False, close_bot_session=False)
                    break
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.warning(f"Telegram polling error (retrying in 5s): {e}")
                    await asyncio.sleep(5)


        polling_task = asyncio.create_task(init_telegram_bot())

        # Send deploy completion notification to configured recipients (ADMIN_ID and DEPLOY_NOTIFY_IDS)
        from backend.bot.services.startup_notify import send_startup_notifications
        asyncio.create_task(send_startup_notifications(bot))
    else:
        logger.warning("BOT_TOKEN is not configured or is a placeholder! Telegram bot polling will not start.")

    yield

    # --- Shutdown ---
    logger.info("Shutting down...")
    try:
        from backend.tunnel import stop_tunnel
        await stop_tunnel()
    except Exception:
        pass
    if polling_task:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
    if bot.session:
        await bot.session.close()

app = FastAPI(
    title="Class Bot & Mini App API",
    description="Backend for School / Class Telegram Bot & WebApp",
    version="1.0.0",
    lifespan=lifespan
)

# CORS & GZip middleware
from starlette.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public EGE Arena accounts are blocked from legacy/private API surfaces.
from backend.api.public_access import enforce_api_access
app.middleware("http")(enforce_api_access)

# Include API routes
app.include_router(api_router)

# Healthcheck for Cloudflare Worker & Render
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "class-bot"}

@app.get("/favicon.ico")
async def favicon():
    return Response(content=b"", media_type="image/x-icon")


class SmartCacheStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        norm_path = str(path).replace("\\", "/").lower()
        if norm_path.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".ico", ".woff2", ".woff", ".mp3")):
            response.headers["Cache-Control"] = "public, max-age=604800, immutable"
        elif norm_path.endswith((".js", ".css")):
            qs = scope.get("query_string", b"")
            if isinstance(qs, bytes):
                qs = qs.decode("utf-8", errors="ignore")
            if "v=" in qs:
                response.headers["Cache-Control"] = "public, max-age=604800, immutable"
            else:
                response.headers["Cache-Control"] = "no-cache"
        else:
            response.headers["Cache-Control"] = "no-cache"
        if "pragma" in response.headers:
            del response.headers["pragma"]
        return response


# Static files for Telegram Mini App
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", SmartCacheStaticFiles(directory=frontend_path), name="static")

_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}

def _serve_page(filename: str, fallback_msg: str):
    file_path = os.path.join(frontend_path, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, headers=_NO_CACHE_HEADERS)
    return {"message": fallback_msg}

@app.get("/")
@app.get("/app")
@app.get("/app/")
@app.get("/miniapp")
@app.get("/miniapp/")
@app.get("/mini-app")
@app.get("/mini-app/")
@app.get("/webapp")
@app.get("/webapp/")
@app.get("/web-app")
@app.get("/web-app/")
@app.get("/game")
@app.get("/game/")
@app.get("/games")
@app.get("/games/")
@app.get("/play")
@app.get("/play/")
@app.get("/bot")
@app.get("/bot/")
@app.get("/index.html")
@app.get("/app/index.html")
async def serve_webapp():
    return _serve_page("index.html", "Frontend not found")

@app.get("/natbirzha")
@app.get("/natbirzha/")
@app.get("/natbirzha/index.html")
@app.get("/app/natbirzha")
@app.get("/app/natbirzha/")
@app.get("/app/natbirzha/index.html")
@app.get("/birzha")
@app.get("/birzha/")
@app.get("/app/birzha")
@app.get("/app/birzha/")
@app.get("/natbirzha-app")
@app.get("/natbirzha_app")
async def serve_natbirzha():
    return _serve_page(os.path.join("natbirzha", "index.html"), "Natbirzha frontend not found")

@app.get("/{full_path:path}")
async def catch_all_frontend(full_path: str):
    # Preserve standard 404 for unmapped API or static asset endpoints
    if full_path.startswith("api/") or full_path.startswith("static/"):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not Found")
    lower = full_path.lower()
    if "natbirzha" in lower or "birzha" in lower:
        return _serve_page(os.path.join("natbirzha", "index.html"), "Natbirzha frontend not found")
    return _serve_page("index.html", "Frontend not found")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", settings.PORT))
    uvicorn.run(
        app,
        host=settings.HOST,
        port=port,
        log_level="info"
    )

