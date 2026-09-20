# NATBIRZHA Progression and Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ten-minute five-level progression with a scalable 60-level company loop and introduce safe, visible factory automation that automatically starts and collects cycles without buying inputs or losing resources.

**Architecture:** Preserve the existing authoritative `ProductionTickEngine` and extend it with deterministic automation behavior. Company-level math is centralised in a progression service, so API progress display, recipe eligibility, slot unlocks and XP awarding agree. Automation is opt-in per factory and has a persistent state reason; a scheduled tick may complete a ready cycle then start exactly one next cycle when enabled. The first automation tier provides the user-facing “works while I am away” behavior; higher tiers improve efficiency and resilience but never place market orders.

**Tech Stack:** Python 3.14, FastAPI, SQLAlchemy async, existing repeatable migrations, vanilla ES modules, Python async tests.

---

## Scope boundaries

- This plan is the safe foundation for the approved infinite-progression design in `docs/superpowers/specs/2026-09-19-natbirzha-infinite-progression-design.md`.
- It implements the progression formula, automation state machine, UI and migration first. Content expansion (new eras, factories, army and research tree) follows through data catalog additions after the foundation is live, rather than shipping hundreds of unbalanced objects at once.
- Automation does **not** buy inputs, spend PVC, make P2P/NPC trades, or silently discard output. It pauses with a reason when it cannot proceed.

## Task 1: Centralise 60-level company progression

**Files:**
- Create: `backend/natbirzha/services/progression_service.py`
- Modify: `backend/natbirzha/config.py`
- Modify: `backend/natbirzha/services/production_service.py`
- Modify: `backend/natbirzha/api/company_routes.py`
- Test: `tests/natbirzha/test_progression_service.py`

- [ ] **Step 1: Write failing progression tests.**
  - Define expected thresholds for levels 1, 5, 10, 30 and 60 using an explicit cumulative formula.
  - Assert XP from production can advance multiple levels but never above `COMPANY_MAX_LEVEL = 60`.
  - Assert API `next_level_xp`/`xp_to_next` work at 60 instead of retaining the current hard-coded level-10 behavior.

- [ ] **Step 2: Run RED.**
  - Run: `python tests/natbirzha/test_progression_service.py`
  - Expected: module absent and existing API caps at 10.

- [ ] **Step 3: Implement the minimal progression service.**
  - Add configuration for six ten-level eras and an explicit `xp_required_for_level(level)` curve, where late levels take materially more XP than early levels.
  - Provide `apply_xp(company, amount)` and `progress_snapshot(company)`; these are the only source of truth for level updates and UI values.
  - Replace the inline `while company.level < 10` loop in `ProductionTickEngine.complete_cycle` and the magic `level * 150` response in `company_routes.py`.

- [ ] **Step 4: Verify GREEN.**
  - Run: `python tests/natbirzha/test_progression_service.py`
  - Run: `python tests/natbirzha/test_registration_production_cycle.py`

- [ ] **Step 5: Commit.**
  - `git add backend/natbirzha/services/progression_service.py backend/natbirzha/config.py backend/natbirzha/services/production_service.py backend/natbirzha/api/company_routes.py tests/natbirzha/test_progression_service.py`
  - `git commit -m "feat(natbirzha): add scalable sixty-level progression"`

## Task 2: Persist safe factory automation state

**Files:**
- Modify: `backend/natbirzha/models/company.py`
- Modify: `backend/natbirzha/migrations.py`
- Modify: `backend/natbirzha/services/upgrade_service.py`
- Test: `tests/natbirzha/test_factory_automation.py`

- [ ] **Step 1: Write a failing persistence test.**
  - Assert a factory can persist `automation_enabled`, `automation_status`, and `automation_pause_reason`.
  - Assert level-0 automation cannot be enabled and automation unlocks only from the approved mid-early progression gate (company level 6).

- [ ] **Step 2: Run RED.**
  - Run: `python tests/natbirzha/test_factory_automation.py`
  - Expected: fields and guard do not exist.

- [ ] **Step 3: Add model/migration/upgrade rules.**
  - Add fields on `NatFactory`:
    ```python
    automation_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    automation_status: Mapped[str] = mapped_column(String(32), default="MANUAL", nullable=False)
    automation_pause_reason: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    ```
  - Add repeatable migration `natbirzha_p2_005_progression_automation`.
  - Expand `UpgradeService.MAX_LEVELS["automation"]` to 10 and gate the first automation upgrade at company level 6; later tiers use the era curve.
  - Maintain backward compatibility: existing automation levels only keep their speed bonus until a player explicitly turns automation on.

- [ ] **Step 4: Verify GREEN.**
  - Run: `python tests/natbirzha/test_factory_automation.py`

- [ ] **Step 5: Commit.**
  - `git add backend/natbirzha/models/company.py backend/natbirzha/migrations.py backend/natbirzha/services/upgrade_service.py tests/natbirzha/test_factory_automation.py`
  - `git commit -m "feat(natbirzha): persist factory automation state"`

## Task 3: Implement the authoritative automatic cycle state machine

**Files:**
- Modify: `backend/natbirzha/services/production_service.py`
- Modify: `backend/natbirzha/api/production_routes.py`
- Test: `tests/natbirzha/test_factory_automation.py`

- [ ] **Step 1: Add failing state-machine tests.**
  - Given enabled automation and enough inputs, assert scheduled processing completes a ready cycle and starts one new one, with output credited exactly once.
  - Given insufficient inputs, assert it does not start, does not remove inputs/cash and stores a deterministic pause reason such as `insufficient_energy`.
  - Given inventory overflow, assert it keeps the completed cycle ready for manual collection rather than losing output.
  - Call scheduled processing twice at the same timestamp and assert no duplicate production.

- [ ] **Step 2: Run RED.**
  - Run: `python tests/natbirzha/test_factory_automation.py`
  - Expected: current scheduled tick completes cycles but never auto-starts and has no state explanation.

- [ ] **Step 3: Implement a single-cycle automation transition.**
  - Add a private `ProductionTickEngine._advance_automation_locked(...)` that may: complete a ready cycle; then start one cycle only when `automation_enabled`; update status to `RUNNING`, `WAITING_INPUTS`, `WAITING_COLLECTION`, `IDLE`, or `MANUAL`.
  - Use existing `_start_cycle_locked` and `_complete_cycle_locked`, so costs, licenses, efficiency and inventory caps remain identical to manual production.
  - Extend `process_global_scheduled_tick` to call this helper while holding existing factory locks; no browser action is required.
  - Add `POST /production/factories/{factory_id}/automation` with explicit `{ enabled: bool }` and return the full factory state.

- [ ] **Step 4: Run GREEN plus production regressions.**
  - Run: `python tests/natbirzha/test_factory_automation.py`
  - Run: `python tests/natbirzha/test_registration_production_cycle.py`
  - Run: `python tests/natbirzha/test_audit_fixes.py`

- [ ] **Step 5: Commit.**
  - `git add backend/natbirzha/services/production_service.py backend/natbirzha/api/production_routes.py tests/natbirzha/test_factory_automation.py`
  - `git commit -m "feat(natbirzha): automate safe factory production cycles"`

## Task 4: Make automation and long progression visible in the Mini App

**Files:**
- Modify: `frontend/natbirzha/js/api.js`
- Modify: `frontend/natbirzha/js/screens/production.js`
- Modify: `frontend/natbirzha/js/screens/upgrades.js`
- Modify: `frontend/natbirzha/js/screens/overview.js`
- Modify: `tests/test_natbirzha_frontend.js`

- [ ] **Step 1: Write failing frontend contract tests.**
  - Assert a factory card exposes an automation toggle, visible status and pause reason.
  - Assert overview renders company level progress from server fields and does not hard-code a level-10 cap.
  - Assert the automation label makes its boundary clear: automatic start/collection, but no automatic purchasing of missing inputs.

- [ ] **Step 2: Run RED.**
  - Run: `node tests/test_natbirzha_frontend.js`

- [ ] **Step 3: Add API client and UI controls.**
  - Add `NatAPI.setFactoryAutomation(factoryId, enabled)`.
  - Show a compact switch on production cards only when automation tier is unlocked; otherwise show unlock level and upgrade path.
  - Make `WAITING_INPUTS` a useful Russian message identifying the exact missing input.
  - Update the upgrade card to show ten automation tiers and its current effect (speed/throughput as configured), without promising unsupported auto-buy behavior.

- [ ] **Step 4: Verify.**
  - Run: `node tests/test_natbirzha_frontend.js`
  - Run: `node --check frontend/natbirzha/js/api.js`
  - Run: `node --check frontend/natbirzha/js/screens/production.js`
  - Run: `node --check frontend/natbirzha/js/screens/upgrades.js`
  - Run: `node --check frontend/natbirzha/js/screens/overview.js`

- [ ] **Step 5: Commit.**
  - `git add frontend/natbirzha/js/api.js frontend/natbirzha/js/screens/production.js frontend/natbirzha/js/screens/upgrades.js frontend/natbirzha/js/screens/overview.js tests/test_natbirzha_frontend.js`
  - `git commit -m "feat(natbirzha): show factory automation and long-term progress"`

## Task 5: Content-extension data contract and rollout checklist

**Files:**
- Modify: `backend/natbirzha/services/building_catalog/buildings_part1.py`
- Modify: `backend/natbirzha/services/building_catalog/buildings_part2.py`
- Modify: `backend/natbirzha/services/unit_catalog.py`
- Create: `docs/natbirzha/content-rollout.md`
- Test: `tests/natbirzha/test_progression_catalog.py`

- [ ] **Step 1: Write failing catalog validation tests.**
  - Assert every recipe has a valid level 1–60, inputs/outputs known to the inventory catalog and a reachable prerequisite chain.
  - Assert every new unit has a clear production source and no premium-only item is required before the late-game gate.

- [ ] **Step 2: Run RED.**
  - Run: `python tests/natbirzha/test_progression_catalog.py`

- [ ] **Step 3: Add the data-contract and rollout document.**
  - Add schema-neutral era metadata to catalog entries first, then write `content-rollout.md` with the approved sequence: 10–12 buildings per existing industry, four late-game industries, research, advanced army, achievements, mastery after level 60.
  - Do not invent and ship untested pricing/recipes in this foundation commit; each content wave must satisfy the new validator and economy tests.

- [ ] **Step 4: Verify and commit.**
  - Run: `python tests/natbirzha/test_progression_catalog.py`
  - `git add backend/natbirzha/services/building_catalog backend/natbirzha/services/unit_catalog.py docs/natbirzha/content-rollout.md tests/natbirzha/test_progression_catalog.py`
  - `git commit -m "docs(natbirzha): define validated progression content rollout"`

## Task 6: Final verification and release handoff

- [ ] **Step 1: Run all focused tests.**
  - `python tests/natbirzha/test_progression_service.py`
  - `python tests/natbirzha/test_factory_automation.py`
  - `python tests/natbirzha/test_progression_catalog.py`
  - `python tests/natbirzha/test_registration_production_cycle.py`
  - `node tests/test_natbirzha_frontend.js`

- [ ] **Step 2: Replay a real game sequence locally.**
  - Create a company, construct a factory, fund inputs, upgrade automation, enable it, advance the scheduled tick, and verify outputs/XP exactly once.
  - Test pause/resume with insufficient input and recheck no resource loss.

- [ ] **Step 3: Inspect release state.**
  - Run `git diff --check`, `git status --short`, and `git log --oneline origin/main..HEAD`.
  - Push only with repository credentials. A failed authentication must not be described as a deployed release.
