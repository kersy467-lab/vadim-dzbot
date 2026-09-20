import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from backend.config import settings
from backend.db.models import Base


def validate_database_url(raw_url: str, *, production: bool | None = None) -> None:
    """Fail closed when a hosted deployment would use an ephemeral SQLite file."""
    is_production = production if production is not None else bool(
        os.environ.get("RENDER") or os.environ.get("RENDER_EXTERNAL_URL")
    )
    if is_production and raw_url.lower().startswith("sqlite"):
        raise RuntimeError(
            "Production NATBIRZHA requires a persistent PostgreSQL DATABASE_URL; SQLite is not allowed."
        )


def create_configured_engine():
    raw_url = os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    validate_database_url(raw_url)
    if raw_url.startswith("sqlite"):
        os.makedirs("./data", exist_ok=True)
        return create_async_engine(raw_url, echo=False, future=True, pool_pre_ping=True)
    
    # Normalize postgres URL for asyncpg
    url = raw_url
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    
    # Strip query params like sslmode or channel_binding which asyncpg handles via connect_args
    if "?" in url:
        base_url, query = url.split("?", 1)
        params = [p for p in query.split("&") if not p.startswith("sslmode") and not p.startswith("channel_binding")]
        url = base_url + ("?" + "&".join(params) if params else "")

    connect_args = {"ssl": "require"} if ("neon.tech" in url or "sslmode=require" in raw_url or "ssl=require" in raw_url) else {}
    return create_async_engine(
        url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=10,
        max_overflow=20,
        connect_args=connect_args
    )


engine = create_configured_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session

async def init_db():
    # Import domain models before create_all so every NATBIRZHA table is registered.
    import backend.natbirzha.models  # noqa: F401
    print(f"Database backend initialized: {engine.dialect.name} (connection details hidden)")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        from backend.natbirzha.migrations import run_natbirzha_migrations
        await run_natbirzha_migrations(conn)
        try:
            from sqlalchemy import text
            if engine.dialect.name == "sqlite":
                res_hw = await conn.execute(text("PRAGMA table_info(homeworks);"))
                cols_hw = [row[1] for row in res_hw.fetchall()]
                if "assigned_date" not in cols_hw:
                    await conn.execute(text("ALTER TABLE homeworks ADD COLUMN assigned_date DATE;"))

                res_u = await conn.execute(text("PRAGMA table_info(users);"))
                cols_u = [row[1] for row in res_u.fetchall()]
                if "custom_name" not in cols_u:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN custom_name VARCHAR(255);"))
                if "is_tester" not in cols_u:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN is_tester BOOLEAN DEFAULT 0;"))
                if "canteen_reminder_enabled" not in cols_u:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN canteen_reminder_enabled BOOLEAN DEFAULT 0;"))
                if "currency_ecosystem_enabled" not in cols_u:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN currency_ecosystem_enabled BOOLEAN DEFAULT 0;"))
                if "coins" not in cols_u:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN coins BIGINT DEFAULT 100;"))
                if "last_work_date" not in cols_u:
                    await conn.execute(text("ALTER TABLE users ADD COLUMN last_work_date DATE;"))

                res_dg = await conn.execute(text("PRAGMA table_info(duty_groups);"))
                cols_dg = [row[1] for row in res_dg.fetchall()]
                if "member_ids" not in cols_dg:
                    await conn.execute(text("ALTER TABLE duty_groups ADD COLUMN member_ids JSON;"))

                res_df = await conn.execute(text("PRAGMA table_info(daily_facts);"))
                cols_df = [row[1] for row in res_df.fetchall()]
                if "hour" not in cols_df:
                    await conn.execute(text("ALTER TABLE daily_facts ADD COLUMN hour INTEGER DEFAULT 0;"))
                if "minute" not in cols_df:
                    await conn.execute(text("ALTER TABLE daily_facts ADD COLUMN minute INTEGER DEFAULT 0;"))
                await conn.execute(text("DROP INDEX IF EXISTS ix_daily_facts_date;"))
                await conn.execute(text("DROP INDEX IF EXISTS uq_daily_facts_date_hour;"))
                res_gc = await conn.execute(text("PRAGMA table_info(group_chats);"))
                cols_gc = [row[1] for row in res_gc.fetchall()]
                for col in ["topic_hw_id", "topic_schedule_id", "topic_duty_id", "topic_announcements_id"]:
                    if col not in cols_gc:
                        await conn.execute(text(f"ALTER TABLE group_chats ADD COLUMN {col} INTEGER;"))
                res_nf = await conn.execute(text("PRAGMA table_info(nat_factories);"))
                cols_nf = [row[1] for row in res_nf.fetchall()]
                for col, ddl in {
                    "technology_level": "INTEGER DEFAULT 0",
                    "current_recipe": "VARCHAR(100)",
                    "cycle_started_at": "DATETIME",
                    "cycle_ready_at": "DATETIME",
                    "cycle_input_cost": "FLOAT DEFAULT 0"
                }.items():
                    if col not in cols_nf:
                        await conn.execute(text(f"ALTER TABLE nat_factories ADD COLUMN {col} {ddl};"))

                res_rc = await conn.execute(text("PRAGMA table_info(rpg_characters);"))
                cols_rc = [row[1] for row in res_rc.fetchall()]
                if "stat_points" not in cols_rc:
                    await conn.execute(text("ALTER TABLE rpg_characters ADD COLUMN stat_points INTEGER DEFAULT 2;"))
                if "rebirths" not in cols_rc:
                    await conn.execute(text("ALTER TABLE rpg_characters ADD COLUMN rebirths INTEGER DEFAULT 0;"))
                if "talent_points" not in cols_rc:
                    await conn.execute(text("ALTER TABLE rpg_characters ADD COLUMN talent_points INTEGER DEFAULT 0;"))
                if "talents" not in cols_rc:
                    await conn.execute(text("ALTER TABLE rpg_characters ADD COLUMN talents JSON DEFAULT '{}';"))
                if "boss_kills" not in cols_rc:
                    await conn.execute(text("ALTER TABLE rpg_characters ADD COLUMN boss_kills INTEGER DEFAULT 0;"))
                if "pets" not in cols_rc:
                    await conn.execute(text("ALTER TABLE rpg_characters ADD COLUMN pets JSON DEFAULT '[]';"))
                for col in ["hp_max", "mp_max", "hp", "mp", "hp_current", "current_hp"]:
                    if col in cols_rc:
                        try:
                            await conn.execute(text(f"ALTER TABLE rpg_characters DROP COLUMN {col};"))
                        except Exception:
                            pass
            else:
                await conn.execute(text("ALTER TABLE homeworks ADD COLUMN IF NOT EXISTS assigned_date DATE;"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS custom_name VARCHAR(255);"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_tester BOOLEAN DEFAULT FALSE;"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS canteen_reminder_enabled BOOLEAN DEFAULT FALSE;"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS currency_ecosystem_enabled BOOLEAN DEFAULT FALSE;"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS coins BIGINT DEFAULT 100;"))
                await conn.execute(text("ALTER TABLE users ALTER COLUMN coins TYPE BIGINT;"))
                await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_work_date DATE;"))
                await conn.execute(text("ALTER TABLE duty_groups ADD COLUMN IF NOT EXISTS member_ids JSONB;"))
                await conn.execute(text("ALTER TABLE daily_facts ADD COLUMN IF NOT EXISTS hour INTEGER DEFAULT 0;"))
                await conn.execute(text("ALTER TABLE daily_facts ADD COLUMN IF NOT EXISTS minute INTEGER DEFAULT 0;"))
                await conn.execute(text("ALTER TABLE nat_factories ADD COLUMN IF NOT EXISTS technology_level INTEGER DEFAULT 0;"))
                await conn.execute(text("ALTER TABLE nat_factories ADD COLUMN IF NOT EXISTS current_recipe VARCHAR(100);"))
                await conn.execute(text("ALTER TABLE nat_factories ADD COLUMN IF NOT EXISTS cycle_started_at TIMESTAMP;"))
                await conn.execute(text("ALTER TABLE nat_factories ADD COLUMN IF NOT EXISTS cycle_ready_at TIMESTAMP;"))
                await conn.execute(text("ALTER TABLE nat_factories ADD COLUMN IF NOT EXISTS cycle_input_cost DOUBLE PRECISION DEFAULT 0;"))
                await conn.execute(text("ALTER TABLE rpg_characters ADD COLUMN IF NOT EXISTS stat_points INTEGER DEFAULT 2;"))
                await conn.execute(text("ALTER TABLE rpg_characters ADD COLUMN IF NOT EXISTS rebirths INTEGER DEFAULT 0;"))
                await conn.execute(text("ALTER TABLE rpg_characters ADD COLUMN IF NOT EXISTS talent_points INTEGER DEFAULT 0;"))
                await conn.execute(text("ALTER TABLE rpg_characters ADD COLUMN IF NOT EXISTS talents JSONB DEFAULT '{}'::jsonb;"))
                await conn.execute(text("ALTER TABLE rpg_characters ADD COLUMN IF NOT EXISTS boss_kills INTEGER DEFAULT 0;"))
                await conn.execute(text("ALTER TABLE rpg_characters ADD COLUMN IF NOT EXISTS pets JSONB DEFAULT '[]'::jsonb;"))
                await conn.execute(text("ALTER TABLE rpg_characters ALTER COLUMN gold TYPE BIGINT;"))
                await conn.execute(text("ALTER TABLE rpg_characters ALTER COLUMN xp TYPE BIGINT;"))
                # Clean up any legacy columns or constraints in rpg_characters from earlier prototypes
                await conn.execute(text("""
                    DO $$
                    DECLARE
                        legacy_col TEXT;
                    BEGIN
                        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'rpg_characters') THEN
                            FOR legacy_col IN SELECT unnest(ARRAY['hp_max', 'mp_max', 'hp', 'mp', 'hp_current', 'current_hp', 'mana', 'max_hp', 'max_mp'])
                            LOOP
                                IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'rpg_characters' AND column_name = legacy_col) THEN
                                    EXECUTE format('ALTER TABLE rpg_characters DROP COLUMN %I CASCADE;', legacy_col);
                                END IF;
                            END LOOP;

                            FOR legacy_col IN 
                                SELECT column_name 
                                FROM information_schema.columns 
                                WHERE table_name = 'rpg_characters' 
                                  AND is_nullable = 'NO' 
                                  AND column_name NOT IN (
                                      'id', 'user_id', 'hero_class', 'level', 'xp', 'gold', 'gems',
                                      'strength', 'agility', 'intelligence', 'vitality', 'stat_points',
                                      'equipment', 'inventory', 'dungeon_floor', 'dungeon_cleared',
                                      'pvp_rating', 'pvp_wins', 'pvp_losses', 'boss_kills',
                                      'rebirths', 'talent_points', 'talents', 'pets',
                                      'created_at', 'updated_at'
                                  )
                            LOOP
                                EXECUTE format('ALTER TABLE rpg_characters ALTER COLUMN %I DROP NOT NULL;', legacy_col);
                                EXECUTE format('ALTER TABLE rpg_characters ALTER COLUMN %I SET DEFAULT 0;', legacy_col);
                            END LOOP;
                        END IF;
                    END $$;
                """))
                await conn.execute(text("ALTER TABLE group_chats ADD COLUMN IF NOT EXISTS topic_hw_id INTEGER;"))
                await conn.execute(text("ALTER TABLE group_chats ADD COLUMN IF NOT EXISTS topic_schedule_id INTEGER;"))
                await conn.execute(text("ALTER TABLE group_chats ADD COLUMN IF NOT EXISTS topic_duty_id INTEGER;"))
                await conn.execute(text("ALTER TABLE group_chats ADD COLUMN IF NOT EXISTS topic_announcements_id INTEGER;"))
                await conn.execute(text("DROP INDEX IF EXISTS ix_daily_facts_date;"))
                await conn.execute(text("DROP INDEX IF EXISTS uq_daily_facts_date_hour;"))
                await conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_daily_facts_date_hour_min ON daily_facts (date, hour, minute);"))
        except Exception as e:
            print(f"init_db migration note: {e}")

    try:
        from backend.db.crud import recalculate_bell_schedule_chain
        async with async_session_factory() as session:
            await recalculate_bell_schedule_chain(session, specific_date=None, from_lesson=2)
    except Exception as e:
        print(f"init_db bell recalculate note: {e}")

    try:
        from backend.bot.services.facts import cleanup_past_facts
        async with async_session_factory() as session:
            await cleanup_past_facts(session)
    except Exception as e:
        print(f"init_db facts cleanup note: {e}")
