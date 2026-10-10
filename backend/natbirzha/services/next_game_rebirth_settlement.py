"""Close escrow, redeem deposits and repay obligations before any rebirth reset."""
from sqlalchemy import select
from backend.natbirzha.models.next_game import (
    NatNextGameCompany, NatNextGameMarketOrder, NatNextGameDeposit, NatNextGameLoan,
)
from backend.natbirzha.models.next_game_equity import NatNextGameShareIssue, NatNextGameShareOrder
from backend.natbirzha.models.next_game_finance import NatNextGameFinanceContract
from backend.natbirzha.models.next_game_banking import NatNextGameCorporateLoan
from backend.natbirzha.models.next_game_advance import NatNextGameMarketAdvance
from backend.natbirzha.models.next_game_partnerships import NatNextGameJointProject, NatNextGameSupplyDeal


async def blockers(session, company_id):
    active = await session.scalar(select(NatNextGameJointProject.id).where(
        ((NatNextGameJointProject.proposer_company_id == company_id) |
         (NatNextGameJointProject.partner_company_id == company_id)),
        NatNextGameJointProject.status == "ACTIVE",
    ))
    return ["Сначала согласуйте закрытие совместного предприятия с партнёром"] if active else []


async def close_partnership_offers(session, company, current):
    from backend.natbirzha.services.next_game_partnership_service import NextGamePartnershipService
    supplies = (await session.scalars(select(NatNextGameSupplyDeal).where(
        ((NatNextGameSupplyDeal.buyer_company_id == company.id) |
         (NatNextGameSupplyDeal.seller_company_id == company.id)),
        NatNextGameSupplyDeal.status.in_(["OPEN", "ACTIVE"]),
    ).with_for_update())).all()
    projects = (await session.scalars(select(NatNextGameJointProject).where(
        ((NatNextGameJointProject.proposer_company_id == company.id) |
         (NatNextGameJointProject.partner_company_id == company.id)),
        NatNextGameJointProject.status == "OPEN",
    ).with_for_update())).all()
    for row in supplies:
        await NextGamePartnershipService.cancel(session, company.owner_tg_id, "supply", row.id)
    for row in projects:
        await NextGamePartnershipService.cancel(session, company.owner_tg_id, "projects", row.id)


async def close_orders_and_offers(session, company, current):
    from backend.natbirzha.services.next_game_service import NextGameService
    from backend.natbirzha.services.next_game_market_service import NextGameMarketService
    from backend.natbirzha.services.next_game_equity_service import NextGameEquityService
    from backend.natbirzha.services.next_game_finance_service import NextGameFinanceContractService
    orders = (await session.scalars(select(NatNextGameMarketOrder).where(
        NatNextGameMarketOrder.company_id == company.id, NatNextGameMarketOrder.status == "OPEN",
    ).with_for_update())).all()
    # Return BUY reservations first, making existing company money available for debt.
    for order in orders:
        if order.side == "BUY":
            await NextGameMarketService.cancel_order(session, company.owner_tg_id, order.id)
    offers = (await session.scalars(select(NatNextGameFinanceContract).where(
        ((NatNextGameFinanceContract.lender_company_id == company.id) |
         (NatNextGameFinanceContract.borrower_company_id == company.id)),
        NatNextGameFinanceContract.status == "OPEN",
    ).with_for_update())).all()
    for offer in offers:
        lender = await session.get(NatNextGameCompany, offer.lender_company_id)
        await NextGameFinanceContractService.cancel_offer(session, lender.owner_tg_id, offer.id,
            idempotency_key=f"rebirth-cancel-{offer.id}")
    own_issue = await session.scalar(select(NatNextGameShareIssue).where(
        NatNextGameShareIssue.company_id == company.id,
    ))
    query = select(NatNextGameShareOrder).where(NatNextGameShareOrder.status == "OPEN")
    query = query.where((NatNextGameShareOrder.company_id == company.id) |
                        (NatNextGameShareOrder.issue_id == own_issue.id)) if own_issue else query.where(
                            NatNextGameShareOrder.company_id == company.id)
    share_orders = (await session.scalars(query.with_for_update())).all()
    for order in share_orders:
        owner = await session.get(NatNextGameCompany, order.company_id)
        await NextGameEquityService.cancel_order(session, owner.owner_tg_id, order.id)
    return [row for row in orders if row.side == "SELL"]


async def redeem_deposits(session, company, current):
    from backend.natbirzha.services.next_game_service import NextGameService
    treasury = await NextGameService._treasury(session)
    deposits = (await session.scalars(select(NatNextGameDeposit).where(
        NatNextGameDeposit.company_id == company.id, NatNextGameDeposit.status == "ACTIVE",
    ).with_for_update())).all()
    for deposit in deposits:
        payout = deposit.maturity_amount if current >= deposit.matures_at else deposit.principal
        if treasury.cash + 1e-8 < payout:
            raise ValueError("Казна пока не может вернуть вклад; перерождение сохранит все активы")
        company.cash = round(company.cash + payout, 8)
        treasury.cash = round(treasury.cash - payout, 8)
        deposit.status, deposit.withdrawn_at = "WITHDRAWN", current
        session.add(NextGameService._ledger(company.id, "REBIRTH_DEPOSIT_REDEEM", payout, -payout,
            metadata={"deposit_id": deposit.id, "early": current < deposit.matures_at}))
    await session.flush()


async def repay_obligations(session, company, sell_orders, current):
    from backend.natbirzha.services.next_game_service import NextGameService
    from backend.natbirzha.services.next_game_market_service import NextGameMarketService
    from backend.natbirzha.services.next_game_advance_service import NextGameAdvanceService
    from backend.natbirzha.services.next_game_finance_service import NextGameFinanceContractService
    from backend.natbirzha.services.next_game_banking_service import NextGameBankingService
    loans = (await session.scalars(select(NatNextGameLoan).where(
        NatNextGameLoan.company_id == company.id, NatNextGameLoan.status == "ACTIVE",
    ).with_for_update())).all()
    for loan in loans:
        await NextGameService.repay_bank_loan(session, company.owner_tg_id, now=current)
    direct = (await session.scalars(select(NatNextGameFinanceContract).where(
        NatNextGameFinanceContract.borrower_company_id == company.id,
        NatNextGameFinanceContract.status == "ACTIVE",
    ).with_for_update())).all()
    for contract in direct:
        await NextGameFinanceContractService.repay_loan(session, company.owner_tg_id, contract.id,
            idempotency_key=f"rebirth-repay-{contract.id}", now=current)
    corporate = (await session.scalars(select(NatNextGameCorporateLoan).where(
        NatNextGameCorporateLoan.borrower_company_id == company.id,
        NatNextGameCorporateLoan.status == "ACTIVE",
    ).with_for_update())).all()
    for loan in corporate:
        await NextGameBankingService.repay_business_loan(session, company.owner_tg_id, loan.id,
            idempotency_key=f"rebirth-repay-{loan.id}", now=current)
    for order in sell_orders:
        funding = await session.get(NatNextGameMarketAdvance, order.id)
        if funding and funding.outstanding_amount > 1e-8:
            if company.cash + 1e-8 < funding.outstanding_amount:
                raise ValueError("Для перерождения сначала погасите аванс обеспеченного ордера")
            paid = await NextGameAdvanceService.repay_fill(session, order, funding.outstanding_amount)
            company.cash = round(company.cash - paid, 8)
        await NextGameMarketService.cancel_order(session, company.owner_tg_id, order.id)
    await session.flush()


async def repayment_quote(session, company, current):
    """Estimate existing cash available to close this run without a subsidy."""
    from backend.natbirzha.services.next_game_service import NextGameService
    required = 0.0
    loans = (await session.scalars(select(NatNextGameLoan).where(
        NatNextGameLoan.company_id == company.id, NatNextGameLoan.status == "ACTIVE"))).all()
    required += sum(NextGameService._loan_snapshot(row, current)["repayment_amount"] for row in loans)
    direct = (await session.scalars(select(NatNextGameFinanceContract).where(
        NatNextGameFinanceContract.borrower_company_id == company.id,
        NatNextGameFinanceContract.status == "ACTIVE"))).all()
    for row in direct:
        days = min(row.term_days, max(1, int((current - row.accepted_at).total_seconds() // 86400)))
        required += round(row.principal * (1 + row.daily_rate_bps / 10000 * days), 2)
    corporate = (await session.scalars(select(NatNextGameCorporateLoan).where(
        NatNextGameCorporateLoan.borrower_company_id == company.id,
        NatNextGameCorporateLoan.status == "ACTIVE"))).all()
    for row in corporate:
        days = min(row.term_days, max(1, int((current - row.issued_at).total_seconds() // 86400)))
        required += round(row.principal * (1 + row.daily_rate * days), 2)
    advances = (await session.scalars(select(NatNextGameMarketAdvance).where(
        NatNextGameMarketAdvance.company_id == company.id))).all()
    required += sum(row.outstanding_amount for row in advances)
    available = float(company.cash)
    deposits = (await session.scalars(select(NatNextGameDeposit).where(
        NatNextGameDeposit.company_id == company.id, NatNextGameDeposit.status == "ACTIVE"))).all()
    available += sum(row.maturity_amount if current >= row.matures_at else row.principal for row in deposits)
    orders = (await session.scalars(select(NatNextGameMarketOrder).where(
        NatNextGameMarketOrder.company_id == company.id, NatNextGameMarketOrder.status == "OPEN"))).all()
    available += sum(row.reserved_cash for row in orders if row.side == "BUY")
    shares = (await session.scalars(select(NatNextGameShareOrder).where(
        NatNextGameShareOrder.company_id == company.id, NatNextGameShareOrder.status == "OPEN"))).all()
    available += sum(row.reserved_cash for row in shares if row.side == "BUY")
    offers = (await session.scalars(select(NatNextGameFinanceContract).where(
        NatNextGameFinanceContract.lender_company_id == company.id,
        NatNextGameFinanceContract.status == "OPEN"))).all()
    available += sum(row.principal for row in offers)
    supplies = (await session.scalars(select(NatNextGameSupplyDeal).where(
        NatNextGameSupplyDeal.buyer_company_id == company.id,
        NatNextGameSupplyDeal.status.in_(["OPEN", "ACTIVE"])))).all()
    available += sum(row.escrow_cash for row in supplies)
    projects = (await session.scalars(select(NatNextGameJointProject).where(
        NatNextGameJointProject.proposer_company_id == company.id,
        NatNextGameJointProject.status == "OPEN"))).all()
    available += sum(row.escrow_cash for row in projects)
    return {"required_repayment": round(required, 2), "cash_after_redemptions": round(available, 2),
            "shortfall": round(max(0, required - available), 2)}
