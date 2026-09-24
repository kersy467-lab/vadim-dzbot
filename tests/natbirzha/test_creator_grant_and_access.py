import pytest
from backend.db.models import User
from backend.natbirzha.config import nat_settings
from backend.natbirzha.services.access_control import is_creator_identity, is_creator_user, get_creator_tg_ids
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.migrations import MIGRATIONS


def test_creator_identity_allowlist():
    assert 1053722876 in get_creator_tg_ids()
    assert is_creator_identity(1053722876, None) is True
    assert is_creator_identity(None, "notariuspiva") is True
    assert is_creator_identity(None, "@notariuspiva") is True
    assert is_creator_identity(None, "creator") is True
    assert is_creator_identity(12345, "student_user") is False


def test_creator_user_model_checks():
    u_admin = User(id=1, tg_id=99999, full_name="Admin", role="admin")
    u_creator = User(id=2, tg_id=1053722876, full_name="Creator", role="student", username="notariuspiva")
    u_student = User(id=3, tg_id=88888, full_name="Student", role="student", username="vasya")

    assert is_creator_user(u_admin) is True
    assert is_creator_user(u_creator) is True
    assert is_creator_user(u_student) is False


def test_creator_starting_grant_amounts():
    import asyncio

    class DummySession:
        async def get(self, model, user_id):
            return None

        async def execute(self, stmt):
            class DummyResult:
                def scalar_one_or_none(self):
                    return None
            return DummyResult()

    async def _check():
        session = DummySession()
        cash, pvc = await CompanyService.get_starting_grant(session, 1053722876)
        assert cash == nat_settings.STARTING_CASH
        assert pvc == 200

    asyncio.run(_check())


def test_creator_grant_migration_registered():
    versions = [v for v, _ in MIGRATIONS]
    assert "natbirzha_p2_010_creator_grant" in versions
