import hashlib
import json
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.idempotency import NatIdempotencyRecord


class IdempotencyService:
    @staticmethod
    def compute_payload_hash(payload: Any) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    async def check_or_conflict(
        cls,
        session: AsyncSession,
        user_id: int,
        endpoint: str,
        idempotency_key: Optional[str],
        payload: Any,
    ) -> Optional[Tuple[int, Dict[str, Any]]]:
        if not idempotency_key:
            return None

        req_hash = cls.compute_payload_hash(payload)
        res = await session.execute(
            select(NatIdempotencyRecord).where(
                NatIdempotencyRecord.user_id == user_id,
                NatIdempotencyRecord.endpoint == endpoint,
                NatIdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        record = res.scalar_one_or_none()
        if not record:
            return None
        if record.request_hash == req_hash:
            return record.status_code, record.response_body
        raise HTTPException(status_code=409, detail="Idempotency key reused with different payload.")

    @classmethod
    async def save_record(
        cls,
        session: AsyncSession,
        user_id: int,
        endpoint: str,
        idempotency_key: Optional[str],
        payload: Any,
        status_code: int,
        response_body: Dict[str, Any],
        commit: bool = True,
    ) -> None:
        if not idempotency_key:
            if commit:
                await session.commit()
            return
        session.add(
            NatIdempotencyRecord(
                user_id=user_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                request_hash=cls.compute_payload_hash(payload),
                status_code=status_code,
                response_body=response_body,
            )
        )
        if commit:
            await session.commit()
        else:
            await session.flush()

    @classmethod
    async def commit_response(
        cls,
        session: AsyncSession,
        user_id: int,
        endpoint: str,
        idempotency_key: Optional[str],
        payload: Any,
        response_body: Dict[str, Any],
        status_code: int = 200,
    ) -> Dict[str, Any]:
        """Commit business mutation and idempotency record in one DB transaction.

        If two workers race with the same key, the unique constraint makes one
        transaction win. The losing transaction is rolled back and returns the
        already committed cached response instead of duplicating the mutation.
        """
        if not idempotency_key:
            await session.commit()
            return response_body

        session.add(
            NatIdempotencyRecord(
                user_id=user_id,
                endpoint=endpoint,
                idempotency_key=idempotency_key,
                request_hash=cls.compute_payload_hash(payload),
                status_code=status_code,
                response_body=response_body,
            )
        )
        try:
            await session.commit()
            return response_body
        except IntegrityError:
            await session.rollback()
            cached = await cls.check_or_conflict(session, user_id, endpoint, idempotency_key, payload)
            if cached:
                return cached[1]
            raise
