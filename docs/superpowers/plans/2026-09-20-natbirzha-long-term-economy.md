# NATBIRZHA Long-Term Economy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a measurable, long-lived economic progression without turning early PVC into pay-to-win.

**Architecture:** The backend owns every balance rule; catalog data provides bases and services derive outcomes. The Mini App only renders authoritative API responses, so changing tabs cannot mutate game state.

**Tech Stack:** FastAPI, async SQLAlchemy, PostgreSQL/SQLite-compatible migrations, vanilla ES modules, Python and Node script tests.

## Implementation status · 2026-09-20

- [x] Economy telemetry records production, NPC cash flows, construction/upgrades, recruitment, territory, PvE and financing; creator dashboard exposes a 7-day source/sink summary.
- [x] Repeat PvE uses one quadratic frontier multiplier, first-win-only land, combined-arms gates, cooldowns and loss-based cash compensation capped below cash recovery cost.
- [x] Post-60 mastery has four soft-capped branches with diminishing returns and no direct PvP damage bonus.
- [x] Midgame debt is available from level 14, capped at 35% of net NAV, accrues daily interest, blocks new borrowing after default and can be repaid from the overview.
- [x] Creator self-grants are self-only, rate-limited per operation, audited and measured; season reset remains feature-flagged with preview/backup controls.
- [x] Theme fallback/cache-busting removes the accidental gray/white visual fallback.
- [x] `git diff --check`, Python compile-all, JS syntax checks and `tests/test_natbirzha_frontend.js` pass.
- [ ] DB-backed Python suite is pending in this container because the required `aiosqlite>=0.20.0` package is not installed; the suite fails during engine import before test code executes.
- [ ] Production GitHub push is pending because the linked GitHub installation currently exposes zero repositories to the connector.

---

## Accepted baseline

- Company levels are capped at 60; mastery ranks after 60 are unbounded.
- Automation starts at level 6, consumes existing inputs and never secretly buys them.
- IPO starts at level 2 with a 5–50% dividend policy. A non-blocking capital recommendation appears from level 14 when self-funding fails.
- PvP is only in the 18-hour tournament window. PvE has a two-hour post-win cooldown and mixed-army gates.
- PVC licenses last 48 real hours; rare materials remain player-tradable and never gate early progression.

### Task 1: Instrument sources and sinks before changing more prices

**Files:**

- Create: `backend/natbirzha/models/economy_metrics.py`
- Create: `backend/natbirzha/services/economy_metrics_service.py`
- Modify: `backend/natbirzha/services/production_service.py`
- Modify: `backend/natbirzha/services/npc_service.py`
- Modify: `backend/natbirzha/services/pve_service.py`
- Test: `tests/natbirzha/test_economy_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
event = await EconomyMetricsService.record(session, company.id, "PVE_LOSS", cash_delta=-2000, item_delta={"steel": -3})
summary = await EconomyMetricsService.summary(session, company.id)
assert event.event_type == "PVE_LOSS"
assert summary["cash_sinks"] == 2000
assert summary["item_sinks"]["steel"] == 3
```

- [ ] **Step 2: Run RED**

Run: `$env:PYTHONPATH='.'; python tests/natbirzha/test_economy_metrics.py`

- [ ] **Step 3: Implement the append-only metric event**

```python
class NatEconomyMetric(Base):
    __tablename__ = "nat_economy_metrics"
    company_id: Mapped[int] = mapped_column(ForeignKey("nat_companies.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    cash_delta: Mapped[float] = mapped_column(Float, default=0.0)
    item_delta: Mapped[dict] = mapped_column(JSON, default=dict)
```

Record only completed production, NPC trades, recruitment, upgrades and resolved PvE results. Add a repeatable migration and do not record failed/idempotent replays.

- [ ] **Step 4: Run GREEN**

Run: `$env:PYTHONPATH='.'; python tests/natbirzha/test_economy_metrics.py; python tests/test_suite.py`

- [ ] **Step 5: Commit**

```powershell
git add backend/natbirzha/models/economy_metrics.py backend/natbirzha/services/economy_metrics_service.py backend/natbirzha/migrations.py tests/natbirzha/test_economy_metrics.py
git commit -m "feat(natbirzha): measure economy sources and sinks"
```

### Task 2: Make repeatable PvE scale instead of becoming a farm

**Files:**

- Modify: `backend/natbirzha/services/pve_service.py`
- Modify: `frontend/natbirzha/js/screens/military.js`
- Test: `tests/natbirzha/test_pve_wars.py`

- [ ] **Step 1: Write the failing test**

```python
first = await PveService.scout_target(session, company, "local_logistics")
await win_local_logistics(session, company, now)
await replenish_and_wait_two_hours(session, company, now)
repeat = await PveService.scout_target(session, company, "local_logistics")
assert repeat["campaign_rank"] == 1
assert repeat["strength_range"]["min"] > first["strength_range"]["min"]
```

- [ ] **Step 2: Run RED**

Run: `$env:PYTHONPATH='.'; python tests/natbirzha/test_pve_wars.py`

- [ ] **Step 3: Implement one shared scaling function**

```python
def _campaign_multiplier(wins: int) -> float:
    return round(1.0 + 0.18 * wins + 0.02 * wins * wins, 4)

def _scaled_units(base: dict[str, int], wins: int) -> dict[str, int]:
    return {unit: max(1, ceil(count * _campaign_multiplier(wins))) for unit, count in base.items()}
```

Use the same scaled snapshot in list, scout and attack. First win gives land; repeats give cash, XP and rating only, preventing infinite land from one tiny target.

- [ ] **Step 4: Render campaign state**

```javascript
<div class="text-[10px]">Фронтир ${target.campaign_rank + 1} · ${target.repeatable ? 'повтор без новой земли' : ''}</div>
```

Keep the attack button available once `cooldown_until` expires.

- [ ] **Step 5: Run GREEN and commit**

Run: `$env:PYTHONPATH='.'; python tests/natbirzha/test_pve_wars.py; node tests/test_natbirzha_frontend.js`

Commit: `feat(natbirzha): scale repeat PvE frontiers`

### Task 3: Give post-60 mastery a soft-capped choice

**Files:**

- Create: `backend/natbirzha/services/mastery_service.py`
- Modify: `backend/natbirzha/models/company.py`
- Modify: `backend/natbirzha/api/company_routes.py`
- Modify: `frontend/natbirzha/js/screens/upgrades.js`
- Test: `tests/natbirzha/test_mastery_service.py`

- [ ] **Step 1: Write the failing test**

```python
company.mastery_rank = 4
company.mastery_points = 2
result = MasteryService.unlock(session, company, "supply_chain")
assert result["level"] == 1
assert result["effect"] == "cycle_input_discount"
assert company.mastery_points == 1
```

- [ ] **Step 2: Run RED**

Run: `$env:PYTHONPATH='.'; python tests/natbirzha/test_mastery_service.py`

- [ ] **Step 3: Implement three branches**

```python
MASTERY_BRANCHES = {
    "supply_chain": {"max_level": 20, "effect": "cycle_input_discount", "per_level": 0.005},
    "maintenance": {"max_level": 20, "effect": "factory_recovery", "per_level": 0.004},
    "frontier": {"max_level": 20, "effect": "pve_scout_precision", "per_level": 0.01},
}
```

Award one non-transferable point per rank. Apply diminishing, capped bonuses only; do not use mastery for direct PvP damage.

- [ ] **Step 4: Run GREEN and commit**

Run: `$env:PYTHONPATH='.'; python tests/natbirzha/test_mastery_service.py; python tests/test_suite.py`

Commit: `feat(natbirzha): add post-60 mastery choices`

### Task 4: Build the alternative to IPO at the capital wall

**Files:**

- Create: `backend/natbirzha/services/loan_service.py`
- Modify: `backend/natbirzha/models/instruments.py`
- Modify: `frontend/natbirzha/js/screens/market.js`
- Test: `tests/natbirzha/test_loan_service.py`

- [ ] **Step 1: Write the failing test**

```python
loan = await LoanService.issue(session, company, principal=80000, term_days=7)
assert loan.outstanding_principal == 80000
assert company.cash == cash_before + 80000
assert loan.daily_rate > 0
```

- [ ] **Step 2: Run RED**

Run: `$env:PYTHONPATH='.'; python tests/natbirzha/test_loan_service.py`

- [ ] **Step 3: Implement auditable debt**

```python
MAX_DEBT_TO_NAV = 0.35
LOAN_DAILY_RATE = 0.012
```

At levels 14–25 show IPO (up to 40% float, dividends from 5%) next to debt (ownership retained, daily obligation). Block new debt over the NAV ratio and show repayment in the portfolio.

- [ ] **Step 4: Run GREEN and commit**

Run: `$env:PYTHONPATH='.'; python tests/natbirzha/test_loan_service.py; node tests/test_natbirzha_frontend.js`

Commit: `feat(natbirzha): add midgame debt alternative`

### Task 5: Add safe creator tools and the explicit season reset

**Files:**

- Modify: `backend/natbirzha/api/creator_routes.py`
- Modify: `frontend/natbirzha/js/screens/creator.js`
- Modify: `backend/natbirzha/services/company_service.py`
- Test: `tests/natbirzha/test_creator_controls.py`

- [ ] **Step 1: Write the failing test**

```python
response = await creator_client.post("/api/natbirzha/creator/me/grant", json={"cash": 200000, "pvc": 150})
assert response.status_code == 200
assert response.json()["cash_after"] == 200000
assert normal_client.post("/api/natbirzha/creator/me/grant", json={"cash": 1}).status_code == 403
```

- [ ] **Step 2: Run RED**

Run: `$env:PYTHONPATH='.'; python tests/natbirzha/test_creator_controls.py`

- [ ] **Step 3: Implement creator restrictions**

```python
async def grant_to_self(creator: User, company: NatCompany, cash: float, pvc: int) -> dict:
    if company.user_id != creator.id:
        raise HTTPException(status_code=403, detail="Self grant only")
```

List company name, level, NAV, cash, land and military rating for the creator. Grants are self-only. Keep global reset behind `SEASON_RESET_ENABLED`, show a dry-run count and require a second confirmation token.

- [ ] **Step 4: Run GREEN and commit**

Run: `$env:PYTHONPATH='.'; python tests/natbirzha/test_creator_controls.py; python tests/test_suite.py`

Commit: `feat(natbirzha): add safe creator operations`

## Acceptance simulation before every production push

- Fresh player reaches first NPC sale in minutes and automation at level 6 through meaningful choices.
- A level-14 cash-poor player sees IPO/debt options; a wealthy player does not see a false emergency.
- 20k of pure infantry cannot enter PvE; repeat PvE needs replenishment, waits two hours and scales up.
- XP after 60 changes mastery rank/points but never exceeds company level 60.
- Telegram ID maps to one company on phone and desktop. Only creator sees the full player list; reset stays disabled unless explicitly enabled.

## Research basis

This uses the source/sink balancing and telemetry-driven iteration described by [Unity’s economy guide](https://activation.unity3d.com/how-to/building-game-economy-guide-part-2) and [GDC’s sink-design session](https://www.gdcvault.com/play/1021008/Economic-Balancing-and-Improved-Monetization).
