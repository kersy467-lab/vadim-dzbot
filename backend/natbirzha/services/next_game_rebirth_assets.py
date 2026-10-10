"""Transfer financial ownership to the reserve instead of erasing investor rights."""
from sqlalchemy import select
from backend.natbirzha.models.next_game import NatNextGameCompany
from backend.natbirzha.models.next_game_equity import NatNextGameShareHolding, NatNextGameShareIssue
from backend.natbirzha.models.next_game_finance import NatNextGameFinanceContract
from backend.natbirzha.models.next_game_banking import NatNextGameCorporateLoan, NatNextGameBankAccount

RESERVE_OWNER_TG_ID = -1


async def reserve_company(session):
    company = await session.scalar(select(NatNextGameCompany).where(
        NatNextGameCompany.owner_tg_id == RESERVE_OWNER_TG_ID,
    ).with_for_update())
    if company is None:
        company = NatNextGameCompany(owner_tg_id=RESERVE_OWNER_TG_ID,
            name="Резервный банк 2.0", sector_id="bank", branch_path=[], cash=0, level=1, xp=0)
        session.add(company)
        await session.flush()
    return company


async def sweep_reserve_income(session):
    from backend.natbirzha.services.next_game_service import NextGameService
    await NextGameService._lock_treasury_for_sqlite(session)
    reserve = await session.scalar(select(NatNextGameCompany).where(
        NatNextGameCompany.owner_tg_id == RESERVE_OWNER_TG_ID,
    ).with_for_update())
    if reserve is None or reserve.cash <= 0:
        return 0.0
    treasury = await NextGameService._treasury(session)
    amount = float(reserve.cash)
    reserve.cash = 0
    treasury.cash = round(treasury.cash + amount, 8)
    session.add(NextGameService._ledger(reserve.id, "RESERVE_INCOME_SWEEP", -amount, amount))
    await session.flush()
    return amount


async def transfer_financial_assets(session, company, current):
    from backend.natbirzha.services.next_game_service import NextGameService
    reserve = await reserve_company(session)
    counts = {"share_holdings": 0, "finance_claims": 0, "bank_claims": 0}
    own_issue = await session.scalar(select(NatNextGameShareIssue).where(
        NatNextGameShareIssue.company_id == company.id,
    ).with_for_update())
    holdings = (await session.scalars(select(NatNextGameShareHolding).where(
        NatNextGameShareHolding.company_id == company.id,
    ).with_for_update())).all()
    for holding in holdings:
        if own_issue and holding.issue_id == own_issue.id:
            continue
        target = await session.scalar(select(NatNextGameShareHolding).where(
            NatNextGameShareHolding.company_id == reserve.id,
            NatNextGameShareHolding.issue_id == holding.issue_id,
        ).with_for_update())
        if target:
            total = target.shares + holding.shares
            target.average_price = ((target.shares * target.average_price + holding.shares * holding.average_price)
                                    / total) if total else 0
            target.shares = total
            await session.delete(holding)
        else:
            holding.company_id = reserve.id
        counts["share_holdings"] += 1
    contracts = (await session.scalars(select(NatNextGameFinanceContract).where(
        NatNextGameFinanceContract.lender_company_id == company.id,
        NatNextGameFinanceContract.status == "ACTIVE",
    ).with_for_update())).all()
    for contract in contracts:
        contract.lender_company_id = reserve.id
        contract.offer_key = f"reserve-transfer-{contract.id}"
        counts["finance_claims"] += 1
    loans = (await session.scalars(select(NatNextGameCorporateLoan).where(
        NatNextGameCorporateLoan.bank_company_id == company.id,
        NatNextGameCorporateLoan.status == "ACTIVE",
    ).with_for_update())).all()
    for loan in loans:
        loan.bank_company_id = reserve.id
        loan.idempotency_key = f"reserve-transfer-{loan.id}"
        counts["bank_claims"] += 1
    accounts = (await session.scalars(select(NatNextGameBankAccount).where(
        ((NatNextGameBankAccount.bank_company_id == company.id) |
         (NatNextGameBankAccount.customer_company_id == company.id)),
        NatNextGameBankAccount.status == "ACTIVE",
    ).with_for_update())).all()
    for account in accounts:
        account.status, account.closed_at = "CLOSED", current
    if own_issue:
        # Identity, quantities, other holders and dividend audit remain intact.
        own_issue.last_price = float(own_issue.last_price) * .01
    session.add(NextGameService._ledger(company.id, "REBIRTH_ASSET_TRANSFER", 0, 0,
        metadata={"reserve_company_id": reserve.id, **counts,
                  "own_issue_preserved": own_issue.id if own_issue else None}))
    await session.flush()
    return counts
