import os
from datetime import datetime, date
import zoneinfo
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    BOT_TOKEN: str = Field(default="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz", description="Telegram Bot API Token; production must override this placeholder")

    @field_validator("BOT_TOKEN", mode="before")
    @classmethod
    def validate_bot_token(cls, v):
        value = str(v or "").strip()
        return value or "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"

    ADMIN_ID: int = Field(default=0, description="Telegram ID of the primary administrator")

    @field_validator("ADMIN_ID", mode="before")
    @classmethod
    def validate_admin_id(cls, v):
        try:
            return int(v or 0)
        except Exception:
            return 0

    DEPLOY_NOTIFY_IDS: str = Field(
        default="",
        description="Comma-separated Telegram IDs to receive deploy/startup notifications in addition to ADMIN_ID"
    )

    TELEGRAM_API_SERVER: str = Field(
        default="",
        description="Custom Telegram Bot API server / reverse proxy (e.g. Cloudflare Worker)"
    )
    TELEGRAM_PROXY: str = Field(
        default="",
        description="HTTP/SOCKS proxy for Telegram Bot API"
    )
    ENABLE_BOT_POLLING: bool = Field(
        default=True,
        description="Whether to run aiogram long polling in backend"
    )
    
    PORT: int = Field(default=8000, description="Port to listen on")
    HOST: str = Field(default="0.0.0.0", description="Host to listen on")
    BASE_URL: str = Field(
        default_factory=lambda: os.environ.get("RENDER_EXTERNAL_URL") or "https://dzbot-6eid.onrender.com",
        description="Base URL of the server"
    )
    WEBAPP_URL: str = Field(
        default_factory=lambda: f"{os.environ.get('RENDER_EXTERNAL_URL', 'https://dzbot-6eid.onrender.com').rstrip('/')}/app/natbirzha",
        description="Public URL for the standalone NATBIRZHA Telegram Mini App"
    )
    AUTO_TUNNEL: bool = Field(
        default_factory=lambda: not bool(os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_URL")),
        description="Automatically start tunnel for local HTTPS if available"
    )
    
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./data/bot.db",
        description="Database connection URL. Production deployments must provide DATABASE_URL via environment."
    )

    
    NOTIFICATION_TIME_EVENING: str = Field(default="19:00", description="Time for daily evening digest (HH:MM)")
    TIMEZONE: str = Field(default="Asia/Yekaterinburg", description="Default timezone (Екатеринбург, UTC+5)")
    GEMINI_API_KEY: str = Field(
        default="",
        description="Google Gemini API Key for daily facts"
    )

settings = Settings()


def get_natbirzha_webapp_url(url: str | None = None) -> str:
    """Normalize a public service URL to the dedicated NATBIRZHA Mini App.

    Old Render variables used the parent school app at ``/app``.  Telegram's
    menu must point straight to the game, otherwise it opens the unrelated
    timetable Mini App or a route that later resolves to a 404.
    """
    base = str(url or settings.WEBAPP_URL or settings.BASE_URL or "").strip().rstrip("/")
    if base.endswith("/app/natbirzha"):
        return base
    if base.endswith("/app"):
        return f"{base}/natbirzha"
    return f"{base}/app/natbirzha"

def get_deploy_notify_ids() -> set[int]:
    """Returns set of Telegram IDs to receive deploy/startup notifications."""
    ids: set[int] = set()
    if settings.ADMIN_ID:
        try:
            ids.add(int(settings.ADMIN_ID))
        except (ValueError, TypeError):
            pass
    raw = getattr(settings, "DEPLOY_NOTIFY_IDS", "") or ""
    for token in str(raw).split(","):
        token = token.strip()
        if not token:
            continue
        try:
            ids.add(int(token))
        except ValueError:
            pass
    return ids

def get_today() -> date:
    """Returns today's date according to the configured timezone (Asia/Yekaterinburg)"""
    try:
        tz = zoneinfo.ZoneInfo(settings.TIMEZONE)
        return datetime.now(tz).date()
    except Exception:
        return date.today()

def get_current_date_and_hour() -> tuple[date, int]:
    """Returns (today_date, current_hour 0..23) according to configured timezone (Asia/Yekaterinburg)"""
    try:
        tz = zoneinfo.ZoneInfo(settings.TIMEZONE)
        now = datetime.now(tz)
        return now.date(), now.hour
    except Exception:
        now = datetime.now()
        return now.date(), now.hour

def get_current_date_hour_minute() -> tuple[date, int, int]:
    """Returns (today_date, current_hour, current_minute_slot 0 or 30) according to configured timezone (Asia/Yekaterinburg)"""
    try:
        tz = zoneinfo.ZoneInfo(settings.TIMEZONE)
        now = datetime.now(tz)
        min_slot = 30 if now.minute >= 30 else 0
        return now.date(), now.hour, min_slot
    except Exception:
        now = datetime.now()
        min_slot = 30 if now.minute >= 30 else 0
        return now.date(), now.hour, min_slot


