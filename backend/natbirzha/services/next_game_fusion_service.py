"""Reversible factory fusion consumes sources and never runs their output twice."""
from datetime import timedelta
from sqlalchemy import select
from backend.natbirzha.models.next_game import NatNextGameFacility
from backend.natbirzha.models.next_game_progression import NatNextGameMerger
from backend.natbirzha.next_game_catalog import find_next_game_branch, get_next_game_items
from backend.natbirzha.services.next_game_service import NextGameService
from backend.natbirzha.services.next_game_service.common import facility_recipe_at_level, _utcnow


class NextGameFusionService:
    @staticmethod
    async def facility_recipe(session, facility, recipe):
        merger = await session.scalar(select(NatNextGameMerger).where(
            NatNextGameMerger.company_id == facility.company_id,
            NatNextGameMerger.branch_id == facility.branch_id,
            NatNextGameMerger.status == "ACTIVE",
        ))
        return {**recipe, **merger.recipe_json} if merger else dict(recipe)

    @staticmethod
    async def consumed_branch(session, company_id, branch_id):
        mergers = (await session.scalars(select(NatNextGameMerger).where(
            NatNextGameMerger.company_id == company_id, NatNextGameMerger.status == "ACTIVE",
        ))).all()
        return any(source["branch_id"] == branch_id for row in mergers for source in row.sources_json)

    @staticmethod
    async def snapshot(session, company_id):
        mergers = (await session.scalars(select(NatNextGameMerger).where(
            NatNextGameMerger.company_id == company_id, NatNextGameMerger.status == "ACTIVE",
        ))).all()
        facilities = (await session.scalars(select(NatNextGameFacility).where(
            NatNextGameFacility.company_id == company_id,
        ))).all()
        eligible = []
        for facility in facilities:
            if facility.level >= 5 and not any(row.branch_id == facility.branch_id for row in mergers):
                branch = find_next_game_branch(facility.branch_id)
                if branch:
                    eligible.append({"id": facility.id, "branch_id": facility.branch_id,
                                     "name": branch["name"], "level": facility.level,
                                     "output_item": branch["factory"]["output_item"]})
        return {"mergers": [{"id": row.id, "name": row.recipe_json["facility_name"],
                              "sources": row.sources_json, "factory": row.recipe_json} for row in mergers],
                "eligible_sources": eligible, "minimum_source_level": 5,
                "production_bonus_pct": 25, "fee_policy": "10% стройки источников, минимум 2500"}

    @classmethod
    async def fuse(cls, session, owner_tg_id, source_ids):
        if len(source_ids) != 2 or len(set(source_ids)) != 2:
            raise ValueError("Выберите два разных предприятия")
        await NextGameService._lock_treasury_for_sqlite(session)
        await NextGameService.settle_company(session, owner_tg_id)
        company = await NextGameService._owned_company(session, owner_tg_id)
        sources = (await session.scalars(select(NatNextGameFacility).where(
            NatNextGameFacility.company_id == company.id,
            NatNextGameFacility.id.in_(source_ids),
        ).order_by(NatNextGameFacility.id).with_for_update())).all()
        if len(sources) != 2 or any(row.level < 5 for row in sources):
            raise ValueError("Нужны два собственных предприятия не ниже уровня 5")
        for source in sources:
            from backend.natbirzha.services.next_game_operations_effects import has_factory_assets
            if await has_factory_assets(session, source.id):
                raise ValueError("Объединение недоступно: у источника есть штат, транспорт, автоматизация или действующая лицензия")
            if await cls.consumed_branch(session, company.id, source.branch_id):
                raise ValueError("Объединённый комплекс сначала нужно разделить")
        recipes = [find_next_game_branch(row.branch_id)["factory"] for row in sources]
        if recipes[0]["output_item"] != recipes[1]["output_item"]:
            raise ValueError("Для объединения нужны предприятия с одинаковым конечным продуктом")
        fee = round(max(2500, sum(row["build_cost"] for row in recipes) * .10), 2)
        if company.cash + 1e-8 < fee:
            raise ValueError(f"Для объединения требуется {fee:,.2f} cash")
        quantities = [facility_recipe_at_level(recipe, source.level)["output_quantity"]
                      for recipe, source in zip(recipes, sources)]
        inputs = {}
        for recipe in recipes:
            for key, amount in recipe["inputs"].items():
                inputs[key] = round(inputs.get(key, 0) + amount, 4)
        recipe = {**recipes[0], "facility_name": "Объединённый комплекс: " + recipes[0]["output_name"],
                  "inputs": inputs, "operating_cost": sum(row["operating_cost"] for row in recipes),
                  "output_quantity": round(sum(quantities) * 1.25, 4),
                  "cycle_seconds": max(row["cycle_seconds"] for row in recipes),
                  "build_cost": sum(row["build_cost"] for row in recipes), "fusion": True}
        items = get_next_game_items()
        recipe["net_output_quantity"] = recipe["output_quantity"] - inputs.get(recipe["output_item"], 0)
        recipe["input_items"] = [{"item_id": key, "name": items[key]["name"], "unit": items[key]["unit"],
            "quantity": quantity, "npc_unit_cost": round(items[key]["base_price"] * 1.2, 2),
            "npc_total_cost": round(items[key]["base_price"] * quantity * 1.2, 2)} for key, quantity in inputs.items()]
        cost = round(sum(row["npc_total_cost"] for row in recipe["input_items"]), 2)
        revenue = round(items[recipe["output_item"]]["base_price"] * .8 * recipe["output_quantity"], 2)
        profit = round(revenue - cost - recipe["operating_cost"], 2)
        recipe["economics"] = {**recipe["economics"], "npc_input_cost": cost, "npc_revenue": revenue,
            "npc_profit": profit, "profit_per_hour": round(profit * 3600 / recipe["cycle_seconds"], 2),
            "payback_cycles": round(recipe["build_cost"] / profit, 2) if profit > 0 else None}
        snapshots = [{"branch_id": row.branch_id, "name": find_next_game_branch(row.branch_id)["name"], "level": row.level,
                      "created_at": row.created_at.isoformat(), "original_id": row.id} for row in sources]
        # Both persisted source rows are consumed. Exactly one complex remains.
        anchor = sources[0].branch_id
        for source in sources:
            await session.delete(source)
        await session.flush()
        current = _utcnow()
        merger = NatNextGameMerger(company_id=company.id, branch_id=anchor,
            sources_json=snapshots, recipe_json=recipe, status="ACTIVE", created_at=current)
        session.add(merger)
        session.add(NatNextGameFacility(company_id=company.id, branch_id=anchor, level=1,
            next_cycle_at=current + timedelta(seconds=recipe["cycle_seconds"]), created_at=current))
        treasury = await NextGameService._treasury(session)
        company.cash = round(company.cash - fee, 8)
        treasury.cash = round(treasury.cash + fee, 8)
        session.add(NextGameService._ledger(company.id, "FACTORY_FUSION", -fee, fee,
            metadata={"sources": snapshots, "output_item": recipe["output_item"]}))
        await session.flush()
        return {"success": True, "merger_id": merger.id, "paid_amount": fee}

    @classmethod
    async def dissolve(cls, session, owner_tg_id, merger_id):
        await NextGameService._lock_treasury_for_sqlite(session)
        await NextGameService.settle_company(session, owner_tg_id)
        company = await NextGameService._owned_company(session, owner_tg_id)
        merger = await session.scalar(select(NatNextGameMerger).where(
            NatNextGameMerger.id == merger_id, NatNextGameMerger.company_id == company.id,
            NatNextGameMerger.status == "ACTIVE",
        ).with_for_update())
        if merger is None:
            raise ValueError("Действующее объединение не найдено")
        complex_row = await session.scalar(select(NatNextGameFacility).where(
            NatNextGameFacility.company_id == company.id,
            NatNextGameFacility.branch_id == merger.branch_id,
        ).with_for_update())
        if complex_row is None:
            raise ValueError("Предприятие объединения не найдено")
        from backend.natbirzha.services.next_game_operations_effects import production_slots, used_production_slots
        if await used_production_slots(session, company.id) + len(merger.sources_json) - 1 > await production_slots(session, company.id):
            raise ValueError("Для исходных предприятий расширьте производственную площадку")
        current = _utcnow()
        # Create the other consumed branch first, then transfer paid assets before
        # deleting the anchor. Foreign-key cascades cannot silently destroy them.
        sources = [source for source in merger.sources_json if source["branch_id"] != complex_row.branch_id]
        sources += [source for source in merger.sources_json if source["branch_id"] == complex_row.branch_id]
        first = sources[0]
        first_recipe = find_next_game_branch(first["branch_id"])["factory"]
        target = NatNextGameFacility(company_id=company.id, branch_id=first["branch_id"], level=first["level"],
            created_at=current, next_cycle_at=current + timedelta(seconds=first_recipe["cycle_seconds"]))
        session.add(target)
        await session.flush()
        from backend.natbirzha.services.next_game_operations_effects import move_factory_assets
        await move_factory_assets(session, complex_row.id, target.id)
        await session.delete(complex_row)
        await session.flush()
        for source in sources[1:]:
            recipe = find_next_game_branch(source["branch_id"])["factory"]
            session.add(NatNextGameFacility(company_id=company.id, branch_id=source["branch_id"],
                level=source["level"], created_at=current,
                next_cycle_at=current + timedelta(seconds=recipe["cycle_seconds"])))
        merger.status, merger.dissolved_at = "DISSOLVED", current
        session.add(NextGameService._ledger(company.id, "FACTORY_DISSOLVE", 0, 0,
            metadata={"merger_id": merger.id, "sources": merger.sources_json}))
        await session.flush()
        return {"success": True, "restored_sources": len(merger.sources_json),
            "assets_moved_to": target.branch_id,
            "message": "Исходные предприятия восстановлены; штат и оборудование сохранены на одном источнике. Плата объединения не возвращается"}
