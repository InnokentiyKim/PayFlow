from uuid import UUID

from fastapi import APIRouter
from app.schemas.fetch import GetPaymentInfo
from app.schemas.response import GetPaymentResponseDTO, GetOutboxEventResponseDTO
from app.services.payment import PaymentServiceDependency

router = APIRouter(
    prefix="/outbox-events",
    tags=["outbox-events"],
)


@router.get("", response_model=list[GetOutboxEventResponseDTO])
async def get_events(
    service: PaymentServiceDependency,
) -> list[GetOutboxEventResponseDTO]:
    events = await service.get_outbox_events()
    return [GetOutboxEventResponseDTO.from_model(event) for event in events]
