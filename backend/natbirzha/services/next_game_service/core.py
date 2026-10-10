"""Company lifecycle and treasury ledger helpers for NATBIRZHA 2.0."""
from datetime import datetime, timedelta
from typing import Any
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from backend.natbirzha.models.next_game import (
    NatNextGameCompany, NatNextGameFacility, NatNextGameLedger,
    NatNextGameTreasury,
)
from backend.natbirzha.next_game_catalog import find_next_game_branch, find_next_game_sector, get_next_game_items
from .common import (
    MAX_FACILITY_LEVEL, STARTING_COMPANY_CASH,
    TREASURY_START_CASH, TREASURY_START_STOCK, _utcnow,
    facility_output_multiplier, facility_upgrade_cost,
)

class NextGameCoreMixin:
    @classmethod
    async def create_company(
        cls, session: AsyncSession, owner_tg_id: int, name: str
    ) -> dict[str, Any]:
        safe_name = str(name or "").strip()[:80]
        if len(safe_name) < 2:
            raise ValueError("Название компании должно содержать минимум два символа")
        await cls._lock_treasury_for_sqlite(session)
        company = await session.scalar(
            select(NatNextGameCompany).where(NatNextGameCompany.owner_tg_id == owner_tg_id)
            .with_for_update()
        )
        if company is None:
            treasury = await cls._treasury(session)
            # The singleton treasury lock serializes first-time company creation;
            # recheck after acquiring it so a retry cannot mint a second grant.
            company = await session.scalar(
                select(NatNextGameCompany).where(
                    NatNextGameCompany.owner_tg_id == owner_tg_id
                ).with_for_update().execution_options(populate_existing=True)
            )
            if company is not None:
                return {"success": True, "company": cls.snapshot_company(company)}
            if await cls._available_treasury_cash(session, treasury) < STARTING_COMPANY_CASH:
                raise ValueError("В казне 2.0 недостаточно средств на стартовый капитал")
            company = NatNextGameCompany(
                owner_tg_id=int(owner_tg_id), name=safe_name, branch_path=[],
                cash=STARTING_COMPANY_CASH,
                level=1, xp=0,
            )
            treasury.cash = round(float(treasury.cash) - STARTING_COMPANY_CASH, 8)
            session.add(company)
            await session.flush()
            session.add(cls._ledger(
                company.id, "STARTUP_CAPITAL", STARTING_COMPANY_CASH,
                -STARTING_COMPANY_CASH,
            ))
            await session.flush()
        return {"success": True, "company": cls.snapshot_company(company)}

    @classmethod
    async def select_sector(
        cls, session: AsyncSession, owner_tg_id: int, sector_id: str
    ) -> dict[str, Any]:
        if find_next_game_sector(sector_id) is None:
            raise ValueError("Отрасль отсутствует на карте 2.0")
        await cls._lock_treasury_for_sqlite(session)
        company = await cls._owned_company(session, owner_tg_id)
        if company.sector_id and company.sector_id != sector_id:
            raise ValueError("Стартовая отрасль уже выбрана и сохранена")
        company.sector_id = sector_id
        await session.flush()
        return {"success": True, "company": cls.snapshot_company(company)}

    @classmethod
    async def select_branch(
        cls, session: AsyncSession, owner_tg_id: int, branch_id: str
    ) -> dict[str, Any]:
        await cls._lock_treasury_for_sqlite(session)
        company = await cls._owned_company(session, owner_tg_id)
        if not company.sector_id:
            raise ValueError("Сначала выберите стартовую корпорацию")
        sector = find_next_game_sector(company.sector_id)
        branch = next((item for item in sector["branches"] if item["id"] == branch_id), None)
        if branch is None:
            raise ValueError("Эта ветка не относится к выбранной корпорации")
        path = list(company.branch_path or [])
        if not branch["is_starting_branch"] and not path:
            raise ValueError("Эта производственная ветка открывается позже по карте, а не на старте")
        if path and path[0] != branch_id:
            raise ValueError("Первая ветка развития уже выбрана")
        if not path:
            company.branch_path = [branch_id]
            company.updated_at = _utcnow()
        await session.flush()
        return {"success": True, "company": cls.snapshot_company(company)}

    @classmethod
    async def advance_branch(
        cls, session: AsyncSession, owner_tg_id: int, branch_id: str
    ) -> dict[str, Any]:
        await cls._lock_treasury_for_sqlite(session)
        company = await cls._owned_company(session, owner_tg_id)
        path = list(company.branch_path or [])
        if not path:
            raise ValueError("Сначала выберите стартовую производственную ветку")
        target = find_next_game_branch(branch_id)
        if target is None:
            raise ValueError("Эта ветка отсутствует на карте развития")
        required_level = max(len(path) + 1, int(target.get("requirements", {}).get("company_level", 1)))
        if int(company.level) < required_level:
            raise ValueError(f"Для следующей развилки нужен уровень компании {required_level}")
        previous = find_next_game_branch(path[-1])
        if previous is None or branch_id not in previous["next_branch_ids"]:
            raise ValueError("Эта ветка не открывается из текущего маршрута")
        if branch_id in path:
            raise ValueError("Эта ветка уже есть в маршруте")
        previous_facility = await session.scalar(select(NatNextGameFacility.id).where(
            NatNextGameFacility.company_id == company.id,
            NatNextGameFacility.branch_id == path[-1],
        ))
        from backend.natbirzha.services.next_game_fusion_service import NextGameFusionService
        if previous_facility is None and not await NextGameFusionService.consumed_branch(session, company.id, path[-1]):
            raise ValueError("Сначала постройте завод предыдущего этапа")
        company.branch_path = [*path, branch_id]
        company.updated_at = _utcnow()
        await session.flush()
        return {
            "success": True, "required_level": required_level,
            "company": cls.snapshot_company(company),
        }

    @classmethod
    async def build_facility(
        cls, session: AsyncSession, owner_tg_id: int, *,
        branch_id: str | None = None, now: datetime | None = None,
    ) -> dict[str, Any]:
        await cls._lock_treasury_for_sqlite(session)
        company = await cls._owned_company(session, owner_tg_id)
        if not company.branch_path:
            raise ValueError("Сначала выберите производственную ветку")
        target_branch_id = branch_id or company.branch_path[-1]
        if target_branch_id not in company.branch_path:
            raise ValueError("Эта ветка ещё не открыта")
        from backend.natbirzha.services.next_game_fusion_service import NextGameFusionService
        if await NextGameFusionService.consumed_branch(session, company.id, target_branch_id):
            raise ValueError("Предприятие входит в объединённый комплекс; сначала разделите комплекс")
        branch = find_next_game_branch(target_branch_id)
        if branch is None:
            raise ValueError("Завод этой ветки не найден в каталоге")
        recipe = branch["factory"]
        from backend.natbirzha.services.next_game_operations_effects import production_slots, used_production_slots
        if await used_production_slots(session, company.id) >= await production_slots(session, company.id):
            raise ValueError("Производственные места заняты; расширьте земельную площадку")
        if await session.scalar(select(NatNextGameFacility.id).where(
            NatNextGameFacility.company_id == company.id,
            NatNextGameFacility.branch_id == branch["id"],
        )):
            raise ValueError("Завод этой ветки уже построен")
        cost = float(recipe["build_cost"])
        if float(company.cash) < cost:
            raise ValueError("Недостаточно cash для строительства завода")
        treasury = await cls._treasury(session)
        current = now or _utcnow()
        company.cash = round(float(company.cash) - cost, 8)
        treasury.cash = round(float(treasury.cash) + cost, 8)
        facility = NatNextGameFacility(
            company_id=company.id, branch_id=branch["id"], level=1,
            next_cycle_at=current + timedelta(seconds=int(recipe["cycle_seconds"])),
        )
        session.add(facility)
        session.add(cls._ledger(company.id, "BUILD", -cost, cost, metadata={"branch_id": branch["id"]}))
        await session.flush()
        return {"success": True, "company": cls.snapshot_company(company), "facility": {
            "id": facility.id, "branch_id": facility.branch_id,
            "name": recipe["facility_name"], "level": facility.level,
            "next_cycle_at": facility.next_cycle_at.isoformat(),
        }}

    @classmethod
    async def upgrade_facility(
        cls, session: AsyncSession, owner_tg_id: int, branch_id: str,
    ) -> dict[str, Any]:
        await cls._lock_treasury_for_sqlite(session)
        company = await cls._owned_company(session, owner_tg_id)
        facility = await session.scalar(
            select(NatNextGameFacility).where(
                NatNextGameFacility.company_id == company.id,
                NatNextGameFacility.branch_id == branch_id,
            ).with_for_update()
        )
        if facility is None:
            raise ValueError("Сначала построй завод этого этапа")
        current_level = int(facility.level)
        if current_level >= MAX_FACILITY_LEVEL:
            raise ValueError("Завод уже достиг максимального уровня")
        required_level = current_level + 1
        if int(company.level) < required_level:
            raise ValueError(f"Для улучшения нужен уровень компании {required_level}")
        cost = facility_upgrade_cost(current_level)
        if float(company.cash) + 1e-9 < cost:
            raise ValueError(f"Для улучшения нужно {cost:,.0f} cash")
        treasury = await cls._treasury(session)
        company.cash = round(float(company.cash) - cost, 8)
        treasury.cash = round(float(treasury.cash) + cost, 8)
        facility.level = required_level
        session.add(cls._ledger(
            company.id, "FACILITY_UPGRADE", -cost, cost,
            metadata={"branch_id": branch_id, "from_level": current_level,
                      "to_level": required_level},
        ))
        await session.flush()
        return {
            "success": True,
            "upgrade_cost": cost,
            "output_multiplier": facility_output_multiplier(required_level),
            "facility": {"id": facility.id, "branch_id": facility.branch_id,
                         "level": facility.level},
            "company": cls.snapshot_company(company),
        }

    @classmethod
    async def _available_treasury_cash(
        cls, session: AsyncSession, treasury: NatNextGameTreasury,
    ) -> float:
        liability = await cls._deposit_liability(session)
        from backend.natbirzha.services.next_game_bond_accounting import required_liability
        liability += await required_liability(session)
        from backend.natbirzha.services.next_game_civic_accounting import required_liability as city_liability
        liability += await city_liability(session)
        return max(0.0, round(float(treasury.cash) - liability, 8))

    @staticmethod
    def _ledger(
        company_id: int, action: str, cash_company: float, cash_treasury: float,
        *, item_id: str | None = None, company_quantity: float = 0.0,
        treasury_quantity: float = 0.0, metadata: dict | None = None,
    ) -> NatNextGameLedger:
        return NatNextGameLedger(
            company_id=company_id, action=action,
            cash_company_delta=round(cash_company, 8),
            cash_treasury_delta=round(cash_treasury, 8), item_id=item_id,
            quantity_company_delta=company_quantity,
            quantity_treasury_delta=treasury_quantity,
            metadata_json=metadata or {},
        )

    @classmethod
    async def _lock_treasury_for_sqlite(cls, session: AsyncSession) -> None:
        """Acquire SQLite's database-wide writer lock before reading economy rows."""
        if session.get_bind().dialect.name != "sqlite":
            return
        result = await session.execute(
            update(NatNextGameTreasury)
            .where(NatNextGameTreasury.id == 1)
            .values(cash=NatNextGameTreasury.cash)
        )
        if int(result.rowcount or 0) == 0:
            # Bootstrap before taking company locks; a concurrent first call is
            # serialized by SQLite's writer lock when it inserts the singleton.
            await cls._treasury(session)
            await session.execute(
                update(NatNextGameTreasury)
                .where(NatNextGameTreasury.id == 1)
                .values(cash=NatNextGameTreasury.cash)
            )

    @classmethod
    async def _treasury(cls, session: AsyncSession) -> NatNextGameTreasury:
        treasury = await session.scalar(
            select(NatNextGameTreasury).where(NatNextGameTreasury.id == 1)
            .with_for_update().execution_options(populate_existing=True)
        )
        if treasury is not None:
            return treasury
        # Do not lock every company row while bootstrapping. PostgreSQL economy
        # operations keep their established company-then-treasury lock order;
        # SQLite's caller takes its database-wide write lock before company reads.
        pre_economy_companies = list((await session.scalars(
            select(NatNextGameCompany).where(NatNextGameCompany.owner_tg_id > 0).order_by(NatNextGameCompany.id)
        )).all())
        opening_grants = len(pre_economy_companies) * STARTING_COMPANY_CASH
        if opening_grants > TREASURY_START_CASH:
            raise RuntimeError("Предварительный стартовый капитал превышает резерв казны 2.0")
        stock = {item_id: TREASURY_START_STOCK for item_id in get_next_game_items()}
        treasury = NatNextGameTreasury(
            id=1, cash=TREASURY_START_CASH - opening_grants, inventory_json=stock,
        )
        try:
            async with session.begin_nested():
                session.add(treasury)
                await session.flush()
                for company in pre_economy_companies:
                    session.add(cls._ledger(
                        company.id, "STARTUP_CAPITAL", STARTING_COMPANY_CASH,
                        -STARTING_COMPANY_CASH,
                        metadata={"migrated_preview_company": True},
                    ))
                await session.flush()
        except IntegrityError:
            treasury = await session.scalar(
                select(NatNextGameTreasury).where(NatNextGameTreasury.id == 1)
                .with_for_update().execution_options(populate_existing=True)
            )
            if treasury is None:
                raise
        return treasury

    @staticmethod
    async def _owned_company(session: AsyncSession, owner_tg_id: int, *, allow_recovery: bool = False) -> NatNextGameCompany:
        company = await session.scalar(
            select(NatNextGameCompany).where(NatNextGameCompany.owner_tg_id == owner_tg_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if company is None:
            raise ValueError("Сначала создайте тестовую компанию 2.0")
        if not allow_recovery:
            from backend.natbirzha.models.next_game_bankruptcy import NatNextGameBankruptcy
            bankruptcy = await session.get(NatNextGameBankruptcy, company.id)
            if bankruptcy and bankruptcy.requires_ack:
                raise ValueError("Сначала примите решение после банкротства")
        return company
