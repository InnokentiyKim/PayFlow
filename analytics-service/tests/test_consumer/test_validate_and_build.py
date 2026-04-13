import uuid
from datetime import datetime, UTC
from decimal import Decimal
from unittest.mock import MagicMock


from app.common.enums import PaymentStatusEnum
from consumer.payment_event_consumer import PaymentEventConsumer
from tests.test_consumer.conftest import make_consumer_record


async def test_valid_message_returns_tuple(consumer: PaymentEventConsumer) -> None:
    """A well-formed message should return (event_id, Transaction, PaymentEvent)."""
    eid = uuid.uuid4()
    pid = uuid.uuid4()
    record = make_consumer_record(event_id=eid, payment_id=pid, amount=Decimal("55.00"))

    result = await consumer._validate_and_build(record)

    assert result is not None
    event_id, transaction, event = result
    assert event_id == eid
    assert transaction.payment_id == pid
    assert transaction.amount == Decimal("55.00")
    assert transaction.currency == "USD"
    assert transaction.status == PaymentStatusEnum.COMPLETED
    assert event.payment_id == pid


async def test_valid_message_all_statuses(consumer: PaymentEventConsumer) -> None:
    """All known statuses should be accepted."""
    for status in PaymentStatusEnum:
        record = make_consumer_record(
            status=status.value, event_type=f"payment.{status.value}"
        )
        result = await consumer._validate_and_build(record)
        assert result is not None
        _, txn, _ = result
        assert txn.status == status


async def test_missing_key_returns_none(consumer: PaymentEventConsumer) -> None:
    """Message with key=None should be skipped."""
    record = make_consumer_record(key=None)
    result = await consumer._validate_and_build(record)
    assert result is None


async def test_invalid_uuid_key_returns_none(consumer: PaymentEventConsumer) -> None:
    """Message whose key is not a valid UUID should be skipped."""
    record = make_consumer_record(key=b"not-a-uuid")
    result = await consumer._validate_and_build(record)
    assert result is None


async def test_non_utf8_key_returns_none(consumer: PaymentEventConsumer) -> None:
    """Message whose key is invalid UTF-8 should be skipped."""
    record = make_consumer_record(key=b"\xff\xfe")
    result = await consumer._validate_and_build(record)
    assert result is None


async def test_missing_required_field_returns_none(
    consumer: PaymentEventConsumer,
) -> None:
    """Payload missing a required field should be skipped."""
    eid = uuid.uuid4()
    record = make_consumer_record(event_id=eid)
    # Remove a required field
    del record.value["amount"]
    result = await consumer._validate_and_build(record)
    assert result is None


async def test_completely_wrong_payload_returns_none(
    consumer: PaymentEventConsumer,
) -> None:
    """A payload that cannot be validated at all should be skipped."""
    record = MagicMock()
    record.key = str(uuid.uuid4()).encode("utf-8")
    record.value = {"garbage": True}
    result = await consumer._validate_and_build(record)
    assert result is None


async def test_invalid_amount_type_returns_none(consumer: PaymentEventConsumer) -> None:
    """Payload with non-numeric amount should be skipped."""
    eid = uuid.uuid4()
    record = make_consumer_record(event_id=eid)
    record.value["amount"] = "not-a-number"
    result = await consumer._validate_and_build(record)
    assert result is None


async def test_event_preserves_timestamp(consumer: PaymentEventConsumer) -> None:
    """The transaction's processed_at should match the event timestamp."""
    ts = datetime(2024, 1, 15, 8, 30, 0, tzinfo=UTC)
    record = make_consumer_record(timestamp=ts)

    result = await consumer._validate_and_build(record)
    assert result is not None
    _, txn, event = result
    assert txn.processed_at == ts
    assert event.timestamp == ts


async def test_event_currencies(consumer: PaymentEventConsumer) -> None:
    """Different currencies should be accepted."""
    for cur in ("USD", "EUR", "RUB"):
        record = make_consumer_record(currency=cur)
        result = await consumer._validate_and_build(record)
        assert result is not None
        _, txn, _ = result
        assert txn.currency == cur
