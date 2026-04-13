from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True, frozen=True)
class CreatePaymentCommand:
    amount: Decimal
    currency: str
    idempotency_key: str
    description: str | None
