"""Pure calendar rules for NATBIRZHA mandatory company tax."""

from datetime import date, datetime, time, timedelta

from backend.natbirzha.config import nat_settings


def grace_until(tax_date: date) -> date:
    return tax_date + timedelta(days=max(0, int(nat_settings.TAX_GRACE_DAYS)))


def production_deadline(tax_date: date) -> datetime:
    return datetime.combine(grace_until(tax_date) + timedelta(days=1), time.min)


def penalty_days(tax_date: date, today: date) -> int:
    return max(0, (today - grace_until(tax_date)).days)


__all__ = ["grace_until", "production_deadline", "penalty_days"]
