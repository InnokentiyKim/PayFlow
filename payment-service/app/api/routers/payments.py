from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import Response

from app.schemas.command import CreatePaymentCommand
from app.schemas.fetch import GetPaymentInfo
from app.schemas.request import PaymentCreateRequestDTO
from app.schemas.response import GetPaymentResponseDTO, CreatePaymentResponseDTO
from app.services.payment import PaymentServiceDependency

router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)


@router.get("/{payment_id}", response_model=GetPaymentResponseDTO)
async def get_payment(
    payment_id: UUID, service: PaymentServiceDependency
) -> GetPaymentResponseDTO:
    payment = await service.get_payment(fetch=GetPaymentInfo(payment_id=payment_id))
    return GetPaymentResponseDTO.model_validate(payment)


@router.post("", response_model=CreatePaymentResponseDTO)
async def create_payment(
    dto: PaymentCreateRequestDTO, service: PaymentServiceDependency
):
    payment = await service.create_payment(
        cmd=CreatePaymentCommand(
            amount=dto.amount,
            currency=dto.currency,
            description=dto.description,
            idempotency_key=dto.idempotency_key,
        )
    )

    if payment.is_exists:
        status_code = status.HTTP_200_OK
    else:
        status_code = status.HTTP_201_CREATED

    return Response(
        status_code=status_code,
        content=CreatePaymentResponseDTO.from_model(model=payment).model_dump_json(),
        media_type="application/json",
    )
