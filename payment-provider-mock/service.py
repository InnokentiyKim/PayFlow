from __future__ import annotations

import asyncio
import random
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum

import structlog
from pydantic import BaseModel, Field
from starlette import status

logger = structlog.get_logger(__name__)


SUCCESS_RATE: float = 0.9
ERROR_RATE: float = 0.07            # 7 % → HTTP 500
TIMEOUT_RATE: float = 0.03          # 3 % → simulated timeout
TIMEOUT_DELAY_MIN: float = 10.0     # seconds
TIMEOUT_DELAY_MAX: float = 20.0     # seconds
NORMAL_DELAY_MIN: float = 0.05      # seconds – simulate real network latency
NORMAL_DELAY_MAX: float = 0.3       # seconds



class ProviderPaymentStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class ProcessPaymentRequest(BaseModel):
    payment_id: str = Field(..., description="Unique payment identifier")
    amount: Decimal = Field(..., gt=0, description="Payment amount")
    currency: str = Field(..., min_length=3, max_length=3)
    description: str | None = Field(default=None, max_length=1000)


class ProcessPaymentResponse(BaseModel):
    transaction_id: str = Field(..., description="Provider-side transaction ID")
    payment_id: str = Field(..., description="Original payment ID echoed back")
    status: ProviderPaymentStatus
    message: str
    processed_at: str


class ProviderErrorResponse(Exception):
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "An error occurred while processing the payment. Please retry."

    def __init__(self, status_code: int | None = None, detail: str | None = None):
        if status_code is not None:
            self.status_code = status_code
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


async def process_payment(payload: ProcessPaymentRequest) -> ProcessPaymentResponse:
    """
    Simulates processing a payment with random outcomes:
    - 90% chance of success (HTTP 200)
    - 7% chance of internal server error (HTTP 500)
    - 3% chance of timeout (simulated by delaying response and returning HTTP 504)

    Args:
        payload (ProcessPaymentRequest): The payment details to process.

    Returns:
        ProcessPaymentResponse: The result of the payment processing.

    Raises:
        ProviderErrorResponse: If an error occurs during processing.
    """
    roll = random.random()

    if roll > SUCCESS_RATE + ERROR_RATE:
        delay = random.uniform(TIMEOUT_DELAY_MIN, TIMEOUT_DELAY_MAX)
        await logger.awarn(
            "Simulating timeout",
            payment_id=payload.payment_id,
            delay_seconds=round(delay, 2),
        )
        await asyncio.sleep(delay)
        raise ProviderErrorResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="The payment provider timed out. Please retry.",
        )

    if roll > SUCCESS_RATE:
        await logger.awarn(
            "Simulating provider error",
            payment_id=payload.payment_id,
        )
        # Small realistic delay
        await asyncio.sleep(random.uniform(NORMAL_DELAY_MIN, NORMAL_DELAY_MAX))
        raise ProviderErrorResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the payment. Please retry.",
        )

    await asyncio.sleep(random.uniform(NORMAL_DELAY_MIN, NORMAL_DELAY_MAX))
    await logger.ainfo(
        "Payment processed successfully",
        payment_id=payload.payment_id,
        amount=str(payload.amount),
        currency=payload.currency,
    )

    return ProcessPaymentResponse(
        transaction_id=str(uuid.uuid4()),
        payment_id=payload.payment_id,
        status=ProviderPaymentStatus.SUCCESS,
        message="Payment processed successfully",
        processed_at=datetime.now(timezone.utc).isoformat(),
    )
