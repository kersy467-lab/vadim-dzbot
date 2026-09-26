"""Availability rules for the rare brewery specialization."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.db.models import Base
import backend.natbirzha.models  # noqa: F401
from backend.natbirzha.catalogs.businesses import INDUSTRIES
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.services import industry_selection_service as selection_module
from backend.natbirzha.services.industry_selection_service import IndustrySelectionService
from backend.natbirzha.services.company_service import CompanyService
from backend.natbirzha.services import company_service as company_module


def _run_check(check) -> None:
    async def run() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with sessions() as session:
                await check(session)
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_brewery_unlocks_after_every_other_catalog_industry_has_a_company() -> None:
    async def check(session) -> None:
        other_industries = [industry_id for industry_id in INDUSTRIES if industry_id != "brewery"]
        assert other_industries
        missing_id = other_industries[-1]

        # Multiple firms in one ordinary industry do not make up for an empty one.
        company_specs = other_industries[:-1] + [other_industries[0]]
        for index, specialization in enumerate(company_specs, start=1):
            session.add(NatCompany(
                user_id=970_000 + index,
                name=f"Industry {index}",
                specialization=specialization,
            ))
        await session.flush()

        locked = await IndustrySelectionService.get_availability(session, "brewery")
        assert locked["available"] is False
        assert locked["missing_industries"] == [missing_id]
        assert INDUSTRIES[missing_id]["name"] in locked["reason"]

        session.add(NatCompany(
            user_id=970_100,
            name="Last Ordinary Industry",
            specialization=missing_id,
        ))
        await session.flush()

        unlocked = await IndustrySelectionService.get_availability(session, "brewery")
        assert unlocked["available"] is True
        assert unlocked["missing_industries"] == []
        assert unlocked["company_count"] == 0
        assert "доступна" in unlocked["reason"].lower()

    _run_check(check)


def test_regular_industries_do_not_inherit_brewery_unlock_gate() -> None:
    async def check(session) -> None:
        industry_id = next(key for key in INDUSTRIES if key != "brewery")
        result = await IndustrySelectionService.get_availability(session, industry_id)
        assert result["available"] is True
        assert result["missing_industries"] == []

    _run_check(check)


def test_unknown_specialization_has_a_clear_unavailable_reason() -> None:
    async def check(session) -> None:
        result = await IndustrySelectionService.get_availability(session, "not_an_industry")
        assert result["available"] is False
        assert result["reason"]
        assert "неизвест" in result["reason"].lower()

    _run_check(check)


def test_selection_options_follow_industry_catalog_and_explain_brewery_lock(monkeypatch) -> None:
    catalog = {**INDUSTRIES, "brewery": {"name": "Пивоварня"}}
    monkeypatch.setattr(selection_module, "INDUSTRIES", catalog)

    async def check(session) -> None:
        options = await IndustrySelectionService.get_selection_options(session)
        assert [item["specialization"] for item in options] == list(catalog)
        brewery = next(item for item in options if item["specialization"] == "brewery")
        assert brewery["available"] is False
        assert brewery["missing_industries"] == [item for item in catalog if item != "brewery"]
        assert "Пивоварня" in brewery["reason"]

    _run_check(check)


def test_company_creation_and_respec_enforce_the_server_side_brewery_gate(monkeypatch) -> None:
    async def no_bootstrap(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(company_module, "bootstrap_company_state", no_bootstrap)

    async def check(session) -> None:
        baseline_company = NatCompany(
            user_id=980_001, name="Possible Brewery", specialization="miner", cash=1_000_000
        )
        session.add(baseline_company)
        await session.flush()

        try:
            await CompanyService.create_company(
                session, 980_002, "Early Brewery", "brewery", commit=False
            )
        except ValueError as exc:
            assert "хотя бы одна компания" in str(exc).lower()
        else:
            raise AssertionError("A brewery must be rejected while another sector is empty")

        try:
            await CompanyService.change_specialization(
                session, baseline_company, "brewery", commit=False
            )
        except ValueError as exc:
            assert "хотя бы одна компания" in str(exc).lower()
        else:
            raise AssertionError("Respec must enforce the same brewery gate as company creation")

        for index, specialization in enumerate(
            [industry for industry in INDUSTRIES if industry != "brewery"], start=1
        ):
            if specialization == baseline_company.specialization:
                continue
            session.add(NatCompany(
                user_id=981_000 + index,
                name=f"Covered {index}",
                specialization=specialization,
                cash=1_000_000,
            ))
        await session.flush()

        created = await CompanyService.create_company(
            session, 982_000, "Second Brewery", "brewery", commit=False
        )
        assert created.specialization == "brewery"

        result = await CompanyService.change_specialization(
            session, baseline_company, "brewery", commit=False
        )
        assert result["new_specialization"] == "brewery"

    _run_check(check)
