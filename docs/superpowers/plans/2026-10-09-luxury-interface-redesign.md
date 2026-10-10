# Premium Light Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give all NATBIRZHA screens a coherent mobile-first ivory, sage, emerald, and champagne visual system with locally drawn SVG icons, while preserving gameplay and fixing verified front-end defects.

**Architecture:** Add one small pure SVG icon module and a focused luxury theme stylesheet. Keep existing screen renderers and API contracts; migrate shared shell and screen markup incrementally, using semantic component classes and a compatibility layer for existing Tailwind color utilities. Audit behavior only where the UI is touched, then run the project and icon checks.

**Tech Stack:** HTML, CSS, browser ES modules, Node's built-in test runner, Python project test suite, Telegram Mini App SDK.

---

## File map

- Create `frontend/natbirzha/js/icons.mjs`: trusted icon-name-to-SVG registry and accessible `renderIcon` helper.
- Create `frontend/natbirzha/css/luxury-theme.css`: design tokens, shared surfaces, legacy utility color mapping, responsive/accessibility states.
- Modify `frontend/natbirzha/index.html`: load the new theme and replace static shell emojis with inline SVG references.
- Modify `frontend/natbirzha/js/localization.js`, `items.js`, `onboarding.js`, and `factory_map.js`: stable industry/resource/factory icon names, not emoji glyphs.
- Modify screen renderers and support views to use `renderIcon` for interface glyphs: `screens/catalog.js`, `overview.js`, `overview_capacity.js`, `production.js`, `upgrades.js`, `tycoon.js`, `tycoon_production_status.js`, `company_aid_panel.js`, `company_rebirth_panel.js`, `hybrids.js`, `help.js`, `market.js`, `market_section_loader.js`, `market_commodities.js`, `market_orderbook_view.js`, `market_finance.js`, `market_deals.js`, `market_credit.js`, `market_tax.js`, `market_city_orders.js`, `market_joint_factories.js`, `stocks.js`, `state_share_market.js`, `bankruptcy_market.js`, `military.js`, `military_helpers.js`, `military_hospital.js`, `military_tournament.js`, `leaderboard.js`, `creator.js`, `creator_overview.js`, `creator_credit.js`, `creator_moderation.js`, `creator_players.js`, `creator_sabotages.js`, and `creator_shares.js`.
- Create `tests/frontend-icons.test.mjs`: direct tests of the icon registry, safe-name fallback, and accessible markup.

## Task 1: Add and test the SVG icon contract

**Files:** create `frontend/natbirzha/js/icons.mjs`; create `tests/frontend-icons.test.mjs`.

- [ ] **Step 1: Write icon tests first.** Cover all registered names returning an SVG, unknown names falling back safely, labels being escaped, and decorative markup using `aria-hidden="true"`.
- [ ] **Step 2: Run the focused test and confirm it fails** because `icons.mjs` is not present.
- [ ] **Step 3: Implement a fixed icon registry.** Export `ICON_NAMES` and `renderIcon(name, { size = 20, className = '', label = '' } = {})`. Use this rendering shape, with `ICON_PATHS` containing only authored static SVG child markup:

```js
export function renderIcon(name, { size = 20, className = '', label = '' } = {}) {
  const path = ICON_PATHS[name] || ICON_PATHS.resource;
  const safeClass = escapeAttribute(className);
  const title = label ? `<title>${escapeText(label)}</title>` : '';
  const accessible = label ? `role="img" aria-label="${escapeAttribute(label)}"` : 'aria-hidden="true"';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${clampSize(size)}" height="${clampSize(size)}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" class="${safeClass}" ${accessible}>${title}${path}</svg>`;
}
```

The helper must not accept caller-provided path data or raw SVG strings.
- [ ] **Step 4: Run the focused test and confirm it passes.** Run `node --test tests/frontend-icons.test.mjs`.
- [ ] **Step 5: Check module syntax.** Run `node --check frontend/natbirzha/js/icons.mjs`.

## Task 2: Replace the princess theme with shared luxury tokens

**Files:** create `frontend/natbirzha/css/luxury-theme.css`; modify `frontend/natbirzha/index.html`; retire the `princess-theme.css` include.

- [ ] **Step 1: Define the base tokens and reset** in `luxury-theme.css` using this foundation:

```css
:root {
  color-scheme: light;
  --lux-canvas: #F7F7F1;
  --lux-surface: #FFFFFF;
  --lux-sage: #E4ECE2;
  --lux-emerald: #17664F;
  --lux-emerald-deep: #124B3C;
  --lux-champagne: #B69458;
  --lux-ink: #24332C;
  --lux-muted: #65736B;
  --lux-border: #DCE5DC;
  --lux-focus: #17664F;
}

html, body { min-height: 100%; background: var(--lux-canvas); color: var(--lux-ink); }
```

Add secondary tokens only when a specific component needs them.
- [ ] **Step 2: Add shared shell and component rules** for body, header, bottom navigation, cards, buttons, form controls, pills, loading/error/empty states, toast, visible focus, reduced motion, and Telegram safe-area padding.
- [ ] **Step 3: Map legacy Tailwind color classes** (pink, fuchsia, violet, indigo, blue, amber, slate) to the approved palette only at component surfaces. Keep semantic red for errors and green for positive values.
- [ ] **Step 4: Update `index.html`** to load the new stylesheet after `natbirzha.css`, preserve Tailwind ordering, use `lang="ru"`, set the body to the light luxury surface, and convert all six bottom-nav buttons plus the state button to local SVG icons with text labels and touch targets of at least 44 px.
- [ ] **Step 5: Add responsive rules** for 320 px screens, safe-area insets, horizontal tab overflow, and large-screen max-width; test reduced-motion CSS with `prefers-reduced-motion`.
- [ ] **Step 6: Confirm the shell keeps all existing IDs and `data-tab` values** so `app.js` navigation wiring remains unchanged.

## Task 3: Give industries, facilities, and resources stable icon identities

**Files:** modify `frontend/natbirzha/js/localization.js`, `items.js`, `onboarding.js`, `factory_map.js`; add icon coverage to `tests/frontend-icons.test.mjs`.

- [ ] **Step 1: Add explicit icon names** for the 12 industries, facility families, common resource families, and common actions. Keep localized display names and all item identifiers unchanged.
- [ ] **Step 2: Draw consistent SVGs** for overview, factories, upgrades, exchange, military, rankings, power, water, mining, agriculture, oil, metallurgy, construction, chemistry, technology, AI, logistics, brewing, money, stock, shield, warning, lock, and navigation arrows.
- [ ] **Step 3: Render icons beside existing labels** in onboarding choices, facility maps, resource summaries, and factory cards using this call pattern:

```js
renderIcon('power', { size: 20, className: 'ui-icon ui-icon--industry', label: 'Энергетика' })
```

Do not replace user-created company names or generated flavor text.
- [ ] **Step 4: Test icon coverage** so every known icon name resolves and each icon-only control supplies an accessible label.

## Task 4: Migrate screen families onto the shared visual system

**Files:** modify the screen files listed in the file map and the four existing frontend CSS files only when a rule is screen-specific.

- [ ] **Step 1: Migrate Overview, Factories, Upgrades, and Tycoon.** Replace interface emoji in company status, production cards, upgrade cards, catalog controls, aid/rebirth actions, and hybrid-factory cards with `renderIcon`; use common card/button/status classes.
- [ ] **Step 2: Migrate every Exchange sub-screen.** Apply the same surfaces and icon scale to commodities/orderbook, finance, deals, credit, tax, city orders, joint factories, stocks, state shares, and bankruptcy market. Preserve ticker/item IDs and all request payloads.
- [ ] **Step 3: Migrate Military and Rankings.** Update battle, hospital, tournament, PvE state, and leaderboard surfaces; keep numeric power, costs, and result semantics unchanged.
- [ ] **Step 4: Migrate Creator and Help screens.** Replace control glyphs on moderation, players, sabotage, shares, overview, credit, and help. Preserve admin-only visibility rules.
- [ ] **Step 5: Verify screen lifecycle behavior** after every group: navigation still loads the selected renderer; leaving a screen still disposes its listeners; loading/error/empty states remain visible and readable.
- [ ] **Step 6: Remove obsolete princess-only selectors** from `princess-theme.css` after checking every retained selector has a replacement in `luxury-theme.css`; delete the file only after `rg` confirms no active link or class depends on it.

## Task 5: Audit and repair verified frontend defects

**Files:** only the specific screen/helper files that fail the audit; add a regression test for each corrected behavior to the existing relevant test file or `tests/frontend-icons.test.mjs` when it concerns icon rendering.

- [ ] **Step 1: Inventory DOM event registration and cleanup** in each screen family. Confirm no renderer installs duplicate global listeners on repeated navigation and that registered cleanup callbacks are invoked.
- [ ] **Step 2: Trace every audited request path** through loading, success, empty response, HTTP failure, and screen-unmounted cases. Fix only reproduced cases; re-enable controls in `finally` blocks and prevent stale responses from overwriting a different selected screen.
- [ ] **Step 3: Scan HTML generation** for unescaped user-controlled names in touched templates; route interpolated values through existing `escapeHtml` helpers before rendering.
- [ ] **Step 4: Check layout and accessibility** at 320 px and 390 px widths: no page-level horizontal overflow, minimum touch targets, keyboard focus, input labels, and adequate text/status contrast.
- [ ] **Step 5: Record each found defect and its regression check** in the final report; do not make speculative gameplay or backend changes.

## Task 6: Final verification

**Files:** no additional changes unless a verification result exposes a concrete defect.

- [ ] **Step 1: Run syntax checks on every frontend JS module** with `Get-ChildItem frontend/natbirzha/js -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }` and separately check `icons.mjs`.
- [ ] **Step 2: Run icon tests** with `node --test tests/frontend-icons.test.mjs`.
- [ ] **Step 3: Run the required full project suite** with `python tests/test_suite.py`; fix regressions before finishing.
- [ ] **Step 4: Run `git diff --check`** and inspect the diff for accidental game-rule, API, or data changes.
- [ ] **Step 5: Verify static assets**: the new theme and icon module load from the existing static mount, and no external icon/font request was introduced.
- [ ] **Step 6: Commit the completed implementation** with a concise `feat:` or `fix:` message after all checks pass; deployment is a separate action unless requested.
