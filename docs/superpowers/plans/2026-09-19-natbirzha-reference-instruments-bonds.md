# NATBIRZHA Reference Instruments and Bond Settlement Plan

> Backend phase P2.7. Execute test-first and keep every money movement atomic and idempotent.

## Goal

Add official-reference trading for USD, EUR, gold and silver, plus complete state-bond lifecycle and player-to-player bond resale. The backend must remain usable during short upstream outages without silently serving indefinitely stale prices.

## 1. Reference-rate snapshots

- Add normalized snapshot, position and trade-ledger models.
- Parse the Bank of Russia daily currency XML and precious-metals XML without depending on locale settings.
- Store immutable snapshots for `USD`, `EUR`, `GOLD` and `SILVER`; normalize currencies to RUB per unit and metals to RUB per gram.
- Accept a cached snapshot for at most 72 hours (weekends included). Suspend new reference-instrument trades if it is older; portfolio reading remains available.
- Add deterministic parser/cache tests before implementation.

## 2. Instrument trading

- Add atomic buy/sell operations with row locks, a 1% server spread, cash and position validation, immutable trade rows and an operation key.
- Expose catalog/rates, portfolio and trade endpoints under `/api/natbirzha/instruments`.
- Ensure request idempotency and add API coverage for replay, insufficient cash/holdings and stale rates.

## 3. Bond lifecycle

- Extend bond issues with explicit issue, coupon schedule, maturity and lifecycle state.
- Add an immutable settlement ledger with unique keys per issue, holder, coupon period and maturity.
- Settle due coupons and principal from the state treasury exactly once. Insufficient treasury cash leaves the settlement pending and never creates money.
- Add deterministic tests for multiple coupon periods, retries, maturity and treasury shortage.

## 4. Secondary bond market

- Add sell listings that reserve the seller's bonds and can be cancelled or bought atomically.
- Transfer buyer cash directly to the seller and bonds directly to the buyer; the state treasury is not involved.
- Prevent overselling, self-purchase and double execution. Add listing/history API and idempotency tests.

## 5. Scheduling, migrations and verification

- Run reference refresh and due-bond settlement as restart-safe scheduler jobs.
- Add repeatable live-database migrations for new columns and defaults.
- Update the P2 backend contract and master checklist.
- Run focused tests, the full Python suite, the frontend Node regression test and `git diff --check`.

Official upstream contracts:

- Currency rates: `https://www.cbr.ru/scripts/XML_daily.asp`
- Precious metals: `https://www.cbr.ru/scripts/xml_metall.asp`
- XML interface documentation: `https://www.cbr.ru/development/sxml/`
