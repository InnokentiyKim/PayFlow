import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.models.transactions import Transactions


@dataclass(slots=True, frozen=True)
class StatusSummary:
    status: str
    count: int
    total_amount: Decimal


@dataclass(slots=True, frozen=True)
class CurrencySummary:
    currency: str
    count: int
    total_amount: Decimal


@dataclass(slots=True, frozen=True)
class SummaryReport:
    total_transactions: int
    total_amount: Decimal
    average_amount: Decimal
    by_status: list[StatusSummary]
    by_currency: list[CurrencySummary]
    date_from: datetime | None
    date_to: datetime | None


@dataclass(slots=True, frozen=True)
class TransactionResult:
    payment_id: uuid.UUID
    amount: Decimal
    currency: str
    status: str
    event_type: str
    processed_at: datetime

    @classmethod
    def from_model(cls, model: "Transactions") -> "TransactionResult":
        return cls(
            payment_id=model.payment_id,
            amount=model.amount,
            currency=model.currency,
            status=model.status,
            event_type=model.event_type,
            processed_at=model.processed_at,
        )
