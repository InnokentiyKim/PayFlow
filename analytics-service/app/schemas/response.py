import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.common.dto import BaseResponseDTO
from app.common.enums import PaymentStatusEnum


class TransactionResponseDTO(BaseResponseDTO):
    """DTO for representing a transaction in API responses."""

    payment_id: uuid.UUID
    amount: Decimal
    currency: str
    status: PaymentStatusEnum
    event_type: str
    processed_at: datetime


class StatusBreakdownDTO(BaseModel):
    """DTO for breakdown of transactions by status."""

    model_config = ConfigDict(from_attributes=True)

    status: PaymentStatusEnum
    count: int
    total_amount: Decimal


class CurrencyBreakdownDTO(BaseModel):
    """DTO for breakdown of transactions by currency."""

    model_config = ConfigDict(from_attributes=True)

    currency: str
    count: int
    total_amount: Decimal


class AnalyticsSummaryResponseDTO(BaseModel):
    """Сводка аналитики по транзакциям."""

    model_config = ConfigDict(from_attributes=True)

    total_transactions: int
    total_amount: Decimal
    average_amount: Decimal
    by_status: list[StatusBreakdownDTO]
    by_currency: list[CurrencyBreakdownDTO]
    period_start: datetime | None = None
    period_end: datetime | None = None
