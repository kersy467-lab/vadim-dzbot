# Economy, Warehouse Runway, and UI Repair Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make early oil-to-diesel trade playable, show how long unreserved stock sustains running and supply-paused V2 resource businesses in the eighth factory summary card, fix item icon colors and State panel readability, and keep optional startup checks off the initial-render critical path.

**Architecture:** Keep economy rules in the server catalog and calculate resource runway from the same per-business production rates used by idle settlement. Add runway data to the existing empire-summary response and render it in the Tycoon tab's metric grid so the new card adds no request. Keep icon artwork semantic in the existing SVG icon registry and scope State panel styles to its own root.

**Tech Stack:** Python, FastAPI, SQLAlchemy, pytest, browser ES modules, SVG, CSS.

---

### Task 1: Early oil processing and diesel availability

**Files:**
- Modify: `backend/natbirzha/catalogs/businesses/oilgas.py`
- Modify: `scripts/natbirzha_economy_audit.py`
- Test: `tests/natbirzha/test_oilgas_early_diesel.py`

- [x] Add failing assertions that the starting oil well does not consume diesel, and that an oil-to-diesel processor using crude is available by company level 4 and appears before the level-16 refinery.
- [x] Run `pytest tests/natbirzha/test_oilgas_early_diesel.py -q`; confirm it fails on the missing catalog behavior.
- [x] Add a small refinery as an order-2 level-4 oil business with crude input and diesel output; preserve the existing later gas and refinery progression and keep the starter well free of diesel input.
- [x] Extend the economy audit to report earliest ordinary diesel production and crude consumers, so future balance review measures unlock timing rather than only theoretical ROI.
- [x] Run the focused economy tests. The targeted oil/rebirth/runway tests pass; the broader legacy economy contracts still report five unrelated issues (logistics static sink assumptions, hybrid stage-2 payback, and stale catalog counts).

### Task 2: Warehouse resource runway on the company overview

**Files:**
- Modify: `backend/natbirzha/services/empire_summary_service.py`
- Modify or create: `backend/natbirzha/services/business_inventory_runway.py`
- Modify: `frontend/natbirzha/js/screens/tycoon.js`
- Modify: `backend/natbirzha/api/business_routes.py` only if serialization requires a route adjustment
- Test: `tests/natbirzha/test_business_inventory_runway.py`
- Test: `tests/natbirzha/test_inventory_runway_overview.js`

- [x] Add failing API tests for multiple businesses sharing an input, reserved stock, no consuming businesses, a zero-stock blocker, and supply-paused businesses.
- [x] Run the focused pytest file and confirm the runway summary is missing.
- [x] Sum hourly consumption for ACTIVE, UPGRADING, and PAUSED_SUPPLY resource businesses using canonical input rates and available, unreserved inventory; report the minimum remaining hours and limiting resource(s).
- [x] Include the summary in the existing empire-summary response and render it as an eighth Tycoon metric card without making a new network request.
- [x] Run focused service and frontend contract tests.

### Task 3: Semantic resource artwork and State panel contrast

**Files:**
- Modify: `frontend/natbirzha/js/resource_icons.mjs`
- Modify: `frontend/natbirzha/js/screens/creator.js`
- Modify: `frontend/natbirzha/css/luxury-theme.css`
- Test: `tests/natbirzha/test_item_icon_names.mjs`
- Test: `tests/natbirzha/test_creator_theme_contrast.js`

- [x] Add failing icon assertions for water, energy, diesel, crude oil, and beer semantic colors and recognizable SVG artwork.
- [x] Add failing State panel assertions for a scoped light surface, readable dark text, visible borders, and high-contrast action buttons.
- [x] Replace hash-assigned item palettes with semantic palettes and draw distinct SVG motifs for the named resources while retaining the established icon component API.
- [x] Add a State panel root class and scope card, tab, body, and button colors so the global luxury theme cannot wash out text or controls.
- [x] Run the focused Node tests and icon/localization tests; updated cache keys so the browser fetches changed icon and creator assets.

### Task 4: Targeted screen-load optimization

**Files:**
- Modify: `frontend/natbirzha/js/app.js`, `frontend/natbirzha/js/bankruptcy_gate.js`
- Test: existing frontend loading contract tests and the directly affected screen contract

- [x] Move the noncritical bankruptcy status request off the first-screen rendering path, keeping the check and timer nonblocking.
- [x] Prevent overlapping bankruptcy status requests and ignore a response if the active company changed while it was in flight.
- [x] Add a focused loading-contract assertion and run loading, overlay, and Tycoon screen contracts.

### Task 5: Integration, review, and deployment

**Files:** all files changed by Tasks 1–4.

- [x] Review the combined diff for catalog unlock consistency, accurate shared-stock math, semantic icon mapping, cache busting, and State panel contrast.
- [x] Run focused Python and Node tests, syntax checks, loading contracts, icon/contrast contracts, and the broader economy checks. Targeted tests pass; broader checks have the unrelated legacy failures noted under Task 1.
- [x] Commit the implementation with a descriptive message: `7b04d2b` (`fix: balance early oil and improve factory overview`).
- [x] Push `main` and `dev` to `origin`, `vadim`, and `mybot` using the repository's required safe-directory and noninteractive Git settings.
