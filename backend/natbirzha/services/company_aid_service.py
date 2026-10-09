"""Voluntary gifts from established companies to small companies."""

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.natbirzha.models.company import NatCompany
from backend.natbirzha.models.company_aid import NatCompanyAidRequest, NatCompanyAidTransfer
from backend.natbirzha.models.inventory import CANONICAL_ITEMS, NatInventory


class CompanyAidService:
    """Transfer existing cash or unreserved goods; this service never mints funds."""

    RECEIVABLE_LIMIT_CASH = 100_000.0
    RECEIVABLE_WINDOW = timedelta(days=7)

    @staticmethod
    def _now(value: datetime | None) -> datetime:
        return value or datetime.utcnow()

    @staticmethod
    def _finite_number(value: float | int | None, label: str) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Некорректное значение: {label}") from exc
        if not math.isfinite(number):
            raise ValueError(f"Значение {label} должно быть конечным числом")
        return number

    @classmethod
    def _cash_amount(cls, value: float | int | None, label: str) -> float:
        number = cls._finite_number(value, label)
        if number <= 0:
            raise ValueError(f"Сумма {label} должна быть положительной")
        try:
            rounded = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except InvalidOperation as exc:
            raise ValueError(f"Некорректное значение: {label}") from exc
        if rounded < Decimal("0.01"):
            raise ValueError(f"Минимальная сумма перевода — 0.01 cash")
        return float(rounded)

    @classmethod
    def _item_quantity(cls, value: float | int | None, label: str) -> float:
        number = cls._finite_number(value, label)
        if number <= 0:
            raise ValueError(f"Количество {label} должно быть положительным")
        try:
            raw = Decimal(str(value))
            rounded = raw.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        except InvalidOperation as exc:
            raise ValueError(f"Некорректное количество: {label}") from exc
        if raw != rounded:
            raise ValueError(f"Количество товара поддерживает не более 6 знаков после запятой")
        return float(rounded)

    @classmethod
    def _item_cash_value(cls, item_id: str, quantity: float) -> float:
        base_price = Decimal(str(CANONICAL_ITEMS[item_id]["base_price"]))
        return float((Decimal(str(quantity)) * base_price).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP,
        ))

    @staticmethod
    def _request_view(
        request: NatCompanyAidRequest, *, company_name: str | None = None
    ) -> dict[str, Any]:
        view = {
            "id": request.id,
            "company_id": request.company_id,
            "kind": request.kind,
            "amount_cash": request.amount_cash,
            "item_id": request.item_id,
            "item_quantity": request.item_quantity,
            "fulfilled_quantity": request.fulfilled_quantity,
            "fulfilled_value_cash": request.fulfilled_value_cash,
            "message": request.message,
            "status": request.status,
            "created_at": request.created_at.isoformat() if request.created_at else None,
        }
        if company_name is not None:
            view["company_name"] = company_name
        return view

    @classmethod
    async def create_request(
        cls,
        session: AsyncSession,
        company_id: int,
        *,
        kind: str,
        amount_cash: float | None = None,
        item_id: str | None = None,
        item_quantity: float | None = None,
        message: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        company = await session.scalar(
            select(NatCompany).where(NatCompany.id == company_id)
            .with_for_update().execution_options(populate_existing=True)
        )
        if not company or company.is_bankrupt:
            raise ValueError("Компания не найдена или находится в банкротстве")
        if kind == "cash":
            if amount_cash is None:
                raise ValueError("Запрос денег должен быть от 0 до 100 000 cash")
            amount_cash = cls._cash_amount(amount_cash, "запроса")
            if amount_cash > cls.RECEIVABLE_LIMIT_CASH:
                raise ValueError("Запрос денег должен быть от 0 до 100 000 cash")
            if item_id is not None or item_quantity is not None:
                raise ValueError("Для денежного запроса нельзя указывать товар")
        elif kind == "item":
            if not item_id or item_id not in CANONICAL_ITEMS:
                raise ValueError("Неизвестный товар")
            if item_quantity is None:
                raise ValueError("Укажите положительное количество товара")
            item_quantity = cls._item_quantity(item_quantity, "запроса")
            if amount_cash is not None:
                raise ValueError("Для запроса товара нельзя указывать деньги")
            if cls._item_cash_value(item_id, item_quantity) > cls.RECEIVABLE_LIMIT_CASH:
                raise ValueError("Стоимость запроса превышает недельный лимит помощи 100 000 cash")
        else:
            raise ValueError("Тип запроса должен быть cash или item")

        open_request = await session.scalar(select(NatCompanyAidRequest.id).where(
            NatCompanyAidRequest.company_id == company_id,
            NatCompanyAidRequest.status == "OPEN",
        ).limit(1))
        if open_request:
            raise ValueError("У компании уже есть открытый запрос помощи")

        request = NatCompanyAidRequest(
            company_id=company_id,
            kind=kind,
            amount_cash=amount_cash,
            item_id=item_id,
            item_quantity=item_quantity,
            message=(message or "").strip()[:500] or None,
            created_at=cls._now(now),
        )
        session.add(request)
        await session.flush()
        return cls._request_view(request)

    @classmethod
    async def list_requests(
        cls, session: AsyncSession, *, exclude_company_id: int | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        rows = (await session.execute(
            select(NatCompanyAidRequest, NatCompany.name)
            .join(NatCompany, NatCompany.id == NatCompanyAidRequest.company_id)
            .where(
                NatCompanyAidRequest.status == "OPEN",
                NatCompany.is_bankrupt.is_(False),
                *([NatCompanyAidRequest.company_id != exclude_company_id]
                  if exclude_company_id is not None else []),
            )
            .order_by(NatCompanyAidRequest.created_at.desc())
            .limit(max(1, min(limit, 100)))
        )).all()
        return [cls._request_view(row, company_name=name) for row, name in rows]

    @classmethod
    async def cancel_request(
        cls, session: AsyncSession, company_id: int, request_id: int
    ) -> dict[str, Any]:
        request = await session.scalar(select(NatCompanyAidRequest).where(
            NatCompanyAidRequest.id == request_id,
            NatCompanyAidRequest.company_id == company_id,
        ).with_for_update())
        if not request or request.status != "OPEN":
            raise ValueError("Открытый запрос не найден")
        request.status = "CANCELLED"
        request.updated_at = datetime.utcnow()
        await session.flush()
        return cls._request_view(request)

    @staticmethod
    async def _received_recently(
        session: AsyncSession, company_id: int, cutoff: datetime
    ) -> float:
        total = await session.scalar(select(func.coalesce(func.sum(
            NatCompanyAidTransfer.aid_value_cash
        ), 0.0)).where(
            NatCompanyAidTransfer.recipient_company_id == company_id,
            NatCompanyAidTransfer.created_at >= cutoff,
        ))
        return float(total or 0.0)

    @staticmethod
    async def _recent_recipients(
        session: AsyncSession, sender_company_id: int, cutoff: datetime
    ) -> set[int]:
        recipient_ids = await session.scalars(select(
            NatCompanyAidTransfer.recipient_company_id.distinct()
        ).where(
            NatCompanyAidTransfer.sender_company_id == sender_company_id,
            NatCompanyAidTransfer.created_at >= cutoff,
        ))
        return {int(company_id) for company_id in recipient_ids.all()}

    @classmethod
    async def summary(
        cls, session: AsyncSession, company_id: int, *, now: datetime | None = None,
    ) -> dict[str, Any]:
        current_time = cls._now(now)
        lifetime = (await session.execute(select(
            func.count(NatCompanyAidTransfer.recipient_company_id.distinct()),
            func.coalesce(func.sum(NatCompanyAidTransfer.aid_value_cash), 0.0),
        ).where(NatCompanyAidTransfer.sender_company_id == company_id))).one()
        supported_companies = int(lifetime[0] or 0)
        total_aid_value = float(lifetime[1] or 0.0)
        if supported_companies >= 10:
            mentor_title = "Меценат"
        elif supported_companies >= 5:
            mentor_title = "Куратор"
        elif supported_companies >= 1:
            mentor_title = "Наставник"
        else:
            mentor_title = "Будущий наставник"
        cutoff = current_time - cls.RECEIVABLE_WINDOW
        current_week_supported = await cls._recent_recipients(
            session, company_id, cutoff,
        )
        received_recently = await cls._received_recently(session, company_id, cutoff)
        return {
            "supported_companies": supported_companies,
            "total_aid_value_cash": round(total_aid_value, 2),
            "mentor_title": mentor_title,
            "current_week_supported_count": len(current_week_supported),
            "max_supported_companies_per_week": 2,
            "recipient_week_remaining_cash": round(max(
                0.0, cls.RECEIVABLE_LIMIT_CASH - received_recently,
            ), 2),
        }

    @classmethod
    async def transfer(
        cls,
        session: AsyncSession,
        sender_company_id: int,
        recipient_company_id: int,
        *,
        amount_cash: float | None = None,
        item_id: str | None = None,
        quantity: float | None = None,
        request_id: int | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if sender_company_id == recipient_company_id:
            raise ValueError("Нельзя отправить помощь самой себе")
        cash_transfer = amount_cash is not None
        item_transfer = item_id is not None or quantity is not None
        if cash_transfer == item_transfer:
            raise ValueError("Переведите либо деньги, либо один вид товара")
        if cash_transfer and (amount_cash is None or amount_cash <= 0):
            raise ValueError("Сумма перевода должна быть положительной")
        if item_transfer and (not item_id or quantity is None or quantity <= 0):
            raise ValueError("Укажите товар и положительное количество")
        if item_transfer and item_id not in CANONICAL_ITEMS:
            raise ValueError("Неизвестный товар")
        if request_id is None:
            raise ValueError("Перед переводом получатель должен создать открытую заявку на помощь")

        company_ids = sorted((sender_company_id, recipient_company_id))
        companies = (await session.scalars(
            select(NatCompany).where(NatCompany.id.in_(company_ids))
            .order_by(NatCompany.id).with_for_update()
            .execution_options(populate_existing=True)
        )).all()
        by_id = {company.id: company for company in companies}
        sender, recipient = by_id.get(sender_company_id), by_id.get(recipient_company_id)
        if not sender or not recipient or sender.is_bankrupt or recipient.is_bankrupt:
            raise ValueError("Обе компании должны существовать и быть активны")
        request = await session.scalar(select(NatCompanyAidRequest).where(
            NatCompanyAidRequest.id == request_id,
        ).with_for_update())
        if not request or request.company_id != recipient_company_id or request.status != "OPEN":
            raise ValueError("Открытый запрос этой компании не найден")
        if cash_transfer and (request.kind != "cash" or request.amount_cash is None):
            raise ValueError("Перевод должен соответствовать запросу помощи")
        if item_transfer and (
            request.kind != "item" or request.item_id != item_id or request.item_quantity is None
        ):
            raise ValueError("Передаваемый товар не соответствует запросу")

        current_time = cls._now(now)
        if cash_transfer:
            value_cash = cls._cash_amount(amount_cash, "перевода")
            if value_cash > float(sender.cash):
                raise ValueError("Недостаточно cash у отправителя")
            if request and float(request.amount_cash or 0) - request.fulfilled_value_cash + 1e-6 < value_cash:
                raise ValueError("Сумма больше остатка запроса")
            transferred_quantity = 0.0
            transferred_item_id = None
        else:
            assert item_id is not None and quantity is not None
            quantity = cls._item_quantity(quantity, "перевода")
            value_cash = cls._item_cash_value(item_id, quantity)
            if request and float(request.item_quantity or 0) - request.fulfilled_quantity + 1e-6 < quantity:
                raise ValueError("Количество больше остатка запроса")
            inventory = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == sender_company_id,
                NatInventory.item_id == item_id,
            ).with_for_update())
            if not inventory or inventory.quantity - inventory.reserved_quantity + 1e-6 < quantity:
                raise ValueError("Недостаточно доступного товара: часть запаса зарезервирована")
            transferred_quantity = float(quantity)
            transferred_item_id = item_id

        cutoff = current_time - cls.RECEIVABLE_WINDOW
        helped_companies = await cls._recent_recipients(session, sender_company_id, cutoff)
        if recipient_company_id not in helped_companies and len(helped_companies) >= 2:
            raise ValueError("Наставник может помогать не более чем двум разным компаниям за 7 дней")
        already_received = await cls._received_recently(session, recipient_company_id, cutoff)
        if already_received + value_cash > cls.RECEIVABLE_LIMIT_CASH + 1e-6:
            remaining = max(0.0, cls.RECEIVABLE_LIMIT_CASH - already_received)
            raise ValueError(f"Недельный лимит помощи превышен; осталось {remaining:.2f} cash")

        if cash_transfer:
            sender.cash = float((Decimal(str(sender.cash)) - Decimal(str(value_cash))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP,
            ))
            recipient.cash = float((Decimal(str(recipient.cash)) + Decimal(str(value_cash))).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP,
            ))
        else:
            inventory.quantity -= transferred_quantity
            receiver_inventory = await session.scalar(select(NatInventory).where(
                NatInventory.company_id == recipient_company_id,
                NatInventory.item_id == transferred_item_id,
            ).with_for_update())
            if receiver_inventory is None:
                receiver_inventory = NatInventory(
                    company_id=recipient_company_id,
                    item_id=transferred_item_id,
                    quantity=0.0,
                    reserved_quantity=0.0,
                    avg_cost_basis=inventory.avg_cost_basis,
                )
                session.add(receiver_inventory)
                await session.flush()
            prior_value = receiver_inventory.quantity * receiver_inventory.avg_cost_basis
            incoming_value = transferred_quantity * inventory.avg_cost_basis
            receiver_inventory.quantity += transferred_quantity
            receiver_inventory.avg_cost_basis = (
                (prior_value + incoming_value) / receiver_inventory.quantity
                if receiver_inventory.quantity > 0 else 0.0
            )
            receiver_inventory.updated_at = current_time
            inventory.updated_at = current_time

        transfer = NatCompanyAidTransfer(
            sender_company_id=sender_company_id,
            recipient_company_id=recipient_company_id,
            request_id=request.id if request else None,
            cash_amount=value_cash if cash_transfer else 0.0,
            item_id=transferred_item_id,
            item_quantity=transferred_quantity,
            aid_value_cash=value_cash,
            created_at=current_time,
        )
        session.add(transfer)
        if request:
            if cash_transfer:
                request.fulfilled_value_cash += value_cash
                if request.fulfilled_value_cash + 1e-6 >= float(request.amount_cash or 0):
                    request.status = "FULFILLED"
            else:
                request.fulfilled_quantity += transferred_quantity
                if request.fulfilled_quantity + 1e-6 >= float(request.item_quantity or 0):
                    request.status = "FULFILLED"
            request.updated_at = current_time
        await session.flush()
        return {
            "id": transfer.id,
            "sender_company_id": sender_company_id,
            "recipient_company_id": recipient_company_id,
            "request_id": transfer.request_id,
            "cash_amount": transfer.cash_amount,
            "item_id": transfer.item_id,
            "item_quantity": transfer.item_quantity,
            "aid_value_cash": transfer.aid_value_cash,
            "created_at": current_time.isoformat(),
            "weekly_limit_cash": cls.RECEIVABLE_LIMIT_CASH,
            "weekly_received_cash": already_received + value_cash,
        }


__all__ = ["CompanyAidService"]
