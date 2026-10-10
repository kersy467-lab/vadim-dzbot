"""Shared idempotent transaction boundary for independent 2.0 commands."""
from fastapi import HTTPException
from backend.natbirzha.services.idempotency_service import IdempotencyService
from backend.natbirzha.services.next_game_market_service import NextGameMarketService


async def mutate(session, admin, key, endpoint, payload, operation):
    if not key or not key.strip():
        raise HTTPException(status_code=400, detail="Нужен ключ идемпотентности")
    key = key.strip()[:128]
    try:
        await NextGameMarketService.lock_orderbook(session)
        cached = await IdempotencyService.check_or_conflict(session, admin.id, endpoint, key, payload)
        if cached:
            return cached[1]
        result = await operation()
        return await IdempotencyService.commit_response(session, admin.id, endpoint, key, payload, result)
    except ValueError as exc:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        await session.rollback()
        raise
