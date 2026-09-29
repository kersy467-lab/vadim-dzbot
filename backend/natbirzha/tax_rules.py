"""Pure calendar and period rules for NATBIRZHA mandatory company tax."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from backend.natbirzha.config import get_game_tz, nat_settings


def get_period_bounds(dt: datetime) -> tuple[datetime, datetime]:
    """Return the daily tax window ending at 11:00 in the configured tax timezone.

    Stored ledger timestamps are naive game-time values, so boundaries are
    converted back to GAME_TIMEZONE before being returned.
    """
    game_tz = get_game_tz()
    tax_tz = ZoneInfo(getattr(nat_settings, "TAX_SETTLEMENT_TIMEZONE", "Asia/Yekaterinburg"))
    game_dt = dt.replace(tzinfo=game_tz) if dt.tzinfo is None else dt.astimezone(game_tz)
    tax_dt = game_dt.astimezone(tax_tz)
    hour = max(0, min(23, int(getattr(nat_settings, "TAX_SETTLEMENT_HOUR", 11))))
    start = datetime.combine(tax_dt.date(), time(hour), tzinfo=tax_tz)
    if tax_dt < start:
        start -= timedelta(days=1)
    duration_hours = max(1, int(getattr(nat_settings, "TAX_PERIOD_HOURS", 24)))
    end = start + timedelta(hours=duration_hours)
    return (
        start.astimezone(game_tz).replace(tzinfo=None),
        end.astimezone(game_tz).replace(tzinfo=None),
    )


def tax_boundary_for_date(day: date) -> datetime:
    """Return that date's 11:00 UTC+5 close, represented in game time."""
    game_tz = get_game_tz()
    tax_tz = ZoneInfo(getattr(nat_settings, "TAX_SETTLEMENT_TIMEZONE", "Asia/Yekaterinburg"))
    hour = max(0, min(23, int(getattr(nat_settings, "TAX_SETTLEMENT_HOUR", 11))))
    boundary = datetime.combine(day, time(hour), tzinfo=tax_tz)
    return boundary.astimezone(game_tz).replace(tzinfo=None)


def period_grace_until(period_end: datetime) -> datetime:
    """Return the payment deadline; by default tax is due as the period closes."""
    grace_hours = max(0, int(getattr(nat_settings, "TAX_GRACE_HOURS", 0)))
    return period_end + timedelta(hours=grace_hours)


def period_production_deadline(period_end: datetime) -> datetime:
    """Production stops when an unpaid period tax reaches its payment deadline."""
    return period_grace_until(period_end)


def overdue_hours(period_end: datetime, now: datetime) -> int:
    """Number of complete hours overdue past the tax payment deadline."""
    deadline = period_grace_until(period_end)
    if now <= deadline:
        return 0
    return int((now - deadline).total_seconds() // 3600)


def calculate_hourly_penalty(principal: float, hours: int) -> float:
    """Calculate simple (non-compounding) penalty: +3% of principal per overdue hour."""
    if hours <= 0 or principal <= 0:
        return 0.0
    rate = float(getattr(nat_settings, "TAX_HOURLY_PENALTY_RATE", 0.03))
    return round(float(principal) * rate * hours, 2)


# Backwards compatibility adapters for daily rules
def grace_until(tax_date: date) -> date:
    return tax_date + timedelta(days=max(0, int(nat_settings.TAX_GRACE_DAYS)))


def production_deadline(tax_val: date | datetime) -> datetime:
    if isinstance(tax_val, datetime):
        return period_production_deadline(tax_val)
    return datetime.combine(grace_until(tax_val) + timedelta(days=1), time.min)


def penalty_days(tax_date: date, today: date) -> int:
    return max(0, (today - grace_until(tax_date)).days)


__all__ = [
    "get_period_bounds",
    "tax_boundary_for_date",
    "period_grace_until",
    "period_production_deadline",
    "overdue_hours",
    "calculate_hourly_penalty",
    "grace_until",
    "production_deadline",
    "penalty_days",
]
