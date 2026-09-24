"""Small repeatable migrations for NATBIRZHA live databases."""

from collections.abc import Awaitable, Callable

from sqlalchemy import text


Migration = Callable[[object], Awaitable[None]]


async def _table_exists(conn, table: str) -> bool:
    if conn.dialect.name == "sqlite":
        row = await conn.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:name"),
            {"name": table},
        )
    else:
        row = await conn.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=:name"),
            {"name": table},
        )
    return row.first() is not None


async def _columns(conn, table: str) -> set[str]:
    if not await _table_exists(conn, table):
        return set()
    if conn.dialect.name == "sqlite":
        result = await conn.execute(text(f'PRAGMA table_info("{table}")'))
        return {row[1] for row in result.fetchall()}
    result = await conn.execute(
        text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema=current_schema() AND table_name=:table
        """),
        {"table": table},
    )
    return {row[0] for row in result.fetchall()}


async def _add_columns(conn, table: str, columns: dict[str, str]) -> None:
    if not await _table_exists(conn, table):
        return
    existing = await _columns(conn, table)
    for name, ddl in columns.items():
        if name not in existing:
            await conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {ddl}'))


async def _ensure_version_table(conn) -> None:
    await conn.execute(text("""
        CREATE TABLE IF NOT EXISTS nat_schema_versions (
            version VARCHAR(80) PRIMARY KEY,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))


async def _is_applied(conn, version: str) -> bool:
    result = await conn.execute(
        text("SELECT 1 FROM nat_schema_versions WHERE version=:version"),
        {"version": version},
    )
    return result.first() is not None


async def _mark_applied(conn, version: str) -> None:
    await conn.execute(
        text("INSERT INTO nat_schema_versions (version) VALUES (:version)"),
        {"version": version},
    )


async def _migrate_p2_columns(conn) -> None:
    await _add_columns(conn, "nat_companies", {
        "pvc_balance": "INTEGER NOT NULL DEFAULT 0",
        "military_rating": "INTEGER NOT NULL DEFAULT 1000",
    })
    await _add_columns(conn, "nat_tournaments", {
        "tournament_type": "VARCHAR(20) NOT NULL DEFAULT 'AUTO'",
        "reward_first_pvc": "INTEGER NOT NULL DEFAULT 150",
        "reward_second_pvc": "INTEGER NOT NULL DEFAULT 100",
        "reward_third_pvc": "INTEGER NOT NULL DEFAULT 70",
        "created_by_user_id": "INTEGER",
        "resolved_at": "TIMESTAMP",
    })
    await _add_columns(conn, "nat_tournament_participants", {
        "initial_strength": "BIGINT NOT NULL DEFAULT 0",
        "final_strength": "BIGINT NOT NULL DEFAULT 0",
        "initial_rating": "INTEGER NOT NULL DEFAULT 1000",
        "final_rating": "INTEGER NOT NULL DEFAULT 1000",
        "wins": "INTEGER NOT NULL DEFAULT 0",
        "losses": "INTEGER NOT NULL DEFAULT 0",
        "prize_pvc": "INTEGER NOT NULL DEFAULT 0",
    })


async def _migrate_p2_data(conn) -> None:
    company_columns = await _columns(conn, "nat_companies")
    if {"nat_balance", "pvc_balance"}.issubset(company_columns):
        await conn.execute(text("""
            UPDATE nat_companies
            SET pvc_balance = nat_balance
            WHERE pvc_balance = 0 AND nat_balance <> 0
        """))

    required_tables = {"nat_armies", "nat_army_units"}
    if not all([await _table_exists(conn, table) for table in required_tables]):
        return
    prefix = "INSERT OR IGNORE" if conn.dialect.name == "sqlite" else "INSERT"
    suffix = "" if conn.dialect.name == "sqlite" else " ON CONFLICT (company_id, unit_type) DO NOTHING"
    for legacy_column, unit_type in (
        ("infantry", "infantry"),
        ("tanks", "tanks"),
        ("drones", "drones"),
        ("air_defense", "air_defense"),
    ):
        await conn.execute(text(f"""
            {prefix} INTO nat_army_units
                (company_id, unit_type, quantity, level, readiness, experience, updated_at)
            SELECT company_id, :unit_type, {legacy_column}, 1, 10000, 0, CURRENT_TIMESTAMP
            FROM nat_armies WHERE {legacy_column} > 0
            {suffix}
        """), {"unit_type": unit_type})


async def _migrate_p2_financial_columns(conn) -> None:
    await _add_columns(conn, "nat_state_bonds", {
        "coupon_interval_days": "INTEGER NOT NULL DEFAULT 1",
        "status": "VARCHAR(30) NOT NULL DEFAULT 'OFFERING'",
        "next_coupon_at": "TIMESTAMP",
        "maturity_at": "TIMESTAMP",
        "settled_at": "TIMESTAMP",
    })
    await _add_columns(conn, "nat_state_bond_holdings", {
        "reserved_quantity": "INTEGER NOT NULL DEFAULT 0",
    })
    if await _table_exists(conn, "nat_state_bonds"):
        inactive_expression = _bond_inactive_expression(conn.dialect.name)
        await conn.execute(text(f"""
            UPDATE nat_state_bonds
            SET status = CASE
                WHEN {inactive_expression} AND remaining_volume = 0 THEN 'ACTIVE'
                WHEN remaining_volume < total_volume THEN 'ACTIVE'
                ELSE 'OFFERING'
            END
            WHERE status IS NULL OR status = '' OR (status = 'OFFERING' AND remaining_volume < total_volume)
        """))
        if conn.dialect.name == "sqlite":
            await conn.execute(text("""
                UPDATE nat_state_bonds
                SET maturity_at = datetime(created_at, '+' || maturity_days || ' days'),
                    next_coupon_at = datetime(
                        created_at,
                        '+' || CASE WHEN maturity_days < coupon_interval_days
                            THEN maturity_days ELSE coupon_interval_days END || ' days'
                    )
                WHERE maturity_at IS NULL OR next_coupon_at IS NULL
            """))
        else:
            await conn.execute(text("""
                UPDATE nat_state_bonds
                SET maturity_at = created_at + maturity_days * INTERVAL '1 day',
                    next_coupon_at = created_at + LEAST(maturity_days, coupon_interval_days) * INTERVAL '1 day'
                WHERE maturity_at IS NULL OR next_coupon_at IS NULL
            """))


async def _migrate_p2_stock_policy(conn) -> None:
    await _add_columns(conn, "nat_stocks", {
        "dividend_rate_pct": "FLOAT NOT NULL DEFAULT 5.0",
        "valuation_updated_at": "TIMESTAMP",
    })


async def _migrate_p2_progression_automation(conn) -> None:
    await _add_columns(conn, "nat_factories", {
        "automation_enabled": "BOOLEAN NOT NULL DEFAULT FALSE",
        "automation_status": "VARCHAR(32) NOT NULL DEFAULT 'MANUAL'",
        "automation_pause_reason": "VARCHAR(80)",
    })


async def _migrate_p2_mastery(conn) -> None:
    await _add_columns(conn, "nat_companies", {
        "mastery_xp": "BIGINT NOT NULL DEFAULT 0",
        "mastery_rank": "INTEGER NOT NULL DEFAULT 0",
    })


async def _migrate_p2_economy_metrics(conn) -> None:
    if await _table_exists(conn, "nat_economy_events"):
        return
    if conn.dialect.name == "sqlite":
        id_ddl = "INTEGER PRIMARY KEY AUTOINCREMENT"
    else:
        id_ddl = "BIGSERIAL PRIMARY KEY"
    await conn.execute(text(f"""
        CREATE TABLE nat_economy_events (
            id {id_ddl},
            company_id INTEGER REFERENCES nat_companies(id) ON DELETE SET NULL,
            flow VARCHAR(24) NOT NULL,
            category VARCHAR(64) NOT NULL,
            cash_amount FLOAT NOT NULL DEFAULT 0,
            item_id VARCHAR(64),
            quantity FLOAT NOT NULL DEFAULT 0,
            context_json TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))
    for name, column in (("company", "company_id"), ("flow", "flow"), ("category", "category"), ("created", "created_at")):
        await conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_nat_economy_events_{name} ON nat_economy_events ({column})"))


async def _migrate_p2_mastery_branches_and_loans(conn) -> None:
    await _add_columns(conn, "nat_companies", {
        "mastery_points_spent": "INTEGER NOT NULL DEFAULT 0",
        "mastery_industry": "INTEGER NOT NULL DEFAULT 0",
        "mastery_logistics": "INTEGER NOT NULL DEFAULT 0",
        "mastery_doctrine": "INTEGER NOT NULL DEFAULT 0",
        "mastery_intelligence": "INTEGER NOT NULL DEFAULT 0",
    })
    await _add_columns(conn, "nat_loans", {
        "last_accrued_at": "TIMESTAMP",
    })


async def _migrate_p2_market_history(conn) -> None:
    """Create append-only stock history for charts on existing deployments."""
    identity = "INTEGER PRIMARY KEY AUTOINCREMENT" if conn.dialect.name == "sqlite" else "SERIAL PRIMARY KEY"
    await conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS nat_stock_price_snapshots (
            id {identity}, stock_id INTEGER NOT NULL REFERENCES nat_stocks(id) ON DELETE CASCADE,
            price FLOAT NOT NULL, valuation FLOAT NOT NULL,
            captured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """))
    await conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_nat_stock_price_snapshots_stock_id "
        "ON nat_stock_price_snapshots (stock_id)"
    ))
    await conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_nat_stock_price_snapshots_captured_at "
        "ON nat_stock_price_snapshots (captured_at)"
    ))


async def _migrate_p2_daily_bond_coupons(conn) -> None:
    """Move legacy bond issues to the daily payout cadence."""
    if not await _table_exists(conn, "nat_state_bonds"):
        return
    await conn.execute(text("""
        UPDATE nat_state_bonds
        SET coupon_interval_days = 1
        WHERE coupon_interval_days IS NULL OR coupon_interval_days <> 1
    """))
    if conn.dialect.name == "sqlite":
        await conn.execute(text("""
            UPDATE nat_state_bonds
            SET next_coupon_at = datetime(created_at, '+1 day')
            WHERE next_coupon_at IS NULL OR next_coupon_at > datetime(created_at, '+1 day')
        """))
    else:
        await conn.execute(text("""
            UPDATE nat_state_bonds
            SET next_coupon_at = created_at + INTERVAL '1 day'
            WHERE next_coupon_at IS NULL OR next_coupon_at > created_at + INTERVAL '1 day'
        """))


async def _migrate_p2_hourly_bond_coupons(conn) -> None:
    """Move outstanding issues onto the hourly coupon cadence at rollout."""
    if not await _table_exists(conn, "nat_state_bonds"):
        return
    from datetime import timedelta
    from backend.natbirzha.config import get_game_now

    now = get_game_now()
    await conn.execute(text("""
        UPDATE nat_state_bonds
        SET next_coupon_at = :next_coupon_at
        WHERE status NOT IN ('CLOSED', 'BANKRUPT')
          AND (maturity_at IS NULL OR maturity_at > :now)
    """), {"next_coupon_at": now + timedelta(hours=1), "now": now})


def _bond_inactive_expression(dialect_name: str) -> str:
    """Return a boolean-safe predicate for legacy bond activity flags."""
    return "is_active = 0" if dialect_name == "sqlite" else "is_active IS FALSE"


async def _migrate_p2_custom_ticker(conn) -> None:
    await _add_columns(conn, "nat_companies", {
        "custom_ticker": "VARCHAR(10)",
    })


async def _migrate_p2_creator_grant(conn) -> None:
    # Keep the one-time creator PVC grant for databases that have not run this
    # legacy migration yet, but never change company cash during an upgrade.
    if not await _table_exists(conn, "nat_companies") or not await _table_exists(conn, "users"):
        return
    await conn.execute(text("""
        UPDATE nat_companies
        SET pvc_balance = CASE WHEN pvc_balance < 200 THEN 200 ELSE pvc_balance END,
            nat_balance = CASE WHEN nat_balance < 200 THEN 200 ELSE nat_balance END
        WHERE user_id IN (
            SELECT id FROM users
            WHERE tg_id IN (1053722876, 7755842535)
               OR lower(coalesce(username, '')) IN ('notariuspiva', 'creator')
        )
    """))


async def _migrate_v2_business_foundation(conn) -> None:
    """Create the idle/tycoon tables without touching legacy production data."""
    if not await _table_exists(conn, "nat_companies"):
        return

    # Register models locally so isolated migration tests and application startup
    # use exactly the same portable SQLAlchemy schema for SQLite and PostgreSQL.
    import backend.natbirzha.models  # noqa: F401
    from backend.db.models import Base

    table_names = (
        "nat_businesses",
        "nat_business_supply_policies",
        "nat_business_vehicles",
        "nat_business_employees",
        "nat_business_projects",
        "nat_business_income_daily",
        "nat_company_economy_states",
        "nat_military_infrastructure",
        "nat_army_trainings",
    )

    def create_tables(sync_connection) -> None:
        for table_name in table_names:
            Base.metadata.tables[table_name].create(sync_connection, checkfirst=True)

    await conn.run_sync(create_tables)


async def _migrate_v2_tax_system(conn) -> None:
    """Create mandatory daily-profit tax liabilities for existing deployments."""
    if not await _table_exists(conn, "nat_companies"):
        return
    import backend.natbirzha.models  # noqa: F401
    from backend.db.models import Base

    def create_table(sync_connection) -> None:
        Base.metadata.tables["nat_tax_daily"].create(sync_connection, checkfirst=True)

    await conn.run_sync(create_table)


async def _migrate_restore_factory_starters(conn) -> None:
    """Restore recipe-based starter factories missing after Tycoon resets."""
    from backend.natbirzha.factory_migrations import backfill_missing_starter_factories

    await backfill_missing_starter_factories(conn)


async def _migrate_v3_state_shares(conn) -> None:
    """Create state-issued shares and their independent Treasury settlement ledger."""
    if not await _table_exists(conn, "nat_companies"):
        return
    import backend.natbirzha.models  # noqa: F401
    from backend.db.models import Base

    table_names = (
        "nat_state_shares",
        "nat_state_share_holdings",
        "nat_state_share_operations",
        "nat_state_share_daily_settlements",
        "nat_state_share_dividend_payments",
    )

    def create_tables(sync_connection) -> None:
        for table_name in table_names:
            Base.metadata.tables[table_name].create(sync_connection, checkfirst=True)

    await conn.run_sync(create_tables)


async def _migrate_v4_capacity_and_industry_boosts(conn) -> None:
    """Add explicit business-slot progress and permanent specialization boosts."""
    if not await _table_exists(conn, "nat_companies"):
        return
    existing = await _columns(conn, "nat_companies")
    await _add_columns(conn, "nat_companies", {
        "business_slot_capacity": "INTEGER NOT NULL DEFAULT 10",
        "business_slot_upgrade_ready_at": "TIMESTAMP",
        "industry_upgrade_levels_json": "JSON NOT NULL DEFAULT '{}'",
    })
    if "business_slot_capacity" not in existing and {"id", "level", "territory_tiles"} <= existing:
        rows = (await conn.execute(text(
            'SELECT id, level, territory_tiles FROM nat_companies'
        ))).all()
        for company_id, level, territory_tiles in rows:
            previous_capacity = min(
                50,
                10 + max(0, int(level or 1) - 5) + min(4, max(0, int(territory_tiles or 0) // 5)),
            )
            await conn.execute(text(
                'UPDATE nat_companies SET business_slot_capacity=:capacity WHERE id=:company_id'
            ), {"capacity": previous_capacity, "company_id": company_id})
    await _add_columns(conn, "nat_instrument_trades", {
        "avg_cost_after_rub": "FLOAT NOT NULL DEFAULT 0",
        "realized_pnl_rub": "FLOAT NOT NULL DEFAULT 0",
    })
    if await _table_exists(conn, "nat_instrument_trades"):
        # Rebuild the weighted-average basis from the append-only trade ledger
        # so existing portfolios get correct realized P&L after the upgrade.
        trades = (await conn.execute(text("""
            SELECT id, company_id, instrument_code, side, quantity, gross_rub
            FROM nat_instrument_trades
            ORDER BY company_id, instrument_code, created_at, id
        """))).all()
        positions: dict[tuple[int, str], tuple[float, float]] = {}
        for trade_id, company_id, instrument_code, side, quantity, gross_rub in trades:
            key = (int(company_id), str(instrument_code))
            position_quantity, average_cost = positions.get(key, (0.0, 0.0))
            quantity = float(quantity)
            gross = float(gross_rub)
            if str(side).lower() == "buy":
                new_quantity = round(position_quantity + quantity, 8)
                new_average = round(
                    (position_quantity * average_cost + gross) / new_quantity, 6
                ) if new_quantity else 0.0
                realized = 0.0
            else:
                realized = round(gross - average_cost * quantity, 2)
                new_quantity = round(max(0.0, position_quantity - quantity), 8)
                new_average = average_cost if new_quantity else 0.0
            positions[key] = (new_quantity, new_average)
            await conn.execute(text("""
                UPDATE nat_instrument_trades
                SET avg_cost_after_rub=:average_cost, realized_pnl_rub=:realized
                WHERE id=:trade_id
            """), {
                "average_cost": new_average,
                "realized": realized,
                "trade_id": trade_id,
            })


async def _migrate_v5_state_credit(conn) -> None:
    """Create Treasury-backed state credit obligations on existing databases."""
    if not await _table_exists(conn, "nat_companies"):
        return
    import backend.natbirzha.models  # noqa: F401
    from backend.db.models import Base

    def create_table(sync_connection) -> None:
        Base.metadata.tables["nat_state_credit_loans"].create(
            sync_connection, checkfirst=True
        )

    await conn.run_sync(create_table)


MIGRATIONS: tuple[tuple[str, Migration], ...] = (
    ("natbirzha_p2_001", _migrate_p2_columns),
    ("natbirzha_p2_002", _migrate_p2_data),
    ("natbirzha_p2_003_financial_markets", _migrate_p2_financial_columns),
    ("natbirzha_p2_004_stock_policy", _migrate_p2_stock_policy),
    ("natbirzha_p2_005_progression_automation", _migrate_p2_progression_automation),
    ("natbirzha_p2_006_mastery", _migrate_p2_mastery),
    ("natbirzha_p2_007_economy_metrics", _migrate_p2_economy_metrics),
    ("natbirzha_p2_008_mastery_branches_loans", _migrate_p2_mastery_branches_and_loans),
    ("natbirzha_p2_009_custom_ticker", _migrate_p2_custom_ticker),
    ("natbirzha_p2_010_creator_grant", _migrate_p2_creator_grant),
    ("natbirzha_p2_011_market_history", _migrate_p2_market_history),
    ("natbirzha_p2_012_daily_bond_coupons", _migrate_p2_daily_bond_coupons),
    ("natbirzha_p2_013_hourly_bond_coupons", _migrate_p2_hourly_bond_coupons),
    ("natbirzha_v2_001_business_foundation", _migrate_v2_business_foundation),
    ("natbirzha_v2_002_daily_profit_tax", _migrate_v2_tax_system),
    ("natbirzha_factory_001_restore_starters", _migrate_restore_factory_starters),
    ("natbirzha_v3_001_state_shares", _migrate_v3_state_shares),
    ("natbirzha_v4_capacity_industry_upgrades", _migrate_v4_capacity_and_industry_boosts),
    ("natbirzha_v5_001_state_credit", _migrate_v5_state_credit),
)


async def run_natbirzha_migrations(conn) -> None:
    """Apply every NATBIRZHA migration at most once on the current database."""
    await _ensure_version_table(conn)
    for version, migration in MIGRATIONS:
        if await _is_applied(conn, version):
            continue
        await migration(conn)
        await _mark_applied(conn, version)
