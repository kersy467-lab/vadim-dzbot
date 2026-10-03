# Faster tab loading and clearer PvE force display

## Goal
Reduce avoidable waiting when opening slow screens without serving stale balances or inventory, and make PvE strength labels accurately distinguish enemy estimates from player entry requirements.

## Scope
1. In the war screen, fetch only data needed for the selected section; lazy-load PvE, tournament, history, hospital, and PVC data when their sections are opened. Keep army data for army operations and refresh only relevant data after actions.
2. Replace PvE duplicate victory reads and per-target win-count queries with a joined victory query and one grouped count query.
3. Add small business read models so the upgrade screen no longer loads inventory, supply policies, assets, and full empire metrics, and the market's "needed by factories" filter no longer fetches the full empire summary. Retain normal economy settlement on the upgrade screen.
4. Collapse leaderboard aggregates into one SQL query plus the existing joint-factory stock query, without changing valuation formulas.
5. Label PvE force as an estimated enemy garrison and explicitly state the actual gates; show a useful loading shell immediately for the leaderboard.

## Verification
Review changed diffs and run focused syntax/static checks for edited JavaScript/Python files. Do not run the full test suite unless requested. No commit or deploy in this task.
