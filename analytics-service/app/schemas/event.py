import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PaymentEvent(BaseModel):
    """Structured payload for outbox events related to payments."""

    event_type: str
    payment_id: uuid.UUID
    amount: Decimal
    currency: str
    status: str
    timestamp: datetime
    failure_reason: str | None = None
