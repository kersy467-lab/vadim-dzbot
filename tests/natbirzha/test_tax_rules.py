"""Pure contracts for the mandatory NATBIRZHA tax rules (12h cycle, 13% tax, 3% hourly simple penalty)."""

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
    assert nat_settings.TAX_PERIOD_HOURS == 12
    assert nat_settings.TAX_GRACE_HOURS == 0
    assert nat_settings.TAX_HOURLY_PENALTY_RATE == 0.03
    assert nat_settings.TAX_GRACE_DAYS == 3
    assert nat_settings.TAX_DAILY_PENALTY_RATE == 0.50


def test_12h_period_bounds_and_due_time() -> None:
    # Morning period: 00:00 - 12:00
    p1_start, p1_end = get_period_bounds(datetime(2026, 9, 25, 4, 30))
    assert p1_start == datetime(2026, 9, 25, 0, 0)
    assert p1_end == datetime(2026, 9, 25, 12, 0)

    # Tax becomes due as soon as its 12-hour period closes.
    grace1 = period_grace_until(p1_end)
    assert grace1 == p1_end
    assert period_production_deadline(p1_end) == p1_end

    # Penalties count only complete hours after the period closes.
    assert overdue_hours(p1_end, datetime(2026, 9, 25, 12, 0)) == 0
    assert overdue_hours(p1_end, datetime(2026, 9, 25, 12, 59)) == 0

    # 5 hours overdue
    overdue_now = datetime(2026, 9, 25, 17, 0)
    assert overdue_hours(p1_end, overdue_now) == 5

    # Simple interest: +3% of principal per overdue hour
    penalty = calculate_hourly_penalty(1000.0, 5)
    assert penalty == 150.0  # 1000 * 0.03 * 5 = 150.0


def test_12h_period_evening_bounds() -> None:
    # Evening period: 12:00 - 24:00
    p2_start, p2_end = get_period_bounds(datetime(2026, 9, 25, 15, 45))
    assert p2_start == datetime(2026, 9, 25, 12, 0)
    assert p2_end == datetime(2026, 9, 26, 0, 0)

    # The evening period closes at midnight and tax is due then.
    grace2 = period_grace_until(p2_end)
    assert grace2 == p2_end


def test_tax_period_row_outstanding_includes_penalty_and_payments() -> None:
    row = NatTaxPeriod(
        company_id=1,
        period_start=datetime(2026, 9, 25, 0, 0),
        period_end=datetime(2026, 9, 25, 12, 0),
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
