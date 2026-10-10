"""Validated inputs for the isolated 2.0 economic endpoints."""
from typing import Literal, Optional
from math import isfinite
from pydantic import BaseModel, Field, field_validator
from backend.natbirzha.services.next_game_service import (
    MAX_TRADE_QUANTITY, MAX_BANK_LOAN, MAX_BANK_DEPOSIT, MAX_BANK_DEPOSIT_DAYS,
)


class CreateSandboxCompany(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class SelectSector(BaseModel):
    sector_id: str = Field(min_length=2, max_length=48)


class SelectBranch(BaseModel):
    branch_id: str = Field(min_length=2, max_length=64)


class BuildFacility(BaseModel):
    branch_id: Optional[str] = Field(default=None, min_length=2, max_length=64)


class TradeItem(BaseModel):
    item_id: str = Field(min_length=1, max_length=64)
    side: Literal["BUY", "SELL"]
    quantity: float = Field(gt=0, le=MAX_TRADE_QUANTITY)

    @field_validator("quantity")
    @classmethod
    def finite_quantity(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Количество должно быть конечное число")
        return value


class LimitOrderRequest(BaseModel):
    item_id: str = Field(min_length=1, max_length=64)
    side: Literal["BUY", "SELL"]
    quantity: float = Field(gt=0, le=MAX_TRADE_QUANTITY)
    limit_price: float = Field(gt=0)

    @field_validator("quantity")
    @classmethod
    def valid_quantity(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Количество должно быть конечное число")
        rounded = round(value, 4)
        if abs(value - rounded) > 1e-9:
            raise ValueError("Количество можно указать максимум с 4 знаками после запятой")
        return rounded

    @field_validator("limit_price")
    @classmethod
    def finite_limit_price(cls, value: float) -> float:
        if not isfinite(value) or value <= 0:
            raise ValueError("Лимитная цена должна быть конечным числом больше нуля")
        rounded = round(value, 4)
        if abs(value - rounded) > 1e-9:
            raise ValueError("Лимитную цену можно указать максимум с 4 знаками после запятой")
        return rounded


class BankLoanRequest(BaseModel):
    amount: float = Field(gt=0, le=MAX_BANK_LOAN)

    @field_validator("amount")
    @classmethod
    def finite_amount(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Сумма кредита должна быть конечным числом")
        return value


class BankDepositRequest(BaseModel):
    amount: float = Field(gt=0, le=MAX_BANK_DEPOSIT)
    term_days: int = Field(ge=1, le=MAX_BANK_DEPOSIT_DAYS)

    @field_validator("amount")
    @classmethod
    def finite_amount(cls, value: float) -> float:
        if not isfinite(value):
            raise ValueError("Сумма вклада должна быть конечным числом")
        if abs(value - round(value, 2)) > 1e-9:
            raise ValueError("Сумму вклада можно указать максимум с двумя знаками после запятой")
        return value


