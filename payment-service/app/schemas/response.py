import uuid
from datetime import datetime
from decimal import Decimal

from app.common.dto import BaseResponseDTO
from app.common.enums import PaymentStatusEnum
from app.schemas.result import CreatePaymentResult, GetOutboxEventResult


class GetPaymentResponseDTO(BaseResponseDTO):
    id: uuid.UUID
    amount: Decimal
    currency: str
    status: PaymentStatusEnum
    description: str
    idempotency_key: str
    created_at: datetime
    updated_at: datetime


class CreatePaymentResponseDTO(BaseResponseDTO):
    id: uuid.UUID
    created_at: datetime
    status: PaymentStatusEnum
    idempotency_key: str

    @classmethod
    def from_model(cls, model: "CreatePaymentResult") -> "CreatePaymentResponseDTO":
        return cls(
            id=model.id,
            created_at=model.created_at,
            status=model.status,
            idempotency_key=model.idempotency_key,
        )


class GetOutboxEventResponseDTO(BaseResponseDTO):
    id: uuid.UUID
    event_type: str
    payload: dict
    created_at: datetime
    published: bool

    @classmethod
    def from_model(cls, model: "GetOutboxEventResult") -> "GetOutboxEventResponseDTO":
        return cls(
            id=model.id,
            event_type=model.event_type,
            payload=model.payload,
            created_at=model.created_at,
            published=model.published,
        )
