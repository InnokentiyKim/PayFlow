import uuid
from datetime import datetime, UTC
from decimal import Decimal
from typing import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.common.enums import PaymentStatusEnum
from app.common.model import Base
from app.models.transactions import Transactions


@pytest.fixture()
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """In-memory SQLite engine with all tables created."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture()
async def session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """A fresh async session for each test, rolled back on teardown."""
    async with async_sessionmaker(async_engine, expire_on_commit=False)() as sess:
        yield sess


def make_transaction(
    *,
    payment_id: uuid.UUID | None = None,
    amount: Decimal = Decimal("100.0000"),
    currency: str = "USD",
    status: PaymentStatusEnum = PaymentStatusEnum.COMPLETED,
    event_type: str = "payment.completed",
    processed_at: datetime | None = None,
) -> Transactions:
    """Factory helper to create a Transactions ORM instance."""
    return Transactions(
        payment_id=payment_id or uuid.uuid4(),
        amount=amount,
        currency=currency,
        status=status,
        event_type=event_type,
        processed_at=processed_at or datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC),
    )


async def seed_transactions(
    session: AsyncSession,
    transactions: list[Transactions],
) -> None:
    """Persist a list of transactions into the test database."""
    async with session.begin():
        for txn in transactions:
            session.add(txn)
