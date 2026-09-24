# Bankruptcy Market and NPC Liquidity Caps Implementation Plan

**Goal:** Replace virtual bankruptcy share issuance with real, purchasable asset listings and bound NPC transactions per item/day.

**Architecture:** Persisted bankruptcy-market lots reserve factories, V2 businesses and the bankrupt company's public-share holdings until buyers pay the Treasury. Factory and business lots are priced at recorded/estimated cost basis plus 30%; share lots use the latest stock quote. Forced liquidation sends 70% of each inventory through existing commodity buy orders, destroys the unmatched seized quantity, transfers company cash and government-trading proceeds to Treasury, and returns active state bonds to issue availability. NPC buybacks from players use the existing item/action daily-volume ledger, with a configurable 100,000 cash budget per item and game day converted to quantity at the NPC buy quote.

**Tech Stack:** FastAPI, SQLAlchemy async, existing commodity/stock/bond order books, vanilla JS, script-based test suite.

---

### Task 1: Bound NPC purchases from players per item and day

**Files:** `backend/natbirzha/config.py`, `backend/natbirzha/services/npc_service.py`, `backend/natbirzha/api/market_routes.py`, `frontend/natbirzha/js/screens/market.js`, `frontend/natbirzha/js/api.js`, and NPC tests.

- [x] Add a configurable buyback cash cap per item; derive quantity at the NPC buy quote and retain rare-material NPC supply reserves.
- [x] Use the existing locked `NatNpcDailyVolume` row for aggregate player sales; return a typed quota-exhausted reason and remaining cash/quantity.
- [x] Expose the remaining buyback quota in `/market/npc/rates` and the NPC trade panel.
- [x] Add regression coverage for quota exhaustion and next-day reset.
- [x] Run the focused NPC test and `git diff --check`.

### Task 2: Persist bankruptcy asset listings and migration

**Files:** new `backend/natbirzha/models/bankruptcy_market.py`, `backend/natbirzha/models/__init__.py`, `backend/natbirzha/migrations.py`, and bankruptcy market tests.

- [x] Define listing identity, asset kind/id, seller, share quantity, price, status, buyer, timestamps, and unique operation key.
- [x] Register the model and make the live migration create its table and acquisition flag idempotently.
- [x] Test model creation and repeatable migration on SQLite.

### Task 3: Make creator bankruptcy transfer real assets

**Files:** `backend/natbirzha/services/forced_bankruptcy_service.py`, new `backend/natbirzha/services/bankruptcy_market_service.py`, and `backend/natbirzha/services/market_service.py` only if required for treasury-routed sale proceeds.

- [x] Cover cash transfer, discrete 70% asset seizure, inventory fills/no-bid destruction, share listing, state-bond return, and no new government-share issue.
- [x] Cancel debtor orders and release/refund escrow before liquidation.
- [x] Lock Treasury before company, mark the company bankrupt, create cost-plus-30% enterprise lots, list public holdings, sell resources against bids, and restore active bonds in one transaction.
- [x] Preserve old state-share records; new bankruptcies use real asset lots instead of fictitious share issues.
- [x] Run focused bankruptcy, migration, and NPC regression tests.

### Task 4: Add bankruptcy-market API and player UI

**Files:** new `backend/natbirzha/api/bankruptcy_market_routes.py`, `backend/natbirzha/api/__init__.py`, `frontend/natbirzha/js/screens/bankruptcy_market.js`, `frontend/natbirzha/js/screens/stocks.js`, `frontend/natbirzha/js/screens/market_finance.js`, and `frontend/natbirzha/js/api.js`.

- [x] Add list and idempotent buy endpoints; allow cross-specialization asset purchases while enforcing cash, business uniqueness, and capacity.
- [x] Transfer factory/business ownership or public shares to the buyer; route purchase proceeds to Treasury.
- [x] Add the Bankruptcy Market entry in place of the government-share market entry; keep historical state-share portfolio data readable.
- [x] Test cross-industry factory and share purchases, migration, market listing, and idempotent replay.

### Task 5: Verify complete behavior and publish

- [x] Run focused NPC, bankruptcy, market, stock, bond, migration, and frontend contract checks.
- [x] Run `python tests/test_suite.py` and `python -m compileall -q backend`.
- [x] Review the final diff, commit, and push to `main` so Render auto-deploys.
