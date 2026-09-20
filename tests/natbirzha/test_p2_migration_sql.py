"""Regression checks for dialect-safe P2 financial migration SQL."""

from backend.natbirzha.migrations import _bond_inactive_expression


def run_checks() -> None:
    assert _bond_inactive_expression("sqlite") == "is_active = 0"
    assert _bond_inactive_expression("postgresql") == "is_active IS FALSE"
    print("NATBIRZHA P2 migration SQL checks: PASS")


if __name__ == "__main__":
    run_checks()
