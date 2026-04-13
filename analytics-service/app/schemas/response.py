import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.common.dto import BaseDTO
from app.schemas.results import SummaryReport


class TransactionResponseDTO(BaseDTO):
    """DTO for representing a transaction in API responses."""

    payment_id: uuid.UUID
    amount: Decimal
    currency: str
    status: str
    event_type: str
    processed_at: datetime


class StatusBreakdownDTO(BaseModel):
    """DTO for breakdown of transactions by status."""

    model_config = ConfigDict(from_attributes=True)

    status: str
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

    @classmethod
    def from_report(cls, report: "SummaryReport") -> "AnalyticsSummaryResponseDTO":
        return cls(
            total_transactions=report.total_transactions,
            total_amount=report.total_amount,
            average_amount=report.average_amount,
            by_status=[
                StatusBreakdownDTO(
                    status=s.status, count=s.count, total_amount=s.total_amount
                )
                for s in report.by_status
            ],
            by_currency=[
                CurrencyBreakdownDTO(
                    currency=c.currency, count=c.count, total_amount=c.total_amount
                )
                for c in report.by_currency
            ],
            period_start=report.date_from,
            period_end=report.date_to,
        )
