import asyncio
import json
import uuid

import structlog
from aiokafka import AIOKafkaConsumer, ConsumerRecord, TopicPartition
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.common.enums import PaymentStatusEnum
from app.core.config import Configs
from app.models.events import ProcessedEvents
from app.models.transactions import Transactions
from app.schemas.event import PaymentEvent
from app.services.cache import CacheService


SUMMARY_CACHE_PREFIX = "analytics:summary"


class PaymentEventConsumer:
    """
    Kafka consumer that processes payment events from a specified topic,
    ensuring idempotent persistence to the database and robust error handling.
    """

    def __init__(
        self,
        config: Configs,
        session_factory: async_sessionmaker[AsyncSession],
        cache_service: CacheService | None = None,
        stop_event: asyncio.Event | None = None,
    ) -> None:
        self._config = config
        self._session_factory = session_factory
        self._cache_service = cache_service
        self._stop_event = stop_event or asyncio.Event()
        self._logger = structlog.get_logger(config.logger.app_logger_name)
        self._consumer: AIOKafkaConsumer | None = None

    async def start(self) -> None:
        """Create the underlying AIOKafkaConsumer, start it, and begin consuming."""
        self._consumer = AIOKafkaConsumer(
            self._config.broker.kafka_topic_payment_events,
            bootstrap_servers=self._config.broker.kafka_bootstrap_servers,
            group_id=self._config.broker.kafka_consumer_group,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            max_poll_records=self._config.broker.kafka_consumer_batch_max_records,
            max_poll_interval_ms=self._config.broker.kafka_consumer_max_poll_interval_ms,
        )

        await self._consumer.start()
        await self._logger.ainfo(
            "Kafka consumer started",
            topic=self._config.broker.kafka_topic_payment_events,
            group_id=self._config.broker.kafka_consumer_group,
            batch_max_records=self._config.broker.kafka_consumer_batch_max_records,
            batch_timeout_ms=self._config.broker.kafka_consumer_batch_timeout_ms,
        )

        try:
            await self._consume()
        finally:
            await self._consumer.stop()
            await self._logger.ainfo("Kafka consumer stopped")

    async def stop(self) -> None:
        """Signal the consumer to stop gracefully after the current batch."""
        await self._logger.ainfo("Graceful shutdown signal received")
        self._stop_event.set()

    async def _consume(self) -> None:
        """
        Fetch messages in batches via ``getmany()`` and process each batch
        atomically: all valid events are persisted in one DB transaction,
        followed by a single Kafka offset commit.
        """
        assert self._consumer is not None

        timeout_ms = self._config.broker.kafka_consumer_batch_timeout_ms

        while not self._stop_event.is_set():
            batch: dict[
                TopicPartition, list[ConsumerRecord]
            ] = await self._consumer.getmany(timeout_ms=timeout_ms)

            if not batch:
                continue

            total_messages = sum(len(msgs) for msgs in batch.values())

            await self._logger.adebug(
                "Fetched message batch",
                partitions=len(batch),
                total_messages=total_messages,
            )

            try:
                await self._handle_batch(batch)
            except Exception as exc:
                await self._logger.aerror(
                    "Failed to process message batch",
                    error=str(exc),
                    total_messages=total_messages,
                    exc_info=True,
                )

    async def _handle_batch(
        self,
        batch: dict[TopicPartition, list[ConsumerRecord]],
    ) -> None:
        """
        Validate every message in the batch, check idempotency via
        ``processed_events``, persist new events together with their
        ``processed_events`` marker in a single DB transaction, then
        commit Kafka offsets once.
        """
        assert self._consumer is not None

        validated: list[tuple[uuid.UUID, Transactions, PaymentEvent]] = []

        for _tp, messages in batch.items():
            for msg in messages:
                try:
                    result = await self._validate_and_build(msg)
                except Exception:
                    continue

                if result is not None:
                    validated.append(result)

        if not validated:
            await self._consumer.commit()
            await self._logger.ainfo("Batch offsets committed (no valid events)")
            return

        async with self._session_factory() as session:
            async with session.begin():
                # Fetch already-processed event_ids from DB in one query
                candidate_ids = [event_id for event_id, _, _ in validated]
                existing_rows = await session.execute(
                    select(ProcessedEvents.event_id).where(
                        ProcessedEvents.event_id.in_(candidate_ids)
                    )
                )
                already_processed: set[uuid.UUID] = {row[0] for row in existing_rows}

                saved_count = 0
                skipped_count = 0

                for event_id, transaction, event in validated:
                    if event_id in already_processed:
                        await self._logger.ainfo(
                            "Duplicate event detected, skipping",
                            event_id=str(event_id),
                            payment_id=str(event.payment_id),
                        )
                        skipped_count += 1
                        continue

                    # Save transaction + processed_events marker together
                    session.add(transaction)
                    session.add(ProcessedEvents(event_id=event_id))
                    # Mark as processed within this batch to handle
                    # intra-batch duplicates
                    already_processed.add(event_id)
                    saved_count += 1

        await self._logger.ainfo(
            "Batch persisted to DB",
            saved_count=saved_count,
            skipped_count=skipped_count,
        )

        # Invalidate summary cache so API returns fresh data
        if saved_count > 0 and self._cache_service is not None:
            await self._cache_service.invalidate_cache(
                cache_prefix=SUMMARY_CACHE_PREFIX
            )

        # Commit Kafka offset
        await self._consumer.commit()

        await self._logger.ainfo(
            "Batch offsets committed",
            saved_count=saved_count,
            skipped_count=skipped_count,
        )

    async def _validate_and_build(
        self,
        msg: ConsumerRecord,
    ) -> tuple[uuid.UUID, Transactions, PaymentEvent] | None:
        """
        Validate a single Kafka message and return a tuple of
        ``(event_id, Transactions, PaymentEvent)`` ready for idempotency
        check and persistence.

        Returns ``None`` for invalid payloads (logged and skipped).
        Raises on unexpected errors so the caller can log and skip.
        """
        if msg.key is None:
            await self._logger.awarning(
                "Message has no key (event_id), skipping",
                raw_value=msg.value,
            )
            return None

        try:
            event_id = uuid.UUID(msg.key.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            await self._logger.awarning(
                "Invalid event_id in message key, skipping",
                raw_key=msg.key,
                error=str(exc),
            )
            return None

        try:
            event = PaymentEvent.model_validate(msg.value)
        except ValidationError as exc:
            await self._logger.awarning(
                "Invalid payment event payload, skipping",
                event_id=str(event_id),
                raw_value=msg.value,
                validation_errors=exc.errors(),
            )
            return None

        await self._logger.ainfo(
            "Received payment event",
            event_id=str(event_id),
            payment_id=str(event.payment_id),
            event_type=event.event_type,
            status=event.status,
        )

        # Build ORM object (not yet flushed)
        transaction = Transactions(
            payment_id=event.payment_id,
            amount=event.amount,
            currency=event.currency,
            status=PaymentStatusEnum(event.status),
            event_type=event.event_type,
            processed_at=event.timestamp,
        )

        return event_id, transaction, event
