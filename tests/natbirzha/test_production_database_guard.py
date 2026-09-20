"""Production must refuse an ephemeral SQLite game database."""

from backend.db.session import validate_database_url


def run_checks() -> None:
    validate_database_url("sqlite+aiosqlite:///./data/local.db", production=False)
    validate_database_url("postgresql://user:secret@db.example/game", production=True)
    try:
        validate_database_url("sqlite+aiosqlite:///./data/bot.db", production=True)
    except RuntimeError as exc:
        assert "PostgreSQL" in str(exc)
    else:
        raise AssertionError("Production SQLite database must be rejected")
    print("NATBIRZHA production database guard: PASS")


if __name__ == "__main__":
    run_checks()
