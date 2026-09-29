"""Pure contracts for daily NATBIRZHA tax rules, 13% tax and simple overdue penalty."""

from datetime import date, datetime

from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.tax import NatTaxDaily, NatTaxPeriod
from backend.natbirzha.tax_rules import (
    calculate_hourly_penalty,
    get_period_bounds,
    grace_until,
    overdue_hours,
    penalty_days,
    period_grace_until,
    period_production_deadline,
    production_deadline,
)


def test_tax_constants_match_game_rule() -> None:
    assert nat_settings.TAX_RATE == 0.13
    assert nat_settings.TAX_PERIOD_HOURS == 24
    assert nat_settings.TAX_SETTLEMENT_HOUR == 11
    assert nat_settings.TAX_SETTLEMENT_TIMEZONE == "Asia/Yekaterinburg"
    assert nat_settings.TAX_GRACE_HOURS == 0
    assert nat_settings.TAX_HOURLY_PENALTY_RATE == 0.03
    assert nat_settings.TAX_GRACE_DAYS == 3
    assert nat_settings.TAX_DAILY_PENALTY_RATE == 0.50


def test_daily_period_bounds_and_due_time() -> None:
    # The period closes every day at 11:00 UTC+5.
    p1_start, p1_end = get_period_bounds(datetime(2026, 9, 25, 4, 30))
    assert p1_start == datetime(2026, 9, 24, 11, 0)
    assert p1_end == datetime(2026, 9, 25, 11, 0)

    # Tax becomes due as soon as its daily period closes.
    grace1 = period_grace_until(p1_end)
    assert grace1 == p1_end
    assert period_production_deadline(p1_end) == p1_end

    # Penalties count complete hours after the 11:00 daily close.
    assert overdue_hours(p1_end, datetime(2026, 9, 25, 11, 59)) == 0
    assert overdue_hours(p1_end, datetime(2026, 9, 25, 12, 0)) == 1

    # 6 hours overdue
    overdue_now = datetime(2026, 9, 25, 17, 0)
    assert overdue_hours(p1_end, overdue_now) == 6

    # Simple interest: +3% of principal per overdue hour
    penalty = calculate_hourly_penalty(1000.0, 5)
    assert penalty == 150.0  # 1000 * 0.03 * 5 = 150.0


def test_daily_period_evening_bounds() -> None:
    p2_start, p2_end = get_period_bounds(datetime(2026, 9, 25, 15, 45))
    assert p2_start == datetime(2026, 9, 25, 11, 0)
    assert p2_end == datetime(2026, 9, 26, 11, 0)

    # The daily period closes at 11:00 and tax is due then.
    grace2 = period_grace_until(p2_end)
    assert grace2 == p2_end


def test_tax_period_row_outstanding_includes_penalty_and_payments() -> None:
    row = NatTaxPeriod(
        company_id=1,
        period_start=datetime(2026, 9, 24, 11, 0),
        period_end=datetime(2026, 9, 25, 11, 0),
        taxable_profit=1000,
        principal=130,
        penalty=39,  # 10 hours * 3% = 30% * 130 = 39.0
        paid_amount=50,
    )
    assert row.total_assessed == 169
    assert row.outstanding == 119


def test_tax_deadline_starts_after_three_full_unpaid_days() -> None:
    tax_day = date(2026, 9, 21)
    assert grace_until(tax_day) == date(2026, 9, 24)
    assert production_deadline(tax_day) == datetime(2026, 9, 25, 0, 0)
    assert penalty_days(tax_day, date(2026, 9, 25)) == 1


def test_tax_row_outstanding_includes_penalty_and_payments() -> None:
    row = NatTaxDaily(
        company_id=1,
        tax_date=date(2026, 9, 21),
        taxable_profit=1000,
        principal=130,
        penalty=65,
        paid_amount=50,
    )
    assert row.total_assessed == 195
    assert row.outstanding == 145


def test_tax_period_is_daily_and_closes_at_11_in_game_time() -> None:
    assert nat_settings.TAX_PERIOD_HOURS == 24
    assert getattr(nat_settings, "TAX_SETTLEMENT_HOUR", None) == 11

    before_close_start, before_close_end = get_period_bounds(datetime(2026, 9, 25, 10, 59))
    assert before_close_start == datetime(2026, 9, 24, 11, 0)
    assert before_close_end == datetime(2026, 9, 25, 11, 0)

    at_close_start, at_close_end = get_period_bounds(datetime(2026, 9, 25, 11, 0))
    assert at_close_start == datetime(2026, 9, 25, 11, 0)
    assert at_close_end == datetime(2026, 9, 26, 11, 0)
    assert (at_close_end - at_close_start).total_seconds() == 24 * 60 * 60


def test_tax_close_remains_11_msk_plus_2_when_game_timezone_differs(monkeypatch) -> None:
    monkeypatch.setattr(nat_settings, "GAME_TIMEZONE", "Europe/Moscow")

    before_start, before_end = get_period_bounds(datetime(2026, 9, 25, 8, 59))
    assert before_start == datetime(2026, 9, 24, 9, 0)
    assert before_end == datetime(2026, 9, 25, 9, 0)

    at_start, at_end = get_period_bounds(datetime(2026, 9, 25, 9, 0))
    assert at_start == datetime(2026, 9, 25, 9, 0)
    assert at_end == datetime(2026, 9, 26, 9, 0)
