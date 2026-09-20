# NATBIRZHA P2 Military and Premium Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a production-ready backend for composite armies, PvE territory wars, 18-hour PvP tournaments, military rating, Pivocoins, and 48-hour premium licenses.

**Architecture:** Keep battle calculation pure and deterministic, while transaction services own row locks, persistence, rewards, and idempotency. Add new normalized tables alongside current NATBIRZHA tables, migrate old army and premium balances forward, and preserve compatibility responses until the frontend is replaced.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async, PostgreSQL/SQLite, Pydantic v2, APScheduler, httpx test client.

---

## File map

- Create `backend/natbirzha/migrations.py` — repeatable SQLite/PostgreSQL schema and data migrations.
- Create `backend/natbirzha/models/premium.py` — PVC ledger and timed licenses.
- Create `backend/natbirzha/models/combat.py` — normalized units, battles, PvE targets/victories, rating events, PvP cooldowns.
- Modify `backend/natbirzha/models/company.py` — add `pvc_balance` and military rating.
- Modify `backend/natbirzha/models/military.py` — extend tournament fields and participant snapshots.
- Modify `backend/natbirzha/models/__init__.py` — import and export every new model.
- Create `backend/natbirzha/services/unit_catalog.py` — unit and counter-class constants.
- Create `backend/natbirzha/services/combat_resolver.py` — pure three-phase battle calculation.
- Create `backend/natbirzha/services/premium_service.py` — wallet ledger and license transactions.
- Create `backend/natbirzha/services/army_service.py` — normalized recruitment, snapshots, losses, compatibility totals.
- Create `backend/natbirzha/services/rating_service.py` — rating calculations and immutable events.
- Create `backend/natbirzha/services/pve_service.py` — target catalog and PvE attacks.
- Create `backend/natbirzha/services/tournament_service.py` — lifecycle, PvP, snapshots, ranking, rewards.
- Create `backend/natbirzha/api/premium_routes.py` — PVC and license endpoints.
- Modify `backend/natbirzha/api/military_routes.py` — PvE, battle log, tournament targets, PvP endpoints.
- Modify `backend/natbirzha/api/creator_routes.py` — custom tournament request with three rewards.
- Modify `backend/natbirzha/api/__init__.py` — register premium routes.
- Modify `backend/bot/services/scheduler.py` — idempotent tournament lifecycle tick.
- Create `tests/natbirzha/test_combat_resolver.py` — unit and counter-class tests.
- Create `tests/natbirzha/test_premium_and_licenses.py` — PVC ledger and 48-hour license tests.
- Create `tests/natbirzha/test_pve_wars.py` — PvE transaction and territory tests.
- Create `tests/natbirzha/test_tournament_pvp.py` — lifecycle, cooldown, concurrent attack, ranking, rewards.
- Create `tests/natbirzha/test_p2_backend_api.py` — HTTP auth, ownership, idempotency, creator permissions.

## Task 1: Repeatable schema migration foundation

**Files:**
- Create: `backend/natbirzha/migrations.py`
- Modify: `backend/db/session.py`
- Test: `tests/natbirzha/test_p2_migrations.py`

- [ ] **Step 1: Write the failing migration test**

Create a SQLite database containing the legacy `nat_companies`, `nat_armies`, and `nat_tournaments` tables, insert one company with `nat_balance=37` and four legacy unit counts, run `run_natbirzha_migrations`, and assert:

```python
assert company_row.pvc_balance == 37
assert units == {
    "infantry": 12,
    "tanks": 2,
    "drones": 3,
    "air_defense": 1,
}
assert schema_version("natbirzha_p2_001") == 1
```

Run: `python tests/natbirzha/test_p2_migrations.py`  
Expected: FAIL because `backend.natbirzha.migrations` does not exist.

- [ ] **Step 2: Implement the migration runner**

Use a migration registry with one immutable key per migration:

```python
MIGRATIONS = (
    ("natbirzha_p2_001", migrate_p2_schema),
    ("natbirzha_p2_002", migrate_legacy_balances_and_armies),
)

async def run_natbirzha_migrations(conn) -> None:
    await ensure_version_table(conn)
    for version, migration in MIGRATIONS:
        if not await is_applied(conn, version):
            await migration(conn)
            await mark_applied(conn, version)
```

The schema migration adds `pvc_balance`, `military_rating`, expanded tournament columns, and creates every new table with dialect-specific JSON/boolean syntax. The data migration copies `nat_balance` once and inserts normalized unit rows using `INSERT ... ON CONFLICT DO NOTHING` on PostgreSQL and `INSERT OR IGNORE` on SQLite.

- [ ] **Step 3: Call the runner from startup**

At the end of `Base.metadata.create_all` inside `init_db`:

```python
from backend.natbirzha.migrations import run_natbirzha_migrations
await run_natbirzha_migrations(conn)
```

- [ ] **Step 4: Verify repeatability**

Run the migration test twice against the same DB.  
Expected: PASS; the second run does not duplicate balances, units, or version rows.

- [ ] **Step 5: Commit**

```bash
git add backend/db/session.py backend/natbirzha/migrations.py tests/natbirzha/test_p2_migrations.py
git commit -m "feat(natbirzha): add repeatable p2 migrations"
```

## Task 2: Add normalized premium and combat models

**Files:**
- Create: `backend/natbirzha/models/premium.py`
- Create: `backend/natbirzha/models/combat.py`
- Modify: `backend/natbirzha/models/company.py`
- Modify: `backend/natbirzha/models/military.py`
- Modify: `backend/natbirzha/models/__init__.py`
- Test: `tests/natbirzha/test_p2_models.py`

- [ ] **Step 1: Write model invariant tests**

Assert unique constraints for `(company_id, unit_type)`, ledger `operation_key`, `(company_id, pve_corporation_id)`, and PvP cooldown pair. Assert the company defaults:

```python
assert company.pvc_balance == 0
assert company.military_rating == 1000
```

Run: `python tests/natbirzha/test_p2_models.py`  
Expected: FAIL because the models do not exist.

- [ ] **Step 2: Define premium models**

Implement `NatPremiumLedgerEntry` and `NatPremiumLicense` with these required fields:

```python
class NatPremiumLedgerEntry(Base):
    __tablename__ = "nat_premium_ledger"
    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("nat_companies.id", ondelete="CASCADE"), index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_before: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    operation_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

`NatPremiumLicense` has unique active identity by company and `license_code`, plus `starts_at`, `expires_at`, `status`, and `purchase_ledger_id`.

- [ ] **Step 3: Define combat models**

Add `NatArmyUnit`, `NatBattle`, `NatBattleSnapshot`, `NatPveCorporation`, `NatPveVictory`, `NatMilitaryRatingEvent`, and `NatPvpCooldown`. Battle rows store `mode`, attacker/defender ids, result, seed digest, catalog version, summary JSON, timestamps, and tournament/PvE references.

- [ ] **Step 4: Extend tournament models**

Add `tournament_type`, `status`, `reward_first_pvc`, `reward_second_pvc`, `reward_third_pvc`, `created_by_user_id`, `resolved_at`, and initial/final strength fields on participants. Preserve existing property names used by the frontend.

- [ ] **Step 5: Export models and verify metadata**

Run: `python tests/natbirzha/test_p2_models.py`  
Expected: PASS with all new tables present in `Base.metadata.tables`.

- [ ] **Step 6: Commit**

```bash
git add backend/natbirzha/models tests/natbirzha/test_p2_models.py
git commit -m "feat(natbirzha): model p2 wars tournaments and pvc"
```

## Task 3: Build the pure combat resolver

**Files:**
- Create: `backend/natbirzha/services/unit_catalog.py`
- Create: `backend/natbirzha/services/combat_resolver.py`
- Test: `tests/natbirzha/test_combat_resolver.py`

- [ ] **Step 1: Write failing counter-class tests**

Use fixed snapshots and seed to assert:

```python
assert resolve(tanks, infantry, seed="x").winner == "attacker"
assert resolve(air_defense, aircraft, seed="x").winner == "attacker"
assert resolve(aircraft, tanks, seed="x").winner == "attacker"
assert resolve(border_guards, infantry, seed="x", defender=True).defender_phase_bonus > 1
```

Also assert identical inputs and seed return identical results, random multiplier stays in `[0.95, 1.05]`, and losses remain in their configured ranges.

Run: `python tests/natbirzha/test_combat_resolver.py`  
Expected: FAIL because the resolver does not exist.

- [ ] **Step 2: Implement the catalog**

Define immutable `UnitSpec` values and matchups:

```python
UNIT_SPECS = {
    "infantry": UnitSpec(10, "ground"),
    "border_guards": UnitSpec(14, "ground", defense=1.30),
    "tanks": UnitSpec(150, "ground", counters={"infantry": 1.25, "border_guards": 1.25}),
    "drones": UnitSpec(80, "recon"),
    "aircraft": UnitSpec(220, "air", counters={"tanks": 1.35}),
    "air_defense": UnitSpec(200, "air_defense", counters={"aircraft": 1.45}),
}
```

- [ ] **Step 3: Implement deterministic resolution**

Expose one pure API:

```python
def resolve_battle(
    attacker: ArmySnapshot,
    defender: ArmySnapshot,
    seed: str,
    premium: PremiumModifiers = PremiumModifiers(),
) -> BattleResult:
    ...
```

Compute recon, air, and ground scores, clamp phase premium bonuses at 20%, derive the ±5% multiplier from HMAC-SHA256, and return per-unit integer losses plus a serializable explanation.

- [ ] **Step 4: Verify edge cases**

Add tests for empty armies, equal scores, no surviving ground unit, extreme level values, and premium cap.  
Expected: all resolver tests PASS with no database imports.

- [ ] **Step 5: Commit**

```bash
git add backend/natbirzha/services/unit_catalog.py backend/natbirzha/services/combat_resolver.py tests/natbirzha/test_combat_resolver.py
git commit -m "feat(natbirzha): add deterministic combined arms resolver"
```

## Task 4: Implement PVC ledger and timed licenses

**Files:**
- Create: `backend/natbirzha/services/premium_catalog.py`
- Create: `backend/natbirzha/services/premium_service.py`
- Create: `backend/natbirzha/api/premium_routes.py`
- Modify: `backend/natbirzha/api/__init__.py`
- Test: `tests/natbirzha/test_premium_and_licenses.py`

- [ ] **Step 1: Write failing wallet tests**

Cover credit, debit, insufficient funds, duplicate operation key, and rollback. Verify ledger sum and wallet balance match.

Run: `python tests/natbirzha/test_premium_and_licenses.py`  
Expected: FAIL because `PremiumService` does not exist.

- [ ] **Step 2: Implement atomic wallet mutation**

```python
async def apply_pvc(
    session: AsyncSession,
    company_id: int,
    amount: int,
    operation_type: str,
    operation_key: str,
    metadata: dict,
    actor_user_id: int | None = None,
) -> NatPremiumLedgerEntry:
    company = await lock_company(session, company_id)
    existing = await ledger_by_key(session, operation_key)
    if existing:
        return existing
    after = company.pvc_balance + amount
    if after < 0:
        raise InsufficientPvc(required=-amount, available=company.pvc_balance)
    ...
```

Do not commit inside the service; the route or higher-level transaction commits wallet and business mutation together.

- [ ] **Step 3: Implement the license catalog and purchase**

Start with `rare_mining` and `advanced_defense`. Each catalog entry defines PVC price, 48-hour duration, permitted building types, recipes, and upgrades. Renewal uses `max(now, expires_at) + 48 hours`.

- [ ] **Step 4: Add premium routes**

Implement wallet, ledger, license catalog, owned licenses, and purchase endpoints. Purchase requires Idempotency-Key and uses `IdempotencyService.commit_response` in the same transaction.

- [ ] **Step 5: Verify expiry behavior**

Use injected `now` values to test active at 47:59:59, expired at 48:00:00, renewal before expiry, and purchase after expiry.

- [ ] **Step 6: Commit**

```bash
git add backend/natbirzha/services/premium_catalog.py backend/natbirzha/services/premium_service.py backend/natbirzha/api/premium_routes.py backend/natbirzha/api/__init__.py tests/natbirzha/test_premium_and_licenses.py
git commit -m "feat(natbirzha): add pvc ledger and timed licenses"
```

## Task 5: Normalize recruitment and army snapshots

**Files:**
- Create: `backend/natbirzha/services/army_service.py`
- Modify: `backend/natbirzha/services/military_service.py`
- Modify: `backend/natbirzha/api/military_routes.py`
- Test: `tests/natbirzha/test_army_service.py`

- [ ] **Step 1: Write failing recruitment tests**

Test all six unit types, Cash/material costs, row locking, duplicate idempotency, and compatibility totals.

- [ ] **Step 2: Implement ArmyService**

The public methods are:

```python
await ArmyService.recruit(session, company, unit_type, count)
await ArmyService.snapshot(session, company.id, for_update=False)
await ArmyService.apply_losses(session, company.id, losses)
await ArmyService.compatibility_status(session, company.id)
```

`apply_losses` rejects any result larger than the locked current quantity. `compatibility_status` returns the old four fields plus `border_guards`, `aircraft`, readiness, phase strengths, and total strength.

- [ ] **Step 3: Delegate old service calls**

Keep `MilitaryService.recruit_units` as a compatibility wrapper around `ArmyService.recruit` so existing imports do not break.

- [ ] **Step 4: Run tests**

Run: `python tests/natbirzha/test_army_service.py`  
Expected: PASS for all six types and atomic resource deduction.

- [ ] **Step 5: Commit**

```bash
git add backend/natbirzha/services/army_service.py backend/natbirzha/services/military_service.py backend/natbirzha/api/military_routes.py tests/natbirzha/test_army_service.py
git commit -m "feat(natbirzha): normalize army recruitment and snapshots"
```

## Task 6: Implement PvE corporate wars

**Files:**
- Create: `backend/natbirzha/services/pve_catalog.py`
- Create: `backend/natbirzha/services/pve_service.py`
- Modify: `backend/natbirzha/api/military_routes.py`
- Test: `tests/natbirzha/test_pve_wars.py`

- [ ] **Step 1: Write failing PvE flow tests**

Cover target visibility, scouting range, victory, defeat, losses, territory, rewards, duplicate idempotency, and unique victory.

- [ ] **Step 2: Seed a versioned target catalog**

Provide at least twelve targets across four tiers. Each target has a stable code, industry, unit snapshot, territory reward, Cash/resource/XP rewards, level prerequisite, and catalog version.

- [ ] **Step 3: Implement transactional attack**

```python
async def attack_target(session, company, target_code, operation_key, now):
    company = await lock_company(session, company.id)
    army = await ArmyService.snapshot(session, company.id, for_update=True)
    victory = await lock_or_create_victory(session, company.id, target_code)
    battle = create_pending_battle(...)
    result = resolve_battle(army, target.snapshot, battle_seed(battle), modifiers(...))
    await ArmyService.apply_losses(session, company.id, result.attacker_losses)
    await RatingService.apply_battle_result(...)
    if result.attacker_won and not victory.reward_claimed:
        apply_pve_rewards(...)
    finalize_battle(...)
    return serialize_battle(...)
```

- [ ] **Step 4: Add scout, attack, history, and detail routes**

Return stable `reason` values for locked target, insufficient ground force, already conquered, and unavailable tier.

- [ ] **Step 5: Run tests and commit**

Run: `python tests/natbirzha/test_pve_wars.py`  
Expected: PASS; repeated requests never duplicate territory or rewards.

```bash
git add backend/natbirzha/services/pve_catalog.py backend/natbirzha/services/pve_service.py backend/natbirzha/api/military_routes.py tests/natbirzha/test_pve_wars.py
git commit -m "feat(natbirzha): add pve corporate territory wars"
```

## Task 7: Implement rating and tournament lifecycle

**Files:**
- Create: `backend/natbirzha/services/rating_service.py`
- Create: `backend/natbirzha/services/tournament_service.py`
- Modify: `backend/natbirzha/services/military_service.py`
- Test: `tests/natbirzha/test_tournament_lifecycle.py`

- [ ] **Step 1: Write failing lifecycle tests**

Test automatic 72-hour cadence, exact 18-hour duration, eligible participant snapshots, state transitions, restart-safe ticks, competition ranking, shared place rewards, and default 150/100/70 PVC.

- [ ] **Step 2: Implement rating events**

Use expected-result rating math and clamp the absolute change to 5–35. Store a unique event per battle/company pair.

- [ ] **Step 3: Implement lifecycle methods**

```python
await TournamentService.ensure_next_scheduled(session, now)
await TournamentService.activate_due(session, now)
await TournamentService.begin_resolution(session, tournament_id, now)
await TournamentService.resolve(session, tournament_id, now)
```

`resolve` locks the tournament, returns its stored result when already completed, captures final strength, assigns competition ranks, and credits PVC using unique ledger keys.

- [ ] **Step 4: Keep old resolve API compatible**

`MilitaryService.resolve_tournament` delegates to `TournamentService.resolve` and retains the keys used by existing callers while adding top-three results.

- [ ] **Step 5: Run tests and commit**

```bash
python tests/natbirzha/test_tournament_lifecycle.py
git add backend/natbirzha/services/rating_service.py backend/natbirzha/services/tournament_service.py backend/natbirzha/services/military_service.py tests/natbirzha/test_tournament_lifecycle.py
git commit -m "feat(natbirzha): add 18 hour tournament lifecycle and rewards"
```

## Task 8: Implement tournament PvP and cooldowns

**Files:**
- Modify: `backend/natbirzha/services/tournament_service.py`
- Modify: `backend/natbirzha/api/military_routes.py`
- Test: `tests/natbirzha/test_tournament_pvp.py`

- [ ] **Step 1: Write failing PvP tests**

Verify attacks fail outside `ACTIVE`, self-attack fails, target must be a participant, winner creates a two-hour attacker/defender cooldown, loser does not create that cooldown, and territory/Cash/inventory remain unchanged.

- [ ] **Step 2: Implement stable lock ordering**

```python
first_id, second_id = sorted((attacker.id, defender.id))
locked = await lock_companies_and_armies(session, first_id, second_id)
```

Recheck tournament status and cooldown after locks are held. Resolve battle, apply both sides' losses, add both rating events, store snapshots, and commit through idempotency.

- [ ] **Step 3: Add targets, attack, and leaderboard endpoints**

The target response includes rating, approximate strength, `cooldown_until`, and attack availability. The leaderboard includes final/current strength, rating, wins, losses, and reward.

- [ ] **Step 4: Verify concurrency**

Launch two attacks against the same defender with separate sessions. Assert committed quantities equal the sequentially valid result and no negative units exist.

- [ ] **Step 5: Commit**

```bash
git add backend/natbirzha/services/tournament_service.py backend/natbirzha/api/military_routes.py tests/natbirzha/test_tournament_pvp.py
git commit -m "feat(natbirzha): add tournament pvp and target cooldowns"
```

## Task 9: Add creator custom tournaments and scheduler jobs

**Files:**
- Modify: `backend/natbirzha/api/creator_routes.py`
- Modify: `backend/natbirzha/services/creator_service.py`
- Modify: `backend/bot/services/scheduler.py`
- Test: `tests/natbirzha/test_creator_custom_tournaments.py`

- [ ] **Step 1: Write failing creator tests**

Test ordinary user 403, three independent rewards, negative and over-limit validation, refusal while active, 18-hour finish time, idempotent replay, and audit entry.

- [ ] **Step 2: Extend request and service**

```python
class LaunchTournamentRequest(BaseModel):
    reward_first_pvc: int = Field(default=150, ge=0, le=10_000)
    reward_second_pvc: int = Field(default=100, ge=0, le=10_000)
    reward_third_pvc: int = Field(default=70, ge=0, le=10_000)
```

CreatorService calls `TournamentService.create_custom` and records all three rewards in the audit metadata.

- [ ] **Step 3: Add one scheduler tick**

Register an interval job every minute that calls `TournamentService.tick_all(now)` in a fresh session. Give it a stable job id and `replace_existing=True`.

- [ ] **Step 4: Verify restart safety and commit**

Run the tick three times at each boundary and assert one tournament, one resolution, and one ledger credit per winner.

```bash
git add backend/natbirzha/api/creator_routes.py backend/natbirzha/services/creator_service.py backend/bot/services/scheduler.py tests/natbirzha/test_creator_custom_tournaments.py
git commit -m "feat(natbirzha): add creator tournaments and scheduler lifecycle"
```

## Task 10: Enforce premium production gates

**Files:**
- Modify: `backend/natbirzha/services/building_catalog/buildings_part1.py`
- Modify: `backend/natbirzha/services/building_service.py`
- Modify: `backend/natbirzha/services/production_service.py`
- Modify: `backend/natbirzha/services/recipes.py`
- Test: `tests/natbirzha/test_premium_production.py`

- [ ] **Step 1: Write failing production gate tests**

Test lithium and rare-earth building without license, active license, expired license, renewal, start before expiry/collect after expiry, and P2P purchase without license.

- [ ] **Step 2: Mark premium catalog entries**

Add `required_license: "rare_mining"` to `lithium_mine`, `rare_earth_mine`, and their canonical recipes. Keep item IDs unchanged.

- [ ] **Step 3: Enforce the gate server-side**

Building and production services call:

```python
await PremiumService.require_active_license(
    session, company.id, required_license, now=get_game_now()
)
```

Collect skips the license check because inputs were reserved at start. MarketService does not check a license for buying or selling the resulting items.

- [ ] **Step 4: Run DAG and production tests**

```bash
python tests/natbirzha/test_premium_production.py
python tests/natbirzha/test_dag_and_specialization.py
python tests/natbirzha/test_registration_production_cycle.py
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/natbirzha/services/building_catalog/buildings_part1.py backend/natbirzha/services/building_service.py backend/natbirzha/services/production_service.py backend/natbirzha/services/recipes.py tests/natbirzha/test_premium_production.py
git commit -m "feat(natbirzha): gate rare production with timed licenses"
```

## Task 11: Add full HTTP and regression coverage

**Files:**
- Create: `tests/natbirzha/test_p2_backend_api.py`
- Modify: `tests/test_suite.py`

- [ ] **Step 1: Write one end-to-end HTTP scenario**

The scenario creates companies, credits PVC through the service, buys and renews a license, recruits all unit classes, wins and loses PvE fights, starts a creator tournament, performs PvP, verifies cooldown, advances time, resolves top-three rewards, and checks ledger entries.

- [ ] **Step 2: Add negative security cases**

Cover unsigned auth, forged creator role, attacking another user's company as self, missing idempotency key, stale tournament, duplicate battle operation, and direct premium recipe start without license.

- [ ] **Step 3: Register tests in the project suite**

Add the P2 scripts to `tests/test_suite.py` without changing existing RPG test order.

- [ ] **Step 4: Run focused verification**

```bash
python -m compileall -q backend tests
python tests/natbirzha/test_combat_resolver.py
python tests/natbirzha/test_premium_and_licenses.py
python tests/natbirzha/test_pve_wars.py
python tests/natbirzha/test_tournament_pvp.py
python tests/natbirzha/test_p2_backend_api.py
```

Expected: all commands exit 0.

- [ ] **Step 5: Run full regression**

```bash
python tests/test_suite.py
node tests/test_frontend_modules.js
node tests/test_natbirzha_frontend.js
git diff --check
```

Expected: `=== ALL TESTS PASSED SUCCESSFULLY! ZERO ERRORS! ===`, both Node scripts PASS, and no whitespace errors.

- [ ] **Step 6: Commit**

```bash
git add tests
git commit -m "test(natbirzha): verify p2 backend end to end"
```

## Task 12: Backend handoff before frontend work

**Files:**
- Create: `docs/natbirzha/p2-backend-api.md`
- Modify: `NATBIRZHA_FIX_REPORT.md`

- [ ] **Step 1: Document final API payloads**

Record request/response examples, `reason` codes, timestamps, unit fields, tournament states, PVC operation types, and license semantics using responses captured from the HTTP tests.

- [ ] **Step 2: Record migration and deployment requirements**

Document required environment values, backup-before-migration procedure, and safe rollback rule: application rollback may ignore new tables, but database rollback must never delete P2 data.

- [ ] **Step 3: Update the verification report**

List commands, exact passing counts, known limits, and the next frontend integration plan.

- [ ] **Step 4: Commit**

```bash
git add docs/natbirzha/p2-backend-api.md NATBIRZHA_FIX_REPORT.md
git commit -m "docs(natbirzha): document p2 backend contract"
```

---

## Next backend plan

After this plan is green, create and execute `NATBIRZHA P2 Reference Instruments and Bond Settlement`: official-source adapters for gold, silver, EUR and USD; cached snapshots; portfolio and trade transactions; bond coupon/maturity settlement; and simulation coverage. Frontend redesign starts after both backend plans pass regression.
