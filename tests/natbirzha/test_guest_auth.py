"""Guest browser identities are stable and cannot collide with Telegram IDs."""

from backend.natbirzha.services.auth_service import guest_tg_id_from_token


def run_checks() -> None:
    token = "browser-session-123"
    first = guest_tg_id_from_token(token)
    assert first == guest_tg_id_from_token(token)
    assert first < 0
    assert first != guest_tg_id_from_token("browser-session-456")
    print("NATBIRZHA guest browser auth checks: PASS")


if __name__ == "__main__":
    run_checks()
