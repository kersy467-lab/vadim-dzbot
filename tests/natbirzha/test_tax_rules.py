"""Pure contracts for the mandatory NATBIRZHA daily-profit tax."""

from datetime import date, datetime

from backend.natbirzha.config import nat_settings
from backend.natbirzha.models.tax import NatTaxDaily
from backend.natbirzha.tax_rules import grace_until, penalty_days, production_deadline


def test_tax_constants_match_game_rule() -> None:
    assert nat_settings.TAX_RATE == 0.13
    assert nat_settings.TAX_GRACE_DAYS == 3
    assert nat_settings.TAX_DAILY_PENALTY_RATE == 0.50


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
