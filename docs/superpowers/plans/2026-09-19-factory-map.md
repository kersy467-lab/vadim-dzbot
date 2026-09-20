# Карта территории и заводов Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with checkpoints. Steps use checkbox syntax for tracking.

**Goal:** Replace the text-heavy production screen with a mobile-safe 3×3 territory map that starts cycles, collects ready output, opens the catalog, and keeps existing server-authoritative production behavior.

**Architecture:** Keep `NatAPI` and production endpoints unchanged. Add a small pure frontend mapper for page/slot/biome and render the existing factory payload into a detached map view; mutation handlers call the current idempotent API methods and refresh only the affected factory/company state. Use CSS classes and existing emoji/icon conventions instead of introducing image assets or a rendering engine.

**Tech Stack:** ES modules, existing Natbirzha screen modules, Tailwind utility classes plus `natbirzha.css`, Node syntax/static tests, Python FastAPI regression suite.

---

### Task 1: Define map projection and regression expectations

**Files:**
- Create: `frontend/natbirzha/js/factory_map.js`
- Modify: `tests/test_natbirzha_frontend.js`

- [ ] **Step 1: Write failing tests for deterministic page projection**

Add assertions that the new module exposes `BIOMES`, `getFactoryPage`, `getFactorySlot`, `getBiomeForPage`, and `buildFactoryPages`, and that a list of factories is stable when its order is unchanged. Assert that page 1 uses the grass biome, page 2 the desert biome, and empty slots are represented without inventing factories.

- [ ] **Step 2: Run the focused frontend test and verify it fails**

Run:

```powershell
node tests/test_natbirzha_frontend.js
```

Expected result: FAIL because `factory_map.js` and its projection helpers do not exist yet.

- [ ] **Step 3: Implement the pure mapper**

Implement the following interface without API calls or DOM access:

```js
export const BIOMES = [
  { id: 'grass', title: 'Зелёная равнина', pageClass: 'factory-biome-grass' },
  { id: 'desert', title: 'Пустыня', pageClass: 'factory-biome-desert' },
  { id: 'snow', title: 'Снежные горы', pageClass: 'factory-biome-snow' },
];

export function getFactoryPage(index) { return Math.floor(index / 9) + 1; }
export function getFactorySlot(index) { return index % 9; }
export function getBiomeForPage(page) { return BIOMES[(page - 1) % BIOMES.length]; }
export function buildFactoryPages(factories, maxSlots) { /* stable 9-slot pages, no fake factories */ }
```

`buildFactoryPages` must preserve input order, use a factory’s explicit `map_page`/`map_slot` only when present, otherwise use the stable array index, and include page metadata plus `null` entries for empty slots. The page count is `Math.max(1, Math.ceil(Math.max(maxSlots || factories.length, factories.length) / 9))`.

- [ ] **Step 4: Run the focused test and verify it passes**

Run the same Node command. Expected result: all frontend assertions pass.

- [ ] **Step 5: Commit the projection unit**

```powershell
git add frontend/natbirzha/js/factory_map.js tests/test_natbirzha_frontend.js
git commit -m "feat(natbirzha): add factory map projection"
```

### Task 2: Add the map presentation styles

**Files:**
- Modify: `frontend/natbirzha/css/natbirzha.css`
- Modify: `tests/test_natbirzha_frontend.js`

- [ ] **Step 1: Add failing style-contract assertions**

Assert that the stylesheet contains `.factory-map`, `.factory-slot`, `.factory-biome-grass`, `.factory-biome-desert`, `.factory-biome-snow`, and a mobile-safe `grid-template-columns` rule.

- [ ] **Step 2: Run the frontend test and verify the new assertions fail**

Run `node tests/test_natbirzha_frontend.js`; expected failure is the missing style selectors.

- [ ] **Step 3: Implement the visual map styles**

Add compact CSS for a responsive 3-column map, 9 slots, terrain gradients, icon/status badges, progress bars, `Забрать` badge, disabled/blocked styling, and page arrows. Keep the map inside the screen’s existing `max-w-md` layout and use `min-width: 0`/`overflow: hidden` so 320px screens do not create horizontal page scroll.

- [ ] **Step 4: Run the frontend test and syntax checks**

Run:

```powershell
node tests/test_natbirzha_frontend.js
node --check frontend/natbirzha/js/factory_map.js
node --check frontend/natbirzha/js/screens/production.js
```

Expected result: all commands pass.

- [ ] **Step 5: Commit the style layer**

```powershell
git add frontend/natbirzha/css/natbirzha.css tests/test_natbirzha_frontend.js
git commit -m "feat(natbirzha): style responsive factory territory map"
```

### Task 3: Render production as a paged territory map

**Files:**
- Modify: `frontend/natbirzha/js/screens/production.js`
- Modify: `frontend/natbirzha/js/state.js` only if selected factory page must persist between renders
- Modify: `tests/test_natbirzha_frontend.js`

- [ ] **Step 1: Add failing renderer contract assertions**

Assert that the production screen imports the mapper, renders `factory-map`, `factory-slot`, `factory-next-page`, `factory-collect-btn`, and `factory-build-btn`, and uses `cycle_ready_at`/`remaining_seconds` rather than inventing cycle state.

- [ ] **Step 2: Run the frontend test and verify it fails**

Run `node tests/test_natbirzha_frontend.js`; expected failure is missing map markup/imports.

- [ ] **Step 3: Implement the map renderer**

Keep `NatAPI.getProductionStatus()` and the existing cached recipes request. Project the returned factories into pages using `buildFactoryPages`; derive `maxSlots` from `store.company.factory_slots.max` or the returned company data. Render one page at a time with:

- page title and biome name;
- nine slots in row-major order;
- empty slot with `＋` and `factory-build-btn`;
- factory icon, short name, level, efficiency and server `start_hint`;
- running state with countdown based on `remaining_seconds`/`cycle_ready_at`;
- ready state with `factory-collect-btn` and no duplicate start button;
- blocked state with the server message and the existing next-step link;
- page dots and previous/next controls, disabled when locked by available slots.

Do not alter production formulas or send a mutation for page navigation.

- [ ] **Step 4: Run the focused frontend checks**

Run `node tests/test_natbirzha_frontend.js` and the three `node --check` commands from Task 2. Expected result: PASS.

- [ ] **Step 5: Commit the map renderer**

```powershell
git add frontend/natbirzha/js/screens/production.js frontend/natbirzha/js/state.js tests/test_natbirzha_frontend.js
git commit -m "feat(natbirzha): render production as territory map"
```

### Task 4: Wire map interactions without full-screen resets

**Files:**
- Modify: `frontend/natbirzha/js/screens/production.js`
- Modify: `frontend/natbirzha/js/screens/catalog.js` only for the return callback contract
- Modify: `tests/test_natbirzha_frontend.js`

- [ ] **Step 1: Add failing interaction assertions**

Assert that production binds `NatAPI.triggerProduction`, `factory-collect-btn`, `openCatalogModal`, disables mutation buttons before awaiting, and calls a targeted factory refresh instead of blindly restarting the selected page.

- [ ] **Step 2: Verify the test fails**

Run `node tests/test_natbirzha_frontend.js`; expected failure is the missing collect/button contract.

- [ ] **Step 3: Implement the interaction handlers**

Use the existing idempotent `NatAPI.triggerProduction(factoryId, recipeId)` for both start and collect. The handler must disable the clicked button, show a short loading label, handle server errors with `showToast`, update `store` from `getMyCompany` when the response changes company data, then refresh only the factory card/page data. The catalog callback must close the modal and return to the same page index. Preserve the selected page and horizontal position; no `container.innerHTML` call may be made from a click handler for a single card.

- [ ] **Step 4: Run frontend tests and existing production API regression**

Run:

```powershell
node tests/test_natbirzha_frontend.js
$env:PYTHONPATH='.'; python tests/natbirzha/test_registration_production_cycle.py
```

Expected result: both pass.

- [ ] **Step 5: Commit interaction behavior**

```powershell
git add frontend/natbirzha/js/screens/production.js frontend/natbirzha/js/screens/catalog.js tests/test_natbirzha_frontend.js
git commit -m "feat(natbirzha): start and collect production from map"
```

### Task 5: Verify mobile layout and regression safety

**Files:**
- Modify: `tests/test_natbirzha_frontend.js` if a reusable viewport contract is needed
- Modify: `outputs/NATBIRZHA_MASTER_CHECKLIST.md`

- [ ] **Step 1: Run syntax and frontend tests**

```powershell
node tests/test_natbirzha_frontend.js
node --check frontend/natbirzha/js/factory_map.js
node --check frontend/natbirzha/js/screens/production.js
git diff --check
```

- [ ] **Step 2: Run backend regression**

```powershell
$env:PYTHONPATH='.'; python tests/test_suite.py
```

Expected result ends with `=== ALL 11 «Б» BOT TESTS PASSED SUCCESSFULLY! ZERO ERRORS! ===`.

- [ ] **Step 3: Exercise the local app at mobile widths**

With the local FastAPI instance on `http://127.0.0.1:8768`, check the production map at 320px, 360px and 390px. Confirm no horizontal page scroll, page arrows remain tappable, empty slots open the catalog, start/collect buttons disable during requests, and leaving the tab during a slow request does not mount stale production DOM.

- [ ] **Step 4: Update the checklist with evidence**

Mark only the factory-map items proven by the commands/manual checks; leave Telegram Android/iOS, production PostgreSQL, reset backup and release-repository items unchecked until those external environments are available.

- [ ] **Step 5: Commit verification notes**

```powershell
git add outputs/NATBIRZHA_MASTER_CHECKLIST.md
git commit -m "test(natbirzha): verify factory map regression"
```

## Self-review

- The plan covers the approved 3×3 layout, biomes, empty slots, start/collect actions, server hints, mobile behavior, and regression requirements from the design spec.
- No backend economic rules or stock-market UI are included; the user’s stock-market drawing remains a separate design task.
- No unresolved TODO/TBD placeholders are used. Every implementation step names a file, test command, expected result, and commit boundary.
