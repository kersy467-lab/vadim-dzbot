# Государственная казна и торговля Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the State Treasury a one-time 10 trillion cash reserve, make NPC trades settle through that reserve, add a reversible fiscal default, and let the creator export State-held goods for external revenue.

**Architecture:** Keep treasury policy and foreign exports in a focused `StateEconomyService`; store State-held commodity quantities separately from company inventories. Apply default prices at the existing NPC quote boundary, update tax calculation from the current Treasury balance, and run idempotent export cycles from a cancellable app-lifespan worker. Preserve current NPC buyback quotas and the ten-rebirth cap.

**Tech Stack:** FastAPI, SQLAlchemy async sessions, Alembic-style startup migrations, existing NATBIRZHA JavaScript screens and pytest-style tests.

---

### Task 1: Treasury reserve, State stock, and migration

**Files:** `backend/natbirzha/models/creator.py`, `backend/natbirzha/models/npc.py`, `backend/natbirzha/models/__init__.py`, `backend/natbirzha/services/state_treasury_service.py`, `backend/natbirzha/migrations.py`, `tests/natbirzha/test_state_economy.py`.

- [x] Add a failing test that a newly created Treasury starts at 10,000,000,000,000 cash and that the one-time migration tops up an existing lower balance without changing a larger balance on a second run.
- [x] Add `NatStateReserveStock(item_id, quantity, average_cost_basis, updated_at)` and export-cycle fields to the singleton Treasury.
- [x] Register both models and add an idempotent migration that creates the stock table, adds Treasury columns, and raises the existing singleton to 10 trillion only once.
- [x] Run the focused migration test, then keep the repository’s migration test green.

### Task 2: NPC cash settlement and fiscal policy

**Files:** `backend/natbirzha/services/state_economy_service.py`, `backend/natbirzha/services/npc_service.py`, `backend/natbirzha/services/npc_quota_service.py`, `backend/natbirzha/api/market_routes.py`, `backend/natbirzha/services/tax_service.py`, `tests/natbirzha/test_npc_liquidity_service.py`, `tests/natbirzha/test_state_economy.py`.

- [x] First assert in the NPC regression test that player purchases credit the Treasury and player sales debit it; verify the test fails against current behavior.
- [x] Set the fiscal-default trigger below 1 trillion cash; use 30% tax, 10% lower NPC buyback prices, and 10% higher NPC retail prices while in default. Return to normal rates once the reserve reaches 1 trillion.
- [x] Lock Treasury before company cash, reject State-funded buybacks that the Treasury cannot afford, update State-held stock atomically, keep daily cash caps only on State purchases from players (energy and water), and allow players to buy every NPC resource without a daily quota.
- [x] Record NPC transfers as transfers rather than new cash creation, and apply the default tax rate only to tax periods created while default is active.
- [x] Run focused NPC, tax, and quote tests.

### Task 3: Foreign exports and creator controls

**Files:** `backend/natbirzha/services/state_economy_service.py`, `backend/natbirzha/api/creator_economy_routes.py`, `backend/natbirzha/api/creator_routes.py`, `backend/main.py`, `frontend/natbirzha/js/api.js`, `frontend/natbirzha/js/screens/creator_overview.js`, `tests/natbirzha/test_state_economy.py`.

- [x] Add tests for disabled exports, one 15-minute export cycle, stock removal, Treasury revenue, and duplicate-cycle prevention.
- [x] When enabled, export 10% of available State stock every 15 minutes at the canonical item base price; empty stock never generates cash.
- [x] Add creator-only status and enable/disable endpoints and display the reserve, default status, current tax rate, export toggle, and stock in the State panel.
- [x] Start one cancellable worker from FastAPI lifespan; use the locked Treasury row and last-export timestamp so multiple app workers cannot sell the same stock twice.
- [x] Run syntax checks and the full `python tests/test_suite.py` suite required by repository instructions; review `git diff` and leave deployment untouched unless requested.

### Task 4: Regression and completion review

**Files:** All task files above.

- [x] Confirm migration idempotence, no negative Treasury balances, NPC transaction rollback on insufficient funds, and no export without stock.
- [x] Confirm `MAX_REBIRTHS` remains 10 and no unrelated working-tree changes are included.
- [x] Report test results; leave the changes uncommitted and do not push or deploy unless explicitly requested.
