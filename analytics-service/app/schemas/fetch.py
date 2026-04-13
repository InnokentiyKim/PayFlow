from dataclasses import dataclass
from datetime import datetime

from app.common.enums import PaymentStatusEnum


@dataclass(slots=True, frozen=True)
class GetAnalyticsSummary:
    date_from: datetime | None
    date_to: datetime | None
    currency: str | None


@dataclass(slots=True, frozen=True)
class GetPaymentByIdempotencyKey:
    date_from: datetime | None
    date_to: datetime | None
    currency: str | None
    status: PaymentStatusEnum | None
    limit: int
    offset: int


@dataclass(slots=True, frozen=True)
class GetTransactions:
    date_from: datetime | None
    date_to: datetime | None
    currency: str | None
    status: PaymentStatusEnum | None
    limit: int
    offset: int
