import asyncio
import uuid
from datetime import datetime, UTC
from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.common.model import Base
from app.core.config import Configs
from app.services.cache import CacheService
from consumer.payment_event_consumer import PaymentEventConsumer


@pytest.fixture()
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory SQLite async engine with all tables."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture()
def session_factory(async_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(async_engine, expire_on_commit=False)


@pytest.fixture()
def mock_cache_service() -> AsyncMock:
    return AsyncMock(spec=CacheService)


@pytest.fixture()
def config() -> Configs:
    return Configs()


@pytest.fixture()
def consumer(
    config: Configs,
    session_factory: async_sessionmaker[AsyncSession],
    mock_cache_service: AsyncMock,
) -> PaymentEventConsumer:
    """A PaymentEventConsumer with a real DB session factory and mocked cache."""
    pec = PaymentEventConsumer(
        config=config,
        session_factory=session_factory,
        cache_service=mock_cache_service,
        stop_event=asyncio.Event(),
    )
    # Replace the internal Kafka consumer with a mock
    pec._consumer = AsyncMock()
    return pec


def make_consumer_record(
    *,
    event_id: uuid.UUID | None = None,
    payment_id: uuid.UUID | None = None,
    amount: Decimal = Decimal("100.00"),
    currency: str = "USD",
    status: str = "completed",
    event_type: str = "payment.completed",
    timestamp: datetime | None = None,
    key: bytes | None = ...,  # sentinel
    value: dict | None = None,
) -> MagicMock:
    """Create a mock ConsumerRecord that mimics a Kafka message."""
    eid = event_id or uuid.uuid4()
    pid = payment_id or uuid.uuid4()
    ts = timestamp or datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)

    if key is ...:
        key = str(eid).encode("utf-8")

    if value is None:
        value = {
            "event_type": event_type,
            "payment_id": str(pid),
            "amount": str(amount),
            "currency": currency,
            "status": status,
            "timestamp": ts.isoformat(),
        }

    record = MagicMock()
    record.key = key
    record.value = value
    return record
