import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.common.enums import PaymentStatusEnum
from app.models.payments import Payment


@dataclass(slots=True, frozen=True)
class GetPaymentResult:
    id: uuid.UUID
    amount: Decimal
    currency: str
    status: PaymentStatusEnum
    description: str | None
    idempotency_key: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, payment: "Payment") -> "GetPaymentResult":
        return cls(
            id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            status=payment.status,
            description=payment.description,
            idempotency_key=payment.idempotency_key,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
        )


@dataclass(slots=True, frozen=True)
class CreatePaymentResult:
    id: uuid.UUID
    created_at: datetime
    status: PaymentStatusEnum
    idempotency_key: str
    is_exists: bool
