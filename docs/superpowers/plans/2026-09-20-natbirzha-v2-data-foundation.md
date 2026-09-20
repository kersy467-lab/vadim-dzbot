# НАТБИРЖА 2.0 Data Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the version 2 business schema and server-owned catalog without changing the active gameplay UI.

**Architecture:** Business rows hold mutable player state; immutable progression formulas live in small catalog modules. Related assets use separate SQLAlchemy models. A repeatable migration creates all new tables in existing SQLite and PostgreSQL installations, while `TYCOON_V2_ENABLED` keeps the feature inactive.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async ORM, SQLite/PostgreSQL, pytest.

---

### Task 1: Define isolated business state models

**Files:**

- Create: `backend/natbirzha/models/business.py`
- Create: `backend/natbirzha/models/business_assets.py`
- Create: `backend/natbirzha/models/military_infrastructure.py`
- Modify: `backend/natbirzha/models/__init__.py`
- Test: `tests/natbirzha/test_tycoon_v2_models.py`

- [ ] **Step 1: Write the failing schema tests**

```python
assert {"nat_businesses", "nat_business_supply_policies", "nat_business_income_daily"} <= set(Base.metadata.tables)
assert NatBusiness.__table__.c.stage.default.arg == 1
assert {"ACTIVE", "UPGRADING", "PAUSED_MANUAL"} <= BUSINESS_STATUSES
```

- [ ] **Step 2: Run the focused test and verify the missing-import failure**

Run: `python -m pytest -q tests/natbirzha/test_tycoon_v2_models.py`

- [ ] **Step 3: Implement minimal models**

`NatBusiness` has `company_id`, `business_type`, `stage`, `status`, `capital_invested`, rate fields, `last_settled_at`, upgrade timestamps, `health`, `efficiency`, `slot_weight` and metadata. Asset models hold only the fields specified in the approved 2.0 design.

- [ ] **Step 4: Run focused schema tests**

Run: `python -m pytest -q tests/natbirzha/test_tycoon_v2_models.py`

- [ ] **Step 5: Commit**

```bash
git add backend/natbirzha/models tests/natbirzha/test_tycoon_v2_models.py
git commit -m "feat(natbirzha): add tycoon business data models"
```

### Task 2: Add a server-owned business catalog

**Files:**

- Create: `backend/natbirzha/catalogs/businesses/starter.py`
- Create: `backend/natbirzha/catalogs/businesses/industry.py`
- Create: `backend/natbirzha/catalogs/businesses/services.py`
- Create: `backend/natbirzha/catalogs/businesses/__init__.py`
- Test: `tests/natbirzha/test_tycoon_v2_catalog.py`

- [ ] **Step 1: Write failing catalog invariants**

```python
assert BUSINESS_CATALOG["retail_chain"]["max_stage"] == 20
assert BUSINESS_CATALOG["retail_chain"]["open_cost"] == 8_000
assert BUSINESS_CATALOG["energy_company"]["outputs_per_hour"] == {"energy": 8.0}
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m pytest -q tests/natbirzha/test_tycoon_v2_catalog.py`

- [ ] **Step 3: Implement starter catalog entries**

Define `retail_chain`, `agroholding`, `energy_company`, `water_utility`, `mining_company` and `oil_gas_company` with server-owned progression data. Do not implement settlement in this commit.

- [ ] **Step 4: Run focused catalog tests**

Run: `python -m pytest -q tests/natbirzha/test_tycoon_v2_catalog.py`

- [ ] **Step 5: Commit**

```bash
git add backend/natbirzha/catalogs tests/natbirzha/test_tycoon_v2_catalog.py
git commit -m "feat(natbirzha): add tycoon business catalog"
```

### Task 3: Register repeatable migration and rollout flag

**Files:**

- Modify: `backend/natbirzha/config.py`
- Modify: `backend/natbirzha/migrations.py`
- Test: `tests/natbirzha/test_tycoon_v2_migrations.py`

- [ ] **Step 1: Write migration and flag tests**

```python
assert nat_settings.TYCOON_V2_ENABLED is False
assert "natbirzha_v2_001_business_foundation" in [version for version, _ in MIGRATIONS]
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `python -m pytest -q tests/natbirzha/test_tycoon_v2_migrations.py`

- [ ] **Step 3: Add migration**

Create every V2 table with `CREATE TABLE IF NOT EXISTS` and indexes compatible with SQLite and PostgreSQL. Add `TYCOON_V2_ENABLED=False` to settings.

- [ ] **Step 4: Run focused migration tests**

Run: `python -m pytest -q tests/natbirzha/test_tycoon_v2_migrations.py`

- [ ] **Step 5: Commit**

```bash
git add backend/natbirzha/config.py backend/natbirzha/migrations.py tests/natbirzha/test_tycoon_v2_migrations.py
git commit -m "feat(natbirzha): register tycoon v2 schema migration"
```

### Task 4: Verify the first rollout-safe foundation

**Files:**

- Test: `tests/natbirzha/test_tycoon_v2_models.py`
- Test: `tests/natbirzha/test_tycoon_v2_catalog.py`
- Test: `tests/natbirzha/test_tycoon_v2_migrations.py`

- [ ] **Step 1: Run syntax validation**

Run: `python -m py_compile backend/natbirzha/models/business.py backend/natbirzha/models/business_assets.py backend/natbirzha/models/military_infrastructure.py`

- [ ] **Step 2: Run the focused suite**

Run: `python -m pytest -q tests/natbirzha/test_tycoon_v2_models.py tests/natbirzha/test_tycoon_v2_catalog.py tests/natbirzha/test_tycoon_v2_migrations.py`

- [ ] **Step 3: Run repository verification**

Run: `python tests/test_suite.py`

- [ ] **Step 4: Commit the planning record**

```bash
git add docs/superpowers/specs/2026-09-20-natbirzha-idle-tycoon-design.md docs/superpowers/plans/2026-09-20-natbirzha-v2-data-foundation.md
git commit -m "docs(natbirzha): plan idle tycoon v2 foundation"
```
