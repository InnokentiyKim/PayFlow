import uuid
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.events import ProcessedEvents
from app.models.transactions import Transactions
from consumer.payment_event_consumer import PaymentEventConsumer, SUMMARY_CACHE_PREFIX
from tests.test_consumer.conftest import make_consumer_record


def _build_batch(records: list[MagicMock]) -> dict:
    """Wrap a list of records into the dict[TopicPartition, list[ConsumerRecord]] shape."""
    tp = MagicMock()
    return {tp: records}


async def test_single_event_persisted(
    consumer: PaymentEventConsumer,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A single valid event should be persisted to the DB."""
    pid = uuid.uuid4()
    batch = _build_batch([make_consumer_record(payment_id=pid)])

    await consumer._handle_batch(batch)

    async with session_factory() as session:
        txn = (await session.execute(select(Transactions))).scalars().all()
        assert len(txn) == 1
        assert txn[0].payment_id == pid

        events = (await session.execute(select(ProcessedEvents))).scalars().all()
        assert len(events) == 1

    consumer._consumer.commit.assert_called()


async def test_multiple_events_persisted(
    consumer: PaymentEventConsumer,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Multiple valid events in a batch should all be saved."""
    records = [make_consumer_record() for _ in range(5)]
    batch = _build_batch(records)

    await consumer._handle_batch(batch)

    async with session_factory() as session:
        txns = (await session.execute(select(Transactions))).scalars().all()
        assert len(txns) == 5


async def test_duplicate_event_skipped(
    consumer: PaymentEventConsumer,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """If an event_id already exists in processed_events, it should be skipped."""
    eid = uuid.uuid4()
    pid = uuid.uuid4()

    # Pre-insert the event as "already processed"
    async with session_factory() as session:
        async with session.begin():
            session.add(ProcessedEvents(event_id=eid))

    record = make_consumer_record(event_id=eid, payment_id=pid)
    batch = _build_batch([record])

    await consumer._handle_batch(batch)

    async with session_factory() as session:
        txns = (await session.execute(select(Transactions))).scalars().all()
        assert len(txns) == 0  # should NOT be persisted


async def test_intra_batch_duplicates(
    consumer: PaymentEventConsumer,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Two messages with the same event_id in the same batch — only the first should be saved."""
    eid = uuid.uuid4()
    pid = uuid.uuid4()
    r1 = make_consumer_record(event_id=eid, payment_id=pid)
    r2 = make_consumer_record(event_id=eid, payment_id=pid)
    batch = _build_batch([r1, r2])

    await consumer._handle_batch(batch)

    async with session_factory() as session:
        txns = (await session.execute(select(Transactions))).scalars().all()
        assert len(txns) == 1


async def test_invalid_messages_skipped(
    consumer: PaymentEventConsumer,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Invalid messages should be skipped; valid ones still saved."""
    valid_record = make_consumer_record()
    invalid_record = make_consumer_record(key=None)  # missing key → skipped

    batch = _build_batch([invalid_record, valid_record])
    await consumer._handle_batch(batch)

    async with session_factory() as session:
        txns = (await session.execute(select(Transactions))).scalars().all()
        assert len(txns) == 1


async def test_all_invalid_batch_commits_offsets(
    consumer: PaymentEventConsumer,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A batch with only invalid messages should still commit Kafka offsets."""
    batch = _build_batch(
        [
            make_consumer_record(key=None),
            make_consumer_record(key=b"bad-key"),
        ]
    )

    await consumer._handle_batch(batch)

    consumer._consumer.commit.assert_called()

    async with session_factory() as session:
        txns = (await session.execute(select(Transactions))).scalars().all()
        assert len(txns) == 0


async def test_cache_invalidated_on_save(
    consumer: PaymentEventConsumer,
    mock_cache_service: AsyncMock,
) -> None:
    """When events are saved, the summary cache should be invalidated."""
    batch = _build_batch([make_consumer_record()])
    await consumer._handle_batch(batch)

    mock_cache_service.invalidate_cache.assert_called_once_with(
        cache_prefix=SUMMARY_CACHE_PREFIX
    )


async def test_cache_not_invalidated_on_all_duplicates(
    consumer: PaymentEventConsumer,
    session_factory: async_sessionmaker[AsyncSession],
    mock_cache_service: AsyncMock,
) -> None:
    """When all events are duplicates (nothing saved), cache should NOT be invalidated."""
    eid = uuid.uuid4()

    # Pre-insert the event
    async with session_factory() as session:
        async with session.begin():
            session.add(ProcessedEvents(event_id=eid))

    record = make_consumer_record(event_id=eid)
    batch = _build_batch([record])

    await consumer._handle_batch(batch)

    mock_cache_service.invalidate_cache.assert_not_called()


async def test_no_cache_service_does_not_crash(
    config,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Consumer without cache_service should work fine."""
    import asyncio

    pec = PaymentEventConsumer(
        config=config,
        session_factory=session_factory,
        cache_service=None,
        stop_event=asyncio.Event(),
    )
    pec._consumer = AsyncMock()

    batch = _build_batch([make_consumer_record()])
    await pec._handle_batch(batch)


async def test_offsets_committed_after_success(
    consumer: PaymentEventConsumer,
) -> None:
    """Kafka offsets must be committed after a successful batch."""
    batch = _build_batch([make_consumer_record()])
    await consumer._handle_batch(batch)
    consumer._consumer.commit.assert_called()


async def test_empty_batch_commits_offsets(
    consumer: PaymentEventConsumer,
) -> None:
    """An empty batch (no messages) should not crash."""
    # _handle_batch expects at least one TP; an "empty valid" scenario
    batch = _build_batch([make_consumer_record(key=None)])
    await consumer._handle_batch(batch)
    consumer._consumer.commit.assert_called()
