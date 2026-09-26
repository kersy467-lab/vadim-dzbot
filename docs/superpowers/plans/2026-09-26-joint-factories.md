# Совместные заводы Implementation Plan

> **For agentic workers:** Implement task by task with the existing codebase. Do not commit, push, or deploy; the user requested local-only work. Use test-first steps for every behavior.

**Goal:** Add 12 fixed 50/50 co-owned production projects between compatible industry companies, with a dedicated slot per company, four upgrade levels, shared output, and no hourly input or cash expenses.

**Architecture:** Keep supply contracts and same-company hybrid mergers intact. Add a separate joint-factory model, server-owned recipe catalog, transactional service/API, and a compact screen nested under Market → Deals. The joint factory lazily produces balanced lower-than-standard output into a shared warehouse, tracks each owner's half, and lets owners claim only their accrued share into their own inventory. Construction and upgrades consume cash and materials from both partners in the same transaction; active production has zero recurring inputs and maintenance.

**Tech Stack:** Python, FastAPI, async SQLAlchemy, existing Natbirzha lazy-settlement and inventory systems, Alembic-style project migrations, JavaScript ES modules.

---

## Fixed behavior

- The twelve industry partnerships and their two compatible partners per sector are the 12 edges of the approved industry loop: miner–logistics, miner–metallurgy, metallurgist–chemist, chemist–oilman, oilman–technoprom, technoprom–power, power–water, water–agrarian, agrarian–brewery, brewery–forester, forester–construction, construction–logistics.
- Each project has four levels, equal ownership, equal output entitlement, and a dedicated joint-factory slot. Neither partner's ordinary business slot usage changes. A company may participate in one active joint factory at a time.
- Both partners pay the same server-calculated fair-value share of opening or upgrade cash/material costs. The recipient accepts a proposal before either contribution is spent. Failure by either side rolls back all spending.
- Active production consumes no cash, materials, or maintenance. Output is deliberately lower than each partner's normal plant at the comparable progression stage. A 50/50 share accrues to each owner in a shared warehouse; owners claim their earned quantity into their company inventories. Full shared storage pauses production without deleting goods or back-paying skipped time.
- Outputs must use existing canonical items and have existing industrial/gameplay sinks. Build and upgrade resources are role-specific and come from the matching partner's inventory.
- Do not count the whole project value twice in company asset rankings. Reset, bankruptcy, and dissolution must not strand a partner's share or inventory.
- Do not commit, push, or deploy.

## Task 1: Define the shared-project recipes and economic envelope

**Files:**
- Create: `backend/natbirzha/catalogs/businesses/joint_factories.py`
- Create: `tests/natbirzha/test_joint_factory_catalog.py`
- Test against: `backend/natbirzha/catalogs/businesses/__init__.py`, `balance.py`, and `CANONICAL_ITEMS` in `models/inventory.py`.

- [ ] Write a failing test asserting exactly twelve known partner links, two links for each of the twelve industries, and no duplicate unordered pair.
- [ ] Add named recipes with two existing output items, role-specific build/upgrade materials, separate cash costs, and four level yield rows. Validate every ID against `INDUSTRIES` and `CANONICAL_ITEMS`.
- [ ] Add an economic guard: for each recipe and each level, total output reference value is below the smaller of the two partner-industry stage benchmarks; each owner's 50% output share is therefore below a regular plant's same-stage return. Use reference values only and report that actual market returns depend on demand.
- [ ] Keep this catalog independent from `CAREER_BUSINESSES`, `NatBusiness`, `BusinessService` capacity, and same-company `HYBRID_RECIPES`.
- [ ] Run `python -m pytest -q -p no:cacheprovider tests/natbirzha/test_joint_factory_catalog.py` and record the intended failing assertion before production changes.

## Task 2: Persist joint ownership, warehouse, and contribution history

**Files:**
- Create: `backend/natbirzha/models/joint_factories.py`
- Create: `backend/natbirzha/joint_factory_migration.py`
- Modify: `backend/natbirzha/models/__init__.py`
- Modify: `backend/natbirzha/migrations.py`
- Create: `tests/natbirzha/test_joint_factory_wiring.py`

- [ ] Test migration registration, idempotence, and the joint tables' uniqueness/check constraints.
- [ ] Add a joint-factory row with two company IDs, recipe, state, level, settlement cursor, pending mutual action, and immutable 50/50 shares.
- [ ] Add one warehouse row per factory/item with cumulative produced and withdrawn quantities tracked separately for both owners; this prevents one partner from claiming the other's half.
- [ ] Add an event ledger for opening, upgrades, claims, dissolution, and bankruptcy transfer, with idempotency keys for mutations.
- [ ] Register migration `natbirzha_v18_001_joint_factories`; migration must be safe when legacy company tables are absent in isolated startup paths.
- [ ] Run focused migration/wiring tests.

## Task 3: Implement proposals, co-funding, upgrades, claims, and ownership safety

**Files:**
- Create: `backend/natbirzha/services/joint_factory_service.py`
- Create: `tests/natbirzha/test_joint_factory_service.py`
- Reuse: `services/business_resource_service.py`, `services/idempotency_service.py`, `models/company.py`, `models/inventory.py`.

- [ ] Test that proposal templates require the exact pair of distinct industries and distinct players; same-company and same-player proposals fail.
- [ ] Test recipient accept checks both partners' cash and role-specific inventories under row locks, consumes equal fair-value contributions atomically, and creates the facility only once.
- [ ] Test insufficient cash or items on either side rolls back both sides' balance, inventory, and project state.
- [ ] Test pending proposals can be rejected or cancelled by the proper party; unrelated companies cannot read or mutate them.
- [ ] Test upgrades require the other owner's approval, both partners fund the exact next-level recipe, and duplicate approvals do not charge twice.
- [ ] Test claims cannot exceed accrued 50% entitlement or the claimant's storage capacity, are idempotent, and update the company's inventory with zero recurring production cost basis.
- [ ] Test mutual dissolution frees both dedicated slots and leaves no unclaimable warehouse assets; unclaimed shares must first be withdrawn or explicitly resolved by the agreed liquidation rule.

## Task 4: Implement lazy, zero-expense production

**Files:**
- Create: `backend/natbirzha/services/joint_factory_settlement.py`
- Modify: `backend/natbirzha/services/idle_company_settlement.py`
- Create: `tests/natbirzha/test_joint_factory_settlement.py`

- [ ] Test one-hour production adds exactly the recipe outputs to the shared warehouse and increments equal owner entitlements, while company cash and input inventory remain unchanged.
- [ ] Test offline catch-up uses the normal offline cap shared by both companies, advances a single project cursor, survives a fresh DB session, and never settles the same interval twice.
- [ ] Test four-level output yields increase monotonically and remain below the ordinary-factory benchmark.
- [ ] Test full warehouse pauses at capacity, preserves accrued owner entitlements, resumes after claims free space, and never creates negative or over-cap stock.
- [ ] Integrate joint settlement with the company lazy-settlement entry point. Lock facility first, then both company rows in ascending ID order. Do not recursively call `IdleEconomyService.settle_company` from joint settlement.
- [ ] Test concurrent settlement requests with SQLite idempotency and Postgres row-lock coverage where the repository's test environment supports it.

## Task 5: Handle reset, bankruptcy, ranking, and slot display

**Files:**
- Modify: `backend/natbirzha/services/company_service.py` or `company_reset_v2.py`
- Modify: `backend/natbirzha/services/bankruptcy_service.py`
- Modify: `backend/natbirzha/services/forced_bankruptcy_service.py`
- Modify: `backend/natbirzha/services/leaderboard_service.py`
- Create or extend tests: `tests/natbirzha/test_joint_factory_lifecycle.py`

- [ ] Test reset of one participant terminates or transfers the project according to the server liquidation rule, resolves both warehouse shares, and releases the surviving participant's slot.
- [ ] Test bankruptcy freezes production and lists only the bankrupt company's 50% ownership as a bankruptcy-market asset; buying that share changes only the bankrupt-side owner and does not duplicate project output.
- [ ] Test leaderboard/NAV counts 50% of project net assets for each active owner and never counts the whole joint facility twice.
- [ ] Test a company with an active joint facility cannot create or accept a second one; this dedicated limit remains separate from ordinary business slot capacity.

## Task 6: Add authenticated API and compact Deals screen

**Files:**
- Create: `backend/natbirzha/api/joint_factory_routes.py`
- Modify: `backend/natbirzha/api/__init__.py`
- Create: `frontend/natbirzha/js/screens/market_joint_factories.js`
- Modify: `frontend/natbirzha/js/screens/market_deals.js`
- Modify: `frontend/natbirzha/js/api.js`
- Modify: `frontend/natbirzha/index.html` only if cache-busting is needed
- Create/modify: `tests/natbirzha/test_joint_factory_api.py`, `tests/test_natbirzha_frontend.js`

- [ ] Test authorized endpoints for recipe/company discovery, create proposal, incoming/outgoing/active/history, accept/reject/cancel, request/approve upgrade, claim, dissolve, and details.
- [ ] Ensure every endpoint verifies the caller is one of the two owners; require idempotency keys on all mutations; derive recipe costs, shares, yields, and prices only from the server catalog.
- [ ] Add a `Совместные заводы` tab under Market → Deals without changing existing supply-deal behavior.
- [ ] Show each company's dedicated joint slot, compatible partner options, role-specific build amounts, both cash/material contributions, four-level yield preview, shared stock, own claimable half, next upgrade cost, and shared status/timer.
- [ ] Add responsive cards using existing market components/styles; keep screens modular and each source file under the AGENTS.md 350–400 line limit.
- [ ] Run frontend contract/syntax tests and verify screen registration/cache-busting.

## Task 7: Verification and local handoff

**Files:** all files above; no commit.

- [ ] Run targeted catalog, migration, service, settlement, API, lifecycle, and frontend tests; fix implementation failures rather than weakening assertions.
- [ ] Run `python -m py_compile` on every new/modified Python module and `node --check` on the new screen.
- [ ] Run `python -u tests/test_suite.py`, `node tests/test_natbirzha_frontend.js`, and `node tests/test_frontend_shell_contract.js`.
- [ ] Run the production-yield audit for all 12 partnerships and levels 1–4; verify construction payback, that each owner receives less hourly output value than a normal plant, no hourly resources/cash are consumed, output storage remains bounded, and no normal slots are consumed.
- [ ] Review reset, bankruptcy, offline settlement, concurrent accept/upgrade, and shared-inventory claim behavior; run `git diff --check`.
- [ ] Keep every change local and uncommitted.
