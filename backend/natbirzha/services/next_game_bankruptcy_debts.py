"""Close obligations with a loss record; writeoffs never pay a creditor."""
from sqlalchemy import select
from backend.natbirzha.models.next_game import NatNextGameDeposit, NatNextGameLoan, NatNextGameMarketOrder
from backend.natbirzha.models.next_game_advance import NatNextGameMarketAdvance
from backend.natbirzha.models.next_game_banking import NatNextGameCorporateLoan
from backend.natbirzha.models.next_game_finance import NatNextGameFinanceContract
from backend.natbirzha.models.next_game_civic import NatNextGameTaxAssessment
from backend.natbirzha.models.next_game_bankruptcy import NatNextGameDebtWriteoff
from backend.natbirzha.services.next_game_service import NextGameService as Game
from backend.natbirzha.services.next_game_civic_accounting import assess_company


async def writeoff(session, company_id, kind, obligation_id, amount, current, creditor_company_id=None):
    session.add(NatNextGameDebtWriteoff(company_id=company_id, creditor_company_id=creditor_company_id,
        kind=kind, obligation_id=obligation_id, amount=amount, created_at=current))
    session.add(Game._ledger(company_id, "BANKRUPTCY_WRITEOFF", 0, 0,
        metadata={"kind": kind, "obligation_id": obligation_id, "amount": amount,
                  "creditor_company_id": creditor_company_id}))


async def writeoff_status(session, kind, obligation_id):
    row = await session.scalar(select(NatNextGameDebtWriteoff.id).where(
        NatNextGameDebtWriteoff.kind == kind, NatNextGameDebtWriteoff.obligation_id == obligation_id))
    return "WRITTEN_OFF" if row else None


async def forgive_taxes(session, company, current):
    account = await assess_company(session, company, current, include_open=True)
    for tax in (await session.scalars(select(NatNextGameTaxAssessment).where(
        NatNextGameTaxAssessment.company_id == company.id, NatNextGameTaxAssessment.status == "DUE").with_for_update())).all():
        await writeoff(session, company.id, "TAX", tax.id, tax.amount, current)
        tax.status = "FORGIVEN"
    account.epoch_at = account.assessed_until = current
    account.loss_carry = 0
    await session.flush()


async def close_debts(session, company, current):
    for model, borrower_field, kind, creditor_field in (
        (NatNextGameLoan, NatNextGameLoan.company_id, "BANK_LOAN", None),
        (NatNextGameCorporateLoan, NatNextGameCorporateLoan.borrower_company_id, "CORPORATE_LOAN", "bank_company_id"),
        (NatNextGameFinanceContract, NatNextGameFinanceContract.borrower_company_id, "DIRECT_LOAN", "lender_company_id"),
    ):
        for row in (await session.scalars(select(model).where(borrower_field == company.id,
            model.status == "ACTIVE").with_for_update())).all():
            if kind == "BANK_LOAN":
                amount = Game._loan_snapshot(row, current)["repayment_amount"]
            else:
                issued_at = row.issued_at if kind == "CORPORATE_LOAN" else row.accepted_at
                days = min(row.term_days, max(1, int((current - issued_at).total_seconds() // 86400)))
                rate = row.daily_rate if kind == "CORPORATE_LOAN" else row.daily_rate_bps / 10000
                amount = round(row.principal * (1 + rate * days), 2)
            await writeoff(session, company.id, kind, row.id, amount, current,
                getattr(row, creditor_field) if creditor_field else None)
            row.status, row.repaid_at = "PAID", current
            if hasattr(row, "repaid_amount"):
                row.repaid_amount = 0
    # Deposits already sit in the reserve; extinguish the claim without moving cash.
    for row in (await session.scalars(select(NatNextGameDeposit).where(
        NatNextGameDeposit.company_id == company.id, NatNextGameDeposit.status == "ACTIVE").with_for_update())).all():
        row.status, row.withdrawn_at = "WITHDRAWN", current
        session.add(Game._ledger(company.id, "BANKRUPTCY_DEPOSIT_FORFEIT", 0, 0,
            metadata={"deposit_id": row.id, "principal": row.principal, "interest_forfeited": row.maturity_amount - row.principal}))
    await session.flush()


async def confiscate_orders(session, company, current):
    treasury = await Game._treasury(session)
    stock = dict(treasury.inventory_json or {})
    for order in (await session.scalars(select(NatNextGameMarketOrder).where(
        NatNextGameMarketOrder.company_id == company.id, NatNextGameMarketOrder.status == "OPEN").with_for_update())).all():
        if order.side == "BUY":
            amount = order.reserved_cash
            treasury.cash = round(treasury.cash + amount, 8)
            session.add(Game._ledger(company.id, "BANKRUPTCY_ORDER_CASH", -amount, amount,
                metadata={"order_id": order.id, "from_reserved_cash": True}))
            order.reserved_cash = 0
        else:
            quantity = order.remaining_quantity
            stock[order.item_id] = round(float(stock.get(order.item_id, 0)) + quantity, 4)
            session.add(Game._ledger(company.id, "BANKRUPTCY_COLLATERAL", 0, 0, item_id=order.item_id,
                company_quantity=-quantity, treasury_quantity=quantity, metadata={"order_id": order.id}))
            funding = await session.get(NatNextGameMarketAdvance, order.id, with_for_update=True)
            if funding and funding.outstanding_amount > 0:
                await writeoff(session, company.id, "MARKET_ADVANCE", order.id, funding.outstanding_amount, current)
                funding.outstanding_amount = 0
        order.status, order.updated_at = "CANCELLED", current
    treasury.inventory_json = stock
    # Any historical closed order with a residual advance also loses its debt claim.
    await session.flush()
    for funding in (await session.scalars(select(NatNextGameMarketAdvance).where(
        NatNextGameMarketAdvance.company_id == company.id, NatNextGameMarketAdvance.outstanding_amount > 0
    ).with_for_update())).all():
        await writeoff(session, company.id, "MARKET_ADVANCE", funding.order_id, funding.outstanding_amount, current)
        funding.outstanding_amount = 0
    await session.flush()
