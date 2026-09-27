from collections import defaultdict
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from backend.natbirzha.catalogs.businesses import (
    CAREER_BUSINESSES,
    INDUSTRIES,
    JOINT_FACTORY_RECIPES,
)
from backend.natbirzha.catalogs.businesses.ai_data import AI_DATA_BUSINESSES
from backend.natbirzha.catalogs.businesses.joint_factories import INDUSTRY_PARTNERSHIPS
from backend.natbirzha.services.company_constants import SPECIALIZATION_ALIASES, VALID_SPECIALIZATIONS


def test_ai_industry_has_a_real_canonical_specialization_and_legacy_alias() -> None:
    assert "ai_data" in INDUSTRIES
    assert INDUSTRIES["ai_data"]["name"] == "ИИ и дата-центры"
    assert "forester" not in INDUSTRIES
    assert "ai_data" in VALID_SPECIALIZATIONS
    assert SPECIALIZATION_ALIASES["forester"] == "ai_data"
    assert SPECIALIZATION_ALIASES["forestry"] == "ai_data"
    assert all(
        spec["specialization"] == "ai_data"
        for business_id in AI_DATA_BUSINESSES
        for spec in (CAREER_BUSINESSES[business_id],)
    )


def test_every_industry_has_two_or_three_sensible_joint_factory_partners() -> None:
    partners: dict[str, set[str]] = defaultdict(set)
    for industry_a, industry_b in INDUSTRY_PARTNERSHIPS:
        partners[industry_a].add(industry_b)
        partners[industry_b].add(industry_a)

    assert set(partners) == set(INDUSTRIES)
    assert all(2 <= len(options) <= 3 for options in partners.values())
    assert partners["ai_data"] == {"chemist", "construction", "technoprom"}
    assert "logistics" not in partners["ai_data"]
    assert partners["brewery"] == {"agrarian", "water"}

    recipe = JOINT_FACTORY_RECIPES["joint_ai_data_technoprom"]
    assert recipe["specializations"] == ("ai_data", "technoprom")
    assert recipe["output_items"] == {
        "ai_data": "ai_compute",
        "technoprom": "components",
    }


def test_early_ai_enterprises_use_regular_water_and_no_electronic_chips() -> None:
    for business_id in ("ai_compute_node", "ml_training_center"):
        inputs = CAREER_BUSINESSES[business_id]["inputs_per_hour"]
        assert inputs.get("water", 0) > 0
        assert "clean_water" not in inputs
        assert "electronics" not in inputs
        assert all(float(quantity) > 0 for quantity in inputs.values())

    midgame_inputs = CAREER_BUSINESSES["cloud_ai_center"]["inputs_per_hour"]
    assert midgame_inputs.get("clean_water", 0) > 0


def test_ai_industry_key_migration_preserves_running_joint_factories() -> None:
    from backend.natbirzha.migrations import _migrate_v20_ai_industry_key

    async def check() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.execute(text(
                "CREATE TABLE nat_companies (id INTEGER PRIMARY KEY, specialization TEXT NOT NULL)"
            ))
            await connection.execute(text(
                "CREATE TABLE nat_factories (id INTEGER PRIMARY KEY, specialization TEXT NOT NULL)"
            ))
            await connection.execute(text(
                "CREATE TABLE nat_businesses (id INTEGER PRIMARY KEY, specialization TEXT NOT NULL)"
            ))
            await connection.execute(text(
                "CREATE TABLE nat_joint_factories (id INTEGER PRIMARY KEY, recipe_id TEXT NOT NULL)"
            ))
            await connection.execute(text("""
                CREATE TABLE nat_joint_factory_proposals (
                    id INTEGER PRIMARY KEY, recipe_id TEXT NOT NULL,
                    status TEXT NOT NULL, responded_at TIMESTAMP
                )
            """))
            for table in ("nat_companies", "nat_factories", "nat_businesses"):
                specialization = "forestry" if table == "nat_businesses" else "forester"
                await connection.execute(text(
                    f"INSERT INTO {table} (id, specialization) VALUES (1, '{specialization}')"
                ))
            await connection.execute(text(
                "INSERT INTO nat_joint_factories (id, recipe_id) VALUES (1, 'joint_brewery_forester')"
            ))
            await connection.execute(text("""
                INSERT INTO nat_joint_factory_proposals (id, recipe_id, status)
                VALUES (1, 'joint_forester_construction', 'PENDING'),
                       (2, 'joint_brewery_forester', 'PENDING')
            """))

            await _migrate_v20_ai_industry_key(connection)
            await _migrate_v20_ai_industry_key(connection)
            specializations = []
            for table in ("nat_companies", "nat_factories", "nat_businesses"):
                specializations.append(await connection.scalar(text(f"SELECT specialization FROM {table} WHERE id=1")))
            factory_recipe = await connection.scalar(text("SELECT recipe_id FROM nat_joint_factories WHERE id=1"))
            proposals = (await connection.execute(text(
                "SELECT recipe_id, status FROM nat_joint_factory_proposals ORDER BY id"
            ))).all()
        await engine.dispose()

        assert specializations == ["ai_data", "ai_data", "ai_data"]
        assert factory_recipe == "joint_brewery_forester"
        assert tuple(proposals[0]) == ("joint_ai_data_construction", "PENDING")
        assert proposals[1].status == "CANCELLED"

    asyncio.run(check())
