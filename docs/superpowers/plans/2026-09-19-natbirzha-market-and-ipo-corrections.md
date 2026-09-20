# NATBIRZHA Market and IPO Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a discoverable IPO flow, make a 5%+ dividend commitment explicit and enforceable, connect listed-share prices to periodic company valuation, remove the accidental energy-sale bottleneck, and make industry choices and sellable own goods understandable.

**Architecture:** Keep the authoritative rules in services and persistent models. Add a dividend policy and valuation timestamp to the stock record through the existing repeatable migration runner. Refresh listed-company valuation lazily at read/trade boundaries under row locks, with a 15-minute gate; the market never trusts a browser price. NPC liquidity remains finite per resource/day, but electricity receives its own producer-facing reserve rather than sharing the small generic cap. The UI receives explicit eligibility, quota and dividend metadata from APIs.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, PostgreSQL/SQLite migration compatibility, vanilla ES modules, Node assertion tests, Python async integration tests.

---

## Scope and Evidence

- The IPO route and modal still exist (`backend/natbirzha/api/stock_routes.py`, `frontend/natbirzha/js/screens/stocks.js`), but the modal only estimates NAV from stale client state and offers no dividend policy.
- Dividends are currently a hard-coded global 10% (`DividendService` reads `DIVIDEND_POOL_PCT`), so the UI cannot show an issuer obligation.
- `NatStock.current_price` changes only on a trade, while `last_valuation` is never refreshed after IPO.
- NPC quota is global by item+direction+day and scales down with player count. The reported “600 energy then no more” is therefore a hidden liquidity cap, not a one-off resource bug.
- The own-industry yellow prioritization was already implemented in commit `9e361a0`; preserve it and make its intent visible in the UI.

## Task 1: Persist an issuer dividend policy and valuation refresh time

**Files:**
- Modify: `backend/natbirzha/models/stocks.py`
- Modify: `backend/natbirzha/migrations.py`
- Modify: `backend/natbirzha/config.py`
- Test: `tests/natbirzha/test_stock_market_rules.py`

- [ ] **Step 1: Write failing model/migration tests.**
  - Create `tests/natbirzha/test_stock_market_rules.py` with an async schema setup.
  - Assert a new IPO defaults to `dividend_rate_pct == 5.0` when no optional higher rate is supplied.
  - Assert legacy-column migration can add `dividend_rate_pct` and `valuation_updated_at` safely on SQLite and PostgreSQL-compatible DDL.

- [ ] **Step 2: Run the test to confirm RED.**
  - Run: `python tests/natbirzha/test_stock_market_rules.py`
  - Expected: failure because `NatStock` does not yet expose the fields or IPO does not accept a rate.

- [ ] **Step 3: Add the minimal persisted fields and settings.**
  - Add to `NatStock`:
    ```python
    dividend_rate_pct: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    valuation_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ```
  - Add settings `IPO_MIN_DIVIDEND_PCT = 5.0`, `IPO_MAX_DIVIDEND_PCT = 50.0`, and `STOCK_VALUATION_REFRESH_MINUTES = 15`.
  - Add migration version `natbirzha_p2_004_stock_policy` using `_add_columns`, with compatible defaults; do not rewrite already-existing rows destructively.

- [ ] **Step 4: Run the focused test to confirm GREEN.**
  - Run: `python tests/natbirzha/test_stock_market_rules.py`
  - Expected: new fields and migration behavior pass.

- [ ] **Step 5: Commit the schema foundation.**
  - `git add backend/natbirzha/models/stocks.py backend/natbirzha/migrations.py backend/natbirzha/config.py tests/natbirzha/test_stock_market_rules.py`
  - `git commit -m "feat(natbirzha): persist stock dividend policy and valuation time"`

## Task 2: Make IPO dividend terms explicit and enforce the 5% minimum

**Files:**
- Modify: `backend/natbirzha/services/stock_service.py`
- Modify: `backend/natbirzha/services/dividend_service.py`
- Modify: `backend/natbirzha/api/stock_routes.py`
- Modify: `frontend/natbirzha/js/api.js`
- Modify: `frontend/natbirzha/js/screens/stocks.js`
- Modify: `tests/natbirzha/test_stock_market_rules.py`
- Modify: `tests/test_natbirzha_frontend.js`

- [ ] **Step 1: Add failing service/API tests.**
  - Verify `StockService.apply_for_ipo(..., dividend_rate_pct=4.99)` raises a validation error.
  - Verify a 5% IPO persists the rate and reports it from `/stocks/market`.
  - Verify dividend settlement uses `stock.dividend_rate_pct / 100`, not the global fixed 10%.

- [ ] **Step 2: Run RED tests.**
  - Run: `python tests/natbirzha/test_stock_market_rules.py`
  - Expected: rate parameter and per-stock calculation are missing.

- [ ] **Step 3: Implement a narrow public API.**
  - Add `IPOApplyRequest` with `dividend_rate_pct: float = Field(default=5.0, ge=5.0, le=50.0)`.
  - Pass it from `apply_for_ipo` route to `StockService.apply_for_ipo` and persist it with `valuation_updated_at=now`.
  - Update `DividendService.settle_daily_dividends_for_stock` to derive its policy from the stock; retain the global setting only as a safe fallback for pre-migration rows.
  - Include `dividend_rate_pct` and `valuation_updated_at` in market and portfolio payloads.

- [ ] **Step 4: Add the IPO UI contract.**
  - Change `NatAPI.issueIPO` to pass `{ dividend_rate_pct }`.
  - In `stocks.js`, show IPO eligibility (`level`, `IPO_MIN_LEVEL`) and a numeric policy choice with 5% minimum.
  - Include a concise confirmation: “Обязательные дивиденды: X% от чистой дневной прибыли; ниже 5% нельзя.”
  - For public issuers and buyer cards, display the actual rate rather than hard-coded “10%”.

- [ ] **Step 5: Run focused frontend/backend verification.**
  - Run: `python tests/natbirzha/test_stock_market_rules.py`
  - Run: `node tests/test_natbirzha_frontend.js`
  - Run: `node --check frontend/natbirzha/js/screens/stocks.js`

- [ ] **Step 6: Commit.**
  - `git add backend/natbirzha/services/stock_service.py backend/natbirzha/services/dividend_service.py backend/natbirzha/api/stock_routes.py frontend/natbirzha/js/api.js frontend/natbirzha/js/screens/stocks.js tests/natbirzha/test_stock_market_rules.py tests/test_natbirzha_frontend.js`
  - `git commit -m "feat(natbirzha): require and show IPO dividend policy"`

## Task 3: Refresh listed stock prices from company valuation every 15 minutes

**Files:**
- Modify: `backend/natbirzha/services/stock_service.py`
- Modify: `backend/natbirzha/api/stock_routes.py`
- Modify: `tests/natbirzha/test_stock_market_rules.py`

- [ ] **Step 1: Create a failing valuation-refresh test.**
  - Set up a listed company with a known initial valuation and an old `valuation_updated_at`.
  - Change its cash/NAV, then call a public `StockService.refresh_due_valuations(session, now=...)`.
  - Assert `last_valuation` and `current_price == round(valuation / total_shares, 2)` change.
  - Call it again within 15 minutes and assert no recalculation occurs.

- [ ] **Step 2: Run RED.**
  - Run: `python tests/natbirzha/test_stock_market_rules.py`
  - Expected: refresh method missing.

- [ ] **Step 3: Implement the service-level recalculation.**
  - Add `refresh_due_valuations(session, now=None)` that selects public stocks, locks each row, and only recalculates when `valuation_updated_at` is absent or older than the configured interval.
  - Reuse the same strategy and financial-history lookup as IPO via a private helper, so IPO and refresh cannot drift.
  - Never overwrite a newer trade price inside the 15-minute gate; when due, the valuation price becomes the new quoted reference price.
  - Call the refresh before `/stocks/market`, `/stocks/portfolio`, and buy/sell processing. It must be idempotent inside the gate.

- [ ] **Step 4: Run GREEN and regression tests.**
  - Run: `python tests/natbirzha/test_stock_market_rules.py`
  - Run: `python tests/natbirzha/test_idempotency_and_stocks.py`

- [ ] **Step 5: Commit.**
  - `git add backend/natbirzha/services/stock_service.py backend/natbirzha/api/stock_routes.py tests/natbirzha/test_stock_market_rules.py`
  - `git commit -m "feat(natbirzha): revalue public shares every fifteen minutes"`

## Task 4: Fix NPC electricity liquidity and surface a useful quota

**Files:**
- Modify: `backend/natbirzha/config.py`
- Modify: `backend/natbirzha/services/npc_service.py`
- Modify: `backend/natbirzha/api/market_routes.py`
- Modify: `frontend/natbirzha/js/screens/market.js`
- Modify: `tests/natbirzha/test_npc_liquidity_service.py`
- Modify: `tests/test_natbirzha_frontend.js`

- [ ] **Step 1: Write a failing test that reproduces the reported cap.**
  - Seed a power company with 600 energy.
  - Assert a SELL request for the entire amount succeeds even when generic per-item quota would be lower.
  - Assert a second sale reports a readable remaining quantity, while BUY reserves for premium resources remain unchanged.

- [ ] **Step 2: Run RED.**
  - Run: `python tests/natbirzha/test_npc_liquidity_service.py`
  - Expected: SELL of 600 energy fails because it uses the generic quota.

- [ ] **Step 3: Add a bounded producer liquidity policy.**
  - Add `NPC_SELL_DAILY_QUOTAS` with a high but finite value for `energy` (e.g. 10,000) and use it only for `action == "SELL"`.
  - Keep separate, global item/day reserve accounting so the state cannot purchase unlimited energy; the capacity is now economically usable for a primary producer.
  - Return `daily_quota`, `remaining_npc_quota`, and a human-readable `quota_label` from the rate endpoint and trade response.
  - Do not alter rare-resource NPC BUY caps.

- [ ] **Step 4: Display the limit before the player submits.**
  - In the NPC selling interface, show the current item’s remaining state demand next to the sell controls.
  - Preserve yellow own-industry cards from commit `9e361a0` and add a short “Ваша отрасль” label, so the player can find sellable outputs immediately.

- [ ] **Step 5: Verify.**
  - Run: `python tests/natbirzha/test_npc_liquidity_service.py`
  - Run: `node tests/test_natbirzha_frontend.js`
  - Run: `node --check frontend/natbirzha/js/screens/market.js`

- [ ] **Step 6: Commit.**
  - `git add backend/natbirzha/config.py backend/natbirzha/services/npc_service.py backend/natbirzha/api/market_routes.py frontend/natbirzha/js/screens/market.js tests/natbirzha/test_npc_liquidity_service.py tests/test_natbirzha_frontend.js`
  - `git commit -m "fix(natbirzha): make electricity NPC demand usable and visible"`

## Task 5: Make specialization choice and IPO route discoverable

**Files:**
- Modify: `frontend/natbirzha/js/screens/onboarding.js`
- Modify: `frontend/natbirzha/js/screens/stocks.js`
- Modify: `tests/test_natbirzha_frontend.js`

- [ ] **Step 1: Write failing static/UI-contract tests.**
  - Assert onboarding contains an “Открыто с начала” legend, an explicit non-selectable “Будущие отрасли” section, and a starter output for every selectable specialization.
  - Assert Stocks screen visibly says IPO unlocks at company level 2 and has an `open-ipo-btn` for eligible private companies.

- [ ] **Step 2: Run RED.**
  - Run: `node tests/test_natbirzha_frontend.js`
  - Expected: the explicit availability guidance is absent.

- [ ] **Step 3: Implement the entry UX.**
  - Keep the current eight selectable starter industries, but add a short “доступно сейчас” card explaining every choice is available at registration.
  - Add a disabled, clearly marked future-expansion list (premium/new-era industries), not fake selectable buttons.
  - Add each starter factory/output directly in the specialization card to prevent a player selecting an industry whose product they cannot identify.
  - On the IPO card, show the exact current company level and the unlock condition rather than appearing to lose the feature when the player is under level 2.

- [ ] **Step 4: Run frontend verification.**
  - Run: `node tests/test_natbirzha_frontend.js`
  - Run: `node --check frontend/natbirzha/js/screens/onboarding.js`
  - Run: `node --check frontend/natbirzha/js/screens/stocks.js`

- [ ] **Step 5: Commit.**
  - `git add frontend/natbirzha/js/screens/onboarding.js frontend/natbirzha/js/screens/stocks.js tests/test_natbirzha_frontend.js`
  - `git commit -m "fix(natbirzha): explain industry and IPO availability"`

## Task 6: Final verification and deploy handoff

- [ ] **Step 1: Run the integrated verification suite.**
  - Run: `python tests/natbirzha/test_stock_market_rules.py`
  - Run: `python tests/natbirzha/test_idempotency_and_stocks.py`
  - Run: `python tests/natbirzha/test_npc_liquidity_service.py`
  - Run: `node tests/test_natbirzha_frontend.js`
  - Run syntax checks for every touched ES module.

- [ ] **Step 2: Inspect migration portability.**
  - Run the migration tests against the configured local database and inspect `git diff --check`.
  - Confirm the old boolean migration continues to use `_bond_inactive_expression`, not `boolean = integer`.

- [ ] **Step 3: Prepare publication.**
  - Check `git status --short` and `git log --oneline origin/main..HEAD`.
  - Push only after GitHub credentials are available; if authentication still fails, report the exact blocker and leave the commits intact for the authorized developer.
