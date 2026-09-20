# NATBIRZHA P2 Frontend Completion Plan

## Goal

Expose the completed P2 backend in the existing Mini App without adding another bottom-navigation item or reintroducing client-authoritative combat/economy logic.

## 1. API client contract

- Add client methods for PvE targets/scouting/attacks, battle history, tournament targets/PvP attacks, reference instruments/trades and secondary bond listings.
- Keep mutation idempotency in the shared request layer.
- Add static contract tests before screen changes.

## 2. Unified War screen

- Rename the navigation item and title from Defense to War.
- Use five internal sections: Army, PvE Borders, Tournament, History and Alliance.
- Show all six unit types, phase strength, readiness and recruitment requirements.
- Show target risk/reward/scouting, attack state, tournament time/rewards/targets/cooldowns and readable battle results.
- Disable each mutation button while its request is running and refresh only the affected War data.

## 3. Existing Market screen integration

- Keep resources/orderbook as the primary Market section.
- Add official USD/EUR/gold/silver cards with source time, stale state, position and buy/sell actions.
- Add state bonds and their secondary listings in the same screen.
- Do not accept or calculate authoritative quote values in the client.

## 4. Verification

- Expand the Node frontend contract test.
- Run JS syntax checks, frontend regression, focused HTTP tests and `git diff --check`.
- Update the master checklist only for verified P2 frontend items.
