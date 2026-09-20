"""The common Mini App must expose the Natbirzha entry to the configured admin."""

import asyncio

from backend.api.routers.common import get_me
from backend.config import settings
from backend.db.models import User


async def run() -> None:
    old_admin_id = settings.ADMIN_ID
    try:
        settings.ADMIN_ID = 777001
        configured_admin = User(
            id=1,
            tg_id=777001,
            full_name="Configured admin",
            role="student",
            is_tester=False,
        )
        payload = await get_me(configured_admin)
        assert payload["role"] == "admin"
        assert payload["is_tester"] is True

        regular_user = User(
            id=2,
            tg_id=777002,
            full_name="Regular student",
            role="student",
            is_tester=False,
        )
        regular_payload = await get_me(regular_user)
        assert regular_payload["role"] == "student"
        assert regular_payload["is_tester"] is False
    finally:
        settings.ADMIN_ID = old_admin_id


if __name__ == "__main__":
    asyncio.run(run())
    print("Common Mini App Natbirzha admin entry: PASS")
