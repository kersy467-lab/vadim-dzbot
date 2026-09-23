# Business Expansion and State Shares Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let players own repeatable businesses with a 10-slot starting portfolio and reinvestment-led progression, and let the creator issue treasury-backed synthetic state shares from the State panel.

**Architecture:** Keep enterprise instances as separate `NatBusiness` rows, group them only for catalog/prerequisite display, and preserve per-instance actions and the existing 40% sale refund. Add an independent state-share issue/holding/settlement domain rather than representing state issuers as player companies; creator routes issue supply, player routes buy or redeem against the State Treasury, portfolio APIs report holdings, and optional dividends never exceed treasury cash.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy async, existing NATBIRZHA migration runner, browser ES modules, pytest-style integration scripts, SQLite in-memory tests.

---

### Task 1: Repeatable businesses, slots, and compounding economics

**Files:**
- Modify: `backend/natbirzha/services/business_service.py`
- Modify: `backend/natbirzha/catalogs/businesses/career.py`
- Modify: `backend/natbirzha/services/empire_summary_service.py` only if serialized catalog/summary fields are needed
- Modify: `frontend/natbirzha/js/screens/tycoon.js`
- Test: `tests/natbirzha/test_tycoon_v2_business_service.py`
- Test: `tests/natbirzha/test_tycoon_v2_catalog.py`
- Test: `tests/test_natbirzha_frontend.js`

- [x] **Step 1: Add failing service tests**

Add assertions that a level-1 company with its starter business has 10 total slots and 9 free slots, that a second non-unique business of the same type opens as a distinct row with a distinct ID, that a unique business still rejects duplicates, and that prerequisites accept the highest-stage copy of a required type. Assert selling still returns exactly 40% of that instance's accumulated `capital_invested`.

```python
assert BusinessService.business_slot_limits(level=1, territory_tiles=4, used=1) == {
    "used": 1, "max": 10, "free": 9,
}
first = await BusinessService.open_business(session, company.id, "coal_open_pit", now=now)
second = await BusinessService.open_business(session, company.id, "coal_open_pit", now=now)
assert first["business"]["id"] != second["business"]["id"]
```

- [x] **Step 2: Run the focused tests and verify the expected failures**

Run: `pytest tests/natbirzha/test_tycoon_v2_business_service.py tests/natbirzha/test_tycoon_v2_catalog.py -q`
Expected: failures on the current 3-slot limit and duplicate ownership rejection, not test setup errors.

- [x] **Step 3: Add failing economy and catalog presentation checks**

Assert early catalog enterprises target roughly 10 in-game hours of net payback including required construction resources; later career orders have longer targets; every upgrade transition increases net profit enough that its all-in marginal payback (including milestone resources at NPC sell price) is no longer than that enterprise's opening target. Extend frontend static assertions so repeated catalog entries remain openable, count copies, and continue addressing management actions by individual business ID. The sale confirmation must display the 40% refund and resulting loss before the existing sell call.

- [x] **Step 4: Run those checks and verify they fail for the missing economics/UI**

Run: `pytest tests/natbirzha/test_tycoon_v2_catalog.py -q` and `node tests/test_natbirzha_frontend.js`.
Expected: the new ROI assertions and duplicate-card UI assertion fail before implementation; note any pre-existing frontend harness failure separately.

- [x] **Step 5: Implement the minimum enterprise changes**

Set starting capacity to 10 including the starter business, scale capacity through level and territory milestones to a configurable cap of 50, and make ordinary career catalog entries repeatable while honoring explicit `unique=True` types. Represent owned enterprises as groups of instances; use the highest-stage instance for prerequisites and show owned-copy counts without collapsing individual cards or controls. Calibrate open investment using cash price plus the NPC sell-price equivalent of consumed opening resources, set the first career payback target to 10 hours, and retain progressively longer targets later in the branch. Tune stage income/output and upgrade cost growth so investing in levels compounds net income and satisfies the marginal-payback assertion. Keep the server-authoritative 40% sale refund and make its confirmation explicit.

- [x] **Step 6: Run focused checks and syntax validation**

Run: `pytest tests/natbirzha/test_tycoon_v2_business_service.py tests/natbirzha/test_tycoon_v2_catalog.py -q`, `python -m py_compile backend/natbirzha/services/business_service.py backend/natbirzha/catalogs/businesses/career.py`, and `node --check frontend/natbirzha/js/screens/tycoon.js`.
Expected: focused tests pass and syntax checks exit 0.

---

### Task 2: Treasury-backed state share issuance and portfolio lifecycle

**Files:**
- Create: `backend/natbirzha/models/state_shares.py`
- Modify: `backend/natbirzha/models/__init__.py`
- Create: `backend/natbirzha/services/state_share_service.py`
- Modify: `backend/natbirzha/api/creator_routes.py`
- Create: `backend/natbirzha/api/state_share_routes.py`
- Modify: `backend/natbirzha/api/__init__.py`
- Modify: `backend/natbirzha/api/portfolio_routes.py`
- Modify: `backend/bot/services/scheduler.py`
- Modify: `backend/natbirzha/migrations.py`
- Create: `tests/natbirzha/test_state_share_lifecycle.py`
- Modify: `tests/natbirzha/test_p2_migration_sql.py`
- Modify: `tests/natbirzha/test_p0_api_hardening.py`

- [x] **Step 1: Add failing state-share service tests**

Cover creator-only issuance, bounded input validation, finite supply, buyer cash debit and treasury credit, portfolio holdings, treasury-limited redemption, and dividend settlement prorated across holders. An exhausted treasury must prevent redemption or scale dividend payouts down without making treasury cash negative.

```python
issue = await StateShareService.issue(session, actor_id=777, title="НАТ-Энерго",
    volume=1000, price=25, projected_annual_profit=10000,
    dividend_rate_pct=20, purpose="Развитие энергетики", commit=False)
buy = await StateShareService.buy(session, buyer, issue["share_id"], 40, commit=False)
assert buy["total_cost"] == 1000
assert treasury.cash == treasury_before + 1000
```

- [x] **Step 2: Run the new service/API tests and verify expected failures**

Run: `pytest tests/natbirzha/test_state_share_lifecycle.py -q`
Expected: tests fail because the state-share model and routes do not exist, with imports/assertions naming those missing behaviors.

- [x] **Step 3: Add the migration regression test and verify it fails**

Assert the new repeatable migration creates state-share issue, holding, and dividend-settlement tables on both SQLite and PostgreSQL-safe SQL paths and records an idempotent migration version.

- [x] **Step 4: Implement state share data and service**

Create independent issue, holding, and payout models. Creator issuance records an audit entry but does not credit the treasury. Player purchases transfer cash to treasury and decrement available shares. A buyback transfers treasury cash to the seller only when the treasury can cover it, and returns shares to available supply. Store a manually supplied per-share price and projected annual issuer profit; use these as the state instrument's valuation and optional annual dividend basis. Settle daily dividends only from available treasury cash, proportionally when the due amount exceeds that balance, and persist payment operation keys to prevent replay. Register settlement in the existing daily scheduler alongside public-company dividends.

- [x] **Step 5: Implement guarded, idempotent APIs and portfolio output**

Add creator-only `POST /creator/shares/issue` and `GET /creator/shares`; add player `GET /state-shares`, `POST /state-shares/{share_id}/buy`, and `POST /state-shares/{share_id}/sell`. Reuse the existing creator permission helper and `IdempotencyService` for mutations. Include holdings and current value in the portfolio response. Add the migration to `MIGRATIONS` and ensure model imports load before `Base.metadata.create_all`.

- [x] **Step 6: Run lifecycle, migration, and API authorization tests**

Run: `pytest tests/natbirzha/test_state_share_lifecycle.py tests/natbirzha/test_p2_migration_sql.py tests/natbirzha/test_p0_api_hardening.py -q`.
Expected: issuance authorization, idempotency, balances, treasury solvency, holdings, dividends, and migration checks pass.

---

### Task 3: State-panel issuance and player market UI

**Files:**
- Create: `frontend/natbirzha/js/screens/creator_shares.js`
- Create: `frontend/natbirzha/js/screens/state_share_market.js`
- Modify: `frontend/natbirzha/js/screens/creator.js`
- Modify: `frontend/natbirzha/js/screens/stocks.js`
- Modify: `frontend/natbirzha/js/screens/market.js`
- Modify: `frontend/natbirzha/js/screens/market_finance.js`
- Modify: `frontend/natbirzha/js/api.js`
- Test: `tests/natbirzha/test_state_share_frontend_contract.js`

- [x] **Step 1: Add failing frontend contract checks**

Assert the creator State panel has a separate state-shares tab with manual title, volume, share price, projected annual profit, dividend percentage, and purpose fields. Assert the stock screen lists state share issues, shows holdings and available supply, and exposes buy/sell actions backed by the new API methods.

- [x] **Step 2: Run the frontend checks and verify they fail for the missing UI/API methods**

Run: `node tests/test_natbirzha_frontend.js`.
Expected: new assertions fail because the state-share controls and API methods are absent; distinguish any existing ESM harness failure.

- [x] **Step 3: Implement creator and player UI**

Add state-share issuance under the existing Creator/State navigation and require an explicit confirmation that issuance itself creates no money. Add buy and Treasury-backed sell controls to the stock screen, show current price, unissued supply, issuer projection, dividends paid, and the player's share portfolio. Escape all issuer-controlled strings before rendering and refresh cash and holdings after successful trades.

- [x] **Step 4: Verify JavaScript syntax and frontend contract checks**

Run: `node --check frontend/natbirzha/js/screens/creator_shares.js`, `node --check frontend/natbirzha/js/screens/creator.js`, `node --check frontend/natbirzha/js/screens/stocks.js`, `node --check frontend/natbirzha/js/api.js`, and `node tests/test_natbirzha_frontend.js`.
Expected: syntax checks pass and the frontend checks pass, or report the exact unrelated harness blocker if it still prevents execution.

---

### Task 4: Full verification, review, and GitHub delivery

**Files:**
- Review all files changed in Tasks 1–3.

- [x] **Step 1: Run project-required verification**

Run targeted Python integration scripts, `python tests/test_suite.py`, Python compilation for changed backend files, JavaScript syntax checks for changed modules, and available NATBIRZHA tests. Record exact pass/fail counts; repair failures caused by this change.

- [x] **Step 2: Review the diff against this plan**

Check repeated-business opening and unique-business rejection, prerequisite selection, slot growth, cash/resource payback, 40% refund, creator-only issuance, idempotent purchase/sale, treasury balance conservation, share portfolio output, and escaped UI output.

- [ ] **Step 3: Commit, fetch/rebase, and push the approved branch**

Commit the finished change on `codex/business-empire-economy`, fetch `origin`, rebase onto the latest `origin/main` if needed, rerun verification after rebase, and push the branch to `https://github.com/k11298379-sudo/dzbot`. Do not deploy.

**Verification record:** After the final UI trade-serialization fix, 17 focused state-share/backend tests passed; `python tests/test_suite.py` passed all 11 bot test groups; the dedicated state-share frontend contract and JavaScript syntax checks passed. The focused tycoon tests had passed earlier. `node tests/test_natbirzha_frontend.js` remains blocked by its pre-existing CommonJS harness trying to parse the ES-module `import` in `api.js`; the relevant new state-share frontend contract passed independently. Static review approved backend share behavior and UI race handling; backend race coverage uses configured PostgreSQL READ COMMITTED assumptions and simulated recovery rather than a two-connection PostgreSQL race.

---
