"""Pure calendar and period rules for NATBIRZHA mandatory company tax."""

from datetime import date, datetime, time, timedelta

from backend.natbirzha.config import nat_settings


def get_period_bounds(dt: datetime) -> tuple[datetime, datetime]:
    """Return [start, end) of the 12-hour tax period containing dt."""
    norm = dt.replace(minute=0, second=0, microsecond=0)
    if norm.hour < 12:
        start = datetime.combine(norm.date(), time(0, 0, 0))
        end = datetime.combine(norm.date(), time(12, 0, 0))
    else:
        start = datetime.combine(norm.date(), time(12, 0, 0))
        end = datetime.combine(norm.date() + timedelta(days=1), time(0, 0, 0))
    return start, end


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
    "period_grace_until",
    "period_production_deadline",
    "overdue_hours",
    "calculate_hourly_penalty",
    "grace_until",
    "production_deadline",
    "penalty_days",
]
