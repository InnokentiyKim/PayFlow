import uuid
from datetime import datetime, UTC
from decimal import Decimal
from sqlalchemy import DECIMAL, TIMESTAMP, String, Enum as SAEnum, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import MappedAsDataclass, Mapped, mapped_column

from app.common.enums import PaymentStatusEnum
from app.common.model import Base


class TransactionsBase(MappedAsDataclass, Base):
    """Base class for SQLAlchemy connector ORM models."""

    __abstract__ = True


class Transactions(TransactionsBase):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_processed_at", "processed_at"),
        Index("ix_transactions_status_processed_at", "status", "processed_at"),
        Index("ix_transactions_currency_status", "currency", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, primary_key=True
    )
    payment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    amount: Mapped[Decimal] = mapped_column(DECIMAL(15, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[PaymentStatusEnum] = mapped_column(
        SAEnum(PaymentStatusEnum), nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(15), nullable=False)

    processed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
    )

    def __init__(
        self,
        payment_id: uuid.UUID,
        amount: Decimal,
        currency: str,
        status: PaymentStatusEnum,
        event_type: str,
        processed_at: datetime | None = None,
    ):
        self.id = uuid.uuid4()
        self.payment_id = payment_id
        self.amount = amount
        self.currency = currency
        self.status = status
        self.event_type = event_type
        self.processed_at = processed_at or datetime.now(UTC)

        super().__init__()
