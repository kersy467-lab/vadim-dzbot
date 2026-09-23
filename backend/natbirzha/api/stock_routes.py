from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.db.session import get_db_session
from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.stocks import NatStock, NatStockHolding
from backend.natbirzha.services.auth_service import get_current_company
from backend.natbirzha.services.stock_service import StockService
from backend.natbirzha.services.stock_orderbook_service import StockOrderbookService
from backend.natbirzha.services.dividend_service import DividendService
from backend.natbirzha.services.idempotency_service import IdempotencyService

router = APIRouter(prefix="/stocks", tags=["Natbirzha Stocks"])

class BuyStockRequest(BaseModel):
    stock_id: int
    shares_count: int = Field(gt=0)

class SellStockRequest(BaseModel):
    stock_id: int
    shares_count: int = Field(gt=0)


class StockLimitOrderRequest(BaseModel):
    side: str
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)


class IPOApplyRequest(BaseModel):
    dividend_rate_pct: float = Field(
        default=5.0,
        ge=5.0,
        le=100.0,
        description="Daily closed-profit share committed to shareholders.",
    )

@router.get("/market")
async def get_stocks_market(session: AsyncSession = Depends(get_db_session)):
    await StockService.refresh_due_valuations(session, commit=True)
    res = await session.execute(
        select(NatStock, NatCompany)
        .join(NatCompany, NatStock.company_id == NatCompany.id)
        .where(NatStock.is_listed == True)
    )
    stocks = []
    for s, c in res.all():
        stocks.append({
            "stock_id": s.id,
            "company_id": c.id,
            "company_name": c.name,
            "specialization": c.specialization,
            "current_price": s.current_price,
            "total_shares": s.total_shares,
            "float_shares": s.float_shares,
            "last_valuation": s.last_valuation,
            "dividend_rate_pct": s.dividend_rate_pct,
            "valuation_updated_at": str(s.valuation_updated_at) if s.valuation_updated_at else None,
            "ipo_date": str(s.ipo_date),
            "history": await StockService.price_history(session, s.id, limit=120, days=31),
        })
    return {"stocks": stocks}





@router.get("/{stock_id}/history")
async def get_stock_history(
    stock_id: int,
    session: AsyncSession = Depends(get_db_session),
):
    return {
        "stock_id": stock_id,
        "history": await StockService.price_history(session, stock_id, limit=180),
    }

@router.get("/{stock_id}/orderbook")
async def get_stock_orderbook(
    stock_id: int,
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    try:
        return await StockOrderbookService.orderbook(session, stock_id, company.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{stock_id}/orders")
async def place_stock_limit_order(
    stock_id: int,
    req: StockLimitOrderRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = f"/api/natbirzha/stocks/{stock_id}/orders"
    payload = req.model_dump()
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        result = await StockOrderbookService.place_limit_order(
            session, company.id, stock_id, req.side, req.quantity, req.price, commit=False
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, result
    )


@router.delete("/orders/{order_id}")
async def cancel_stock_limit_order(
    order_id: int,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session),
):
    endpoint = f"/api/natbirzha/stocks/orders/{order_id}"
    payload = {"order_id": order_id}
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, endpoint, idempotency_key, payload
    )
    if cached:
        return cached[1]
    try:
        result = await StockOrderbookService.cancel_order(
            session, company.id, order_id, commit=False
        )
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await IdempotencyService.commit_response(
        session, company.user_id, endpoint, idempotency_key, payload, result
    )

@router.post("/ipo/apply")
async def apply_for_ipo(
    req: IPOApplyRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, "/api/natbirzha/stocks/ipo/apply", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    try:
        stock = await StockService.apply_for_ipo(session, company, dividend_rate_pct=req.dividend_rate_pct)
        resp = {
            "success": True,
            "stock_id": stock.id,
            "total_shares": stock.total_shares,
            "founder_shares": stock.founder_shares,
            "float_shares": stock.float_shares,
            "share_price": stock.current_price,
            "valuation": stock.last_valuation,
            "dividend_rate_pct": stock.dividend_rate_pct,
        }
        await IdempotencyService.save_record(
            session, company.user_id, "/api/natbirzha/stocks/ipo/apply", idempotency_key, req.model_dump(), 200, resp
        )
        return resp
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/portfolio")
async def get_portfolio(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    await StockService.refresh_due_valuations(session, commit=True)
    res = await session.execute(
        select(NatStockHolding, NatStock, NatCompany)
        .join(NatStock, NatStockHolding.stock_id == NatStock.id)
        .join(NatCompany, NatStock.company_id == NatCompany.id)
        .where(NatStockHolding.holder_company_id == company.id, NatStockHolding.shares_count > 0)
    )
    holdings = [
        {
            "stock_id": h.stock_id,
            "issuer_company": c.name,
            "shares_count": h.shares_count,
            "avg_buy_price": h.avg_price,
            "current_market_price": s.current_price,
            "total_value": round(h.shares_count * s.current_price, 2),
            "dividend_rate_pct": s.dividend_rate_pct,
        }
        for h, s, c in res.all()
    ]
    return {"portfolio": holdings}

@router.post("/buy")
async def buy_shares(
    req: BuyStockRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, "/api/natbirzha/stocks/buy", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    try:
        res = await StockService.buy_shares(session, company, req.stock_id, req.shares_count)
        await IdempotencyService.save_record(
            session, company.user_id, "/api/natbirzha/stocks/buy", idempotency_key, req.model_dump(), 200, res
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/sell")
async def sell_shares_route(
    req: SellStockRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    cached = await IdempotencyService.check_or_conflict(
        session, company.user_id, "/api/natbirzha/stocks/sell", idempotency_key, req.model_dump()
    )
    if cached:
        return cached[1]

    try:
        res = await StockService.sell_shares(session, company, req.stock_id, req.shares_count)
        await IdempotencyService.save_record(
            session, company.user_id, "/api/natbirzha/stocks/sell", idempotency_key, req.model_dump(), 200, res
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/settle_dividends")
async def settle_dividends_endpoint(
    company: NatCompany = Depends(get_current_company),
    session: AsyncSession = Depends(get_db_session)
):
    count = await DividendService.settle_all_public_dividends(session)
    return {"success": True, "settled_stocks_count": count}
