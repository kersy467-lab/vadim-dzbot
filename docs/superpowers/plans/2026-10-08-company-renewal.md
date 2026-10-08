# Company renewal implementation plan

**Goal:** Help small companies restart and give mature companies a new industrial progression.

**Architecture:** Company aid uses authenticated, audited transfers. Production bonuses are calculated once in the authoritative production engines and reflected in summaries. Rebirth resets the company in one transaction, retaining its identity and paid PVC upgrades; external financial obligations must be closed first.

**Tech stack:** FastAPI, SQLAlchemy async, PostgreSQL/SQLite, vanilla JavaScript.

- [x] Replace the automatic mastery cash grant with +1% actual output per mastery rank; inputs and upkeep remain unchanged. Verify settled quantities and summary agree.
- [x] Add rebirth count and last rebirth timestamp, repeatable +25% additive output bonus, maximum ten rebirths. Preserve industry PVC upgrades, wallet, premium licenses and premium ledger.
- [x] Build ten named endgame factories for every industry with explicit rebirth gates. Fix unreachable ordinary company level requirements. Each rebirth requires opening the final factory of the current progression.
- [x] Reset ordinary assets and progress atomically; reject outstanding loans, funded market orders, securities positions, IPO and jointly owned assets rather than deleting another player's claims.
- [x] Add voluntary cash/resource aid requests and audited transfers with receiver consent, reserved-stock protection and receiver limits.
- [x] Wire migrations, API endpoints and compact frontend panels; remove broken industry-change button.
- [x] Check progression, real production, aid accounting, reset safety and premium preservation; check frontend syntax and catalogue integrity.

No live company is reset by the migration. Rebirth requires an explicit player action and confirmation.

Verification: 66 affected backend tests passed, including foreign-key-enabled renewal, current tax settlement, advance/loan/shareholder protection, aid accounting and migration repeatability. JavaScript syntax, frontend shell contracts and git diff checks passed. Changes remain local; no live company was reset.
