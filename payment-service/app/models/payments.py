import uuid
from datetime import datetime, UTC
from decimal import Decimal
from sqlalchemy import DECIMAL, TIMESTAMP, String, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import MappedAsDataclass, Mapped, mapped_column

from app.common.model import Base
from app.common.enums import PaymentStatusEnum


class PaymentBase(MappedAsDataclass, Base):
    """Base class for SQLAlchemy connector ORM models."""

    __abstract__ = True


class Payment(PaymentBase):
    __tablename__ = "payments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, primary_key=True
    )
    amount: Mapped[Decimal] = mapped_column(DECIMAL(15, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[PaymentStatusEnum] = mapped_column(
        SAEnum(PaymentStatusEnum), nullable=False
    )
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )

    processing_started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    def __init__(
        self,
        amount: Decimal,
        currency: str,
        status: PaymentStatusEnum,
        description: str | None,
        idempotency_key: str,
    ):
        self.id = uuid.uuid4()
        self.amount = amount
        self.currency = currency
        self.status = status
        self.description = description
        self.idempotency_key = idempotency_key or self._generate_idempotency_key()

        now = datetime.now(UTC)
        self.created_at = now
        self.updated_at = now

        super().__init__()

    def _generate_idempotency_key(self) -> str:
        """Generate a unique idempotency key for payment processing."""
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        short_id = str(self.id)[:8]
        return f"PAY-{timestamp}-{short_id}"

    def is_successful(self) -> bool:
        """Check if the payment is successfully completed."""
        return self.status == PaymentStatusEnum.COMPLETED

    def is_failed(self) -> bool:
        """Check if the payment has failed."""
        return self.status == PaymentStatusEnum.FAILED

    def is_processing(self) -> bool:
        """Check if the payment is currently processing."""
        return self.status == PaymentStatusEnum.PROCESSING

    def is_pending(self) -> bool:
        """Check if the payment is pending."""
        return self.status == PaymentStatusEnum.PENDING
