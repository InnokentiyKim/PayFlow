import asyncio
import json

import structlog
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import app_config
from app.models.outbox_events import OutboxEvent

logger = structlog.get_logger(__name__)


class OutboxRelay:
    """Reads unpublished outbox events and publishes them to Kafka."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        bootstrap_servers: str = app_config.broker.kafka_bootstrap_servers,
        topic: str = app_config.broker.kafka_topic_payment_events,
        poll_interval: float = app_config.broker.outbox_relay_poll_interval,
        batch_size: int = app_config.broker.outbox_relay_batch_size,
    ) -> None:
        self._session_factory = session_factory
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        self._poll_interval = poll_interval
        self._batch_size = batch_size

        self._producer: AIOKafkaProducer | None = None
        self._running = False

    async def start(self) -> None:
        """Initialise the Kafka producer and begin the poll loop."""
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            acks=app_config.broker.kafka_acks,
            enable_idempotence=app_config.broker.kafka_enable_idempotence,
            retry_backoff_ms=500,
            request_timeout_ms=30_000,
        )
        await self._producer.start()
        self._running = True
        await logger.ainfo(
            "Outbox relay started",
            bootstrap_servers=self._bootstrap_servers,
            topic=self._topic,
            poll_interval=self._poll_interval,
        )

        await self._poll_loop()

    async def stop(self) -> None:
        """Signal the relay to stop and close the Kafka producer."""
        self._running = False
        if self._producer:
            await self._producer.stop()
            self._producer = None
        await logger.ainfo("Outbox relay stopped")

    async def _poll_loop(self) -> None:
        """Continuously poll for unpublished events until stop() is called."""
        while self._running:
            try:
                published_count = await self._publish_pending()
                if published_count:
                    await logger.ainfo(
                        "Outbox relay cycle completed",
                        published_count=published_count,
                    )
            except Exception as exc:
                await logger.aerror(
                    "Outbox relay poll error",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )

            await asyncio.sleep(self._poll_interval)

    async def _publish_pending(self) -> int:
        """Fetch unpublished outbox rows, send to Kafka, mark published.

        Returns:
            Number of events successfully published in this cycle.
        """
        published = 0
        async with self._session_factory() as session:
            result = await session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.published == False)  # noqa: E712
                .order_by(OutboxEvent.created_at)
                .limit(self._batch_size)
            )
            events: list[OutboxEvent] = list(result.scalars().all())

            if not events:
                return 0

            for event in events:
                try:
                    payload_bytes = json.dumps(event.payload).encode("utf-8")
                    key_bytes = str(
                        event.payload.get("payment_id", str(event.id))
                    ).encode("utf-8")

                    await self._producer.send_and_wait(  # type: ignore[union-attr]
                        topic=self._topic,
                        value=payload_bytes,
                        key=key_bytes,
                    )

                    event.mark_as_published()
                    await session.commit()
                    published += 1

                    await logger.ainfo(
                        "Outbox event published to Kafka",
                        event_id=str(event.id),
                        event_type=event.event_type,
                        topic=self._topic,
                        payment_id=event.payload.get("payment_id"),
                    )

                except KafkaError as exc:
                    await session.rollback()
                    await logger.aerror(
                        "Failed to publish outbox event to Kafka",
                        event_id=str(event.id),
                        error=str(exc),
                    )
                    break

        return published
