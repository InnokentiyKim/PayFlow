import uuid
from datetime import datetime, UTC

from sqlalchemy.orm import MappedAsDataclass
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy import String, TIMESTAMP, Boolean

from app.common.model import Base


class OutboxEventBase(MappedAsDataclass, Base):
    """Base class for SQLAlchemy connector ORM models."""

    __abstract__ = True


class OutboxEvent(OutboxEventBase):
    __tablename__ = "outbox_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    published: Mapped[bool] = mapped_column(Boolean, default=False)

    def __init__(
        self,
        event_type: str,
        payload: dict,
        published: bool = False,
    ):
        self.id = uuid.uuid4()
        self.event_type = event_type
        self.payload = payload
        self.created_at = datetime.now(UTC)
        self.published = published

        super().__init__()

    def is_published(self):
        """Checks if the event has been published."""
        return self.published

    def mark_as_published(self):
        """Marks the event as published."""
        self.published = True
