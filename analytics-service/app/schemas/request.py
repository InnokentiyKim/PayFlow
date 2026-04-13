from decimal import Decimal
from pydantic import Field
from app.common.dto import BaseRequestDTO


class PaymentCreateRequestDTO(BaseRequestDTO):
    amount: Decimal = Field(gt=0, max_digits=15, decimal_places=4)
    idempotency_key: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
