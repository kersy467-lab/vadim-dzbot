# НАТБИРЖА — balance/release verification · 2026-09-20

## What changed

The long-term progression now uses interacting loops instead of adding an unlimited number of factories. Levels remain capped at 60; mastery continues after 60 through industry, logistics, doctrine and intelligence. Every branch has diminishing returns and a hard asymptotic effect cap.

Midgame capital now has three real paths: self-funding, debt, or IPO. Debt opens at level 14, is capped at 35% of net NAV, carries daily interest and a 14-day term, and cannot recursively expand its own credit limit through borrowed cash.

PvE keeps the existing combined-arms requirements, cooldowns and repeat-frontier scaling. The first occupation can add territory; repeats do not. Cash from a successful PvE battle is now at most 65% of the cash portion of replacing the actual casualties and never exceeds the configured target cap. Territory, resources, XP, access and rating remain the main reward vectors.

Economy events now measure major currency/resource flows so creator balancing can use live source/sink data. Construction, upgrades, recruitment, territory, NPC trading, production, PvE and debt are included. Creator self-grants are audited and self-only.

The Mini App has a non-gray base theme even if the princess theme is stale or fails to load, and CSS/JS asset URLs are cache-busted.

## Verification performed

Passed locally:

- `git diff --check`
- `python -m compileall -q backend/natbirzha`
- `python -m py_compile` for changed Python modules
- `node --check` for all `frontend/natbirzha/js/*.js`
- `node tests/test_natbirzha_frontend.js` — all 5 sections pass
- Source-size rule for all changed/new Python/JS/HTML/CSS files: no changed source file exceeds 400 lines after splitting production and PvE campaign logic.

Blocked by the execution environment:

- `python tests/test_suite.py` stops before executing tests with `ModuleNotFoundError: No module named 'aiosqlite'`.
- New DB-backed tests fail at the same engine import. `requirements.txt` already requires `aiosqlite>=0.20.0`; no cached package is present in this container.

## Production gate

Before deployment, install project requirements and run `python tests/test_suite.py` until it reaches the repository's required zero-error success marker. Then smoke-test creation, one manual production cycle, one automated production cycle, NPC buy/sell, one PvE scout/attack, mastery unlock at level 60+, loan borrow/repay, creator metrics and both light/dark UI themes.
