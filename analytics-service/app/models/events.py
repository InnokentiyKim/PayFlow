import uuid
from datetime import datetime, UTC
from sqlalchemy import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import MappedAsDataclass, Mapped, mapped_column

from app.common.model import Base


class ProcessedEventsBase(MappedAsDataclass, Base):
    """Base class for SQLAlchemy connector ORM models."""

    __abstract__ = True


class ProcessedEvents(ProcessedEventsBase):
    __tablename__ = "processed_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, primary_key=True
    )

    processed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )

    def __init__(
        self,
        event_id: uuid.UUID,
        processed_at: datetime | None = None,
    ):
        self.event_id = event_id
        self.processed_at = processed_at or datetime.now(UTC)

        super().__init__()
