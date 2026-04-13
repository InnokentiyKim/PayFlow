import uuid
from datetime import datetime, UTC
from decimal import Decimal


from app.schemas.event import PaymentEvent
from app.schemas.results import (
    CurrencySummary,
    StatusSummary,
    SummaryReport,
    TransactionResult,
)


def make_transaction_result(
    *,
    payment_id: uuid.UUID | None = None,
    amount: Decimal = Decimal("100.0000"),
    currency: str = "USD",
    status: str = "completed",
    event_type: str = "payment.completed",
    processed_at: datetime | None = None,
    id: uuid.UUID | None = None,
) -> TransactionResult:
    return TransactionResult(
        payment_id=payment_id or uuid.uuid4(),
        amount=amount,
        currency=currency,
        status=status,
        event_type=event_type,
        processed_at=processed_at or datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC),
    )


def make_summary_report(
    *,
    total_transactions: int = 5,
    total_amount: Decimal = Decimal("500.0000"),
    average_amount: Decimal = Decimal("100.0000"),
    by_status: list[StatusSummary] | None = None,
    by_currency: list[CurrencySummary] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> SummaryReport:
    return SummaryReport(
        total_transactions=total_transactions,
        total_amount=total_amount,
        average_amount=average_amount,
        by_status=[
            StatusSummary(status="completed", count=5, total_amount=total_amount)
        ]
        if by_status is None
        else by_status,
        by_currency=[
            CurrencySummary(currency="USD", count=5, total_amount=total_amount)
        ]
        if by_currency is None
        else by_currency,
        date_from=date_from,
        date_to=date_to,
    )


def make_payment_event(
    *,
    payment_id: uuid.UUID | None = None,
    amount: Decimal = Decimal("250.00"),
    currency: str = "USD",
    status: str = "completed",
    event_type: str = "payment.completed",
    timestamp: datetime | None = None,
) -> PaymentEvent:
    return PaymentEvent(
        event_type=event_type,
        payment_id=payment_id or uuid.uuid4(),
        amount=amount,
        currency=currency,
        status=status,
        timestamp=timestamp or datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC),
    )
