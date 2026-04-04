import uuid
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class GetPaymentInfo:
    payment_id: uuid.UUID


@dataclass(slots=True, frozen=True)
class GetPaymentByIdempotencyKey:
    idempotency_key: str
