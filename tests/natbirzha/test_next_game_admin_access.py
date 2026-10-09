import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base, User
import backend.natbirzha.models  # noqa: F401
from backend.db.session import get_db_session
from backend.natbirzha.api.next_game_routes import router as next_game_router
from backend.natbirzha.config import nat_settings
from backend.natbirzha.services.auth_service import get_strict_natbirzha_user


def test_next_game_endpoints_are_admin_only_and_save_a_separate_preview():
    async def check():
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        previous_ids = nat_settings.CREATOR_TG_IDS
        actor = {'user': User(id=1, tg_id=990001, username='player', full_name='Player', role='student')}

        async def db_session():
            async with sessions() as session:
                yield session

        async def current_user():
            return actor['user']

        app = FastAPI()
        app.include_router(next_game_router, prefix='/api/natbirzha')
        app.dependency_overrides[get_db_session] = db_session
        app.dependency_overrides[get_strict_natbirzha_user] = current_user
        nat_settings.CREATOR_TG_IDS = '990001'
        try:
            with TestClient(app) as client:
                actor['user'] = User(id=2, tg_id=990002, username='guest', full_name='Guest', role='student')
                assert client.get('/api/natbirzha/next-game/map').status_code == 403
                forbidden = client.post('/api/natbirzha/next-game/company', json={'name': 'No Access'})
                assert forbidden.status_code == 403

                actor['user'] = User(id=1, tg_id=990001, username='owner', full_name='Owner', role='student')
                created = client.post('/api/natbirzha/next-game/company', json={'name': 'Private Test Corp'})
                assert created.status_code == 200
                sector = client.put('/api/natbirzha/next-game/sector', json={'sector_id': 'bank'})
                branch = client.put('/api/natbirzha/next-game/branch', json={'branch_id': 'corporate'})
                snapshot = client.get('/api/natbirzha/next-game/map')
                assert sector.json()['company']['sector_id'] == 'bank'
                assert branch.json()['company']['branch_path'] == ['corporate']
                assert snapshot.json()['company']['name'] == 'Private Test Corp'
        finally:
            nat_settings.CREATOR_TG_IDS = previous_ids
            await engine.dispose()

    asyncio.run(check())
