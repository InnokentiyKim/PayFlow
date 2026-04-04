from typing import TypeAlias, Annotated
from structlog import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.common import exceptions
from app.common.enums import PaymentStatusEnum
from app.integrations.dao.payment import PaymentDAO
from app.integrations.database import provide_db_session
from app.models.payments import Payment
from app.schemas.fetch import GetPaymentInfo
from app.schemas.command import CreatePaymentCommand
from app.schemas import result


logger = get_logger(__name__)


class PaymentService:
    def __init__(self, session: AsyncSession, dao: PaymentDAO | None = None):
        self._session = session
        self._dao = dao or PaymentDAO()

    async def get_payment(self, fetch: GetPaymentInfo) -> result.GetPaymentResult:
        payment = await self._dao.get_payment_by_id(self._session, fetch.payment_id)
        if payment is None:
            await logger.ainfo("Payment not found", payment_id=fetch.payment_id)
            raise exceptions.ItemNotFoundError(
                message="Payment not found",
            )

        return result.GetPaymentResult.from_model(payment)

    async def get_payments(self) -> list[result.GetPaymentResult]:
        payments = await self._dao.get_payments(self._session, filter_by={})

        return [result.GetPaymentResult.from_model(payment) for payment in payments]

    async def create_payment(
        self, cmd: CreatePaymentCommand
    ) -> result.CreatePaymentResult:
        existing_payment = await self._dao.get_payment_by_idempotency_key(
            self._session, cmd.idempotency_key
        )
        if existing_payment is not None:
            payment_result = result.CreatePaymentResult(
                id=existing_payment.id,
                created_at=existing_payment.created_at,
                idempotency_key=existing_payment.idempotency_key,
                status=existing_payment.status,
                is_exists=True,
            )
            return payment_result
        else:
            description = cmd.description if cmd.description else None
            payment = Payment(
                amount=cmd.amount,
                currency=cmd.currency,
                status=PaymentStatusEnum.PENDING,
                description=description,
                idempotency_key=cmd.idempotency_key,
            )

            try:
                payment_id = await self._dao.add_payment(self._session, payment)
                return result.CreatePaymentResult(
                    id=payment_id,
                    created_at=payment.created_at,
                    idempotency_key=cmd.idempotency_key,
                    status=payment.status,
                    is_exists=False,
                )
            except exceptions.ItemAlreadyExistsError:  # race condition case
                await logger.aerror(
                    "Payment creation failed", idempotency_key=cmd.idempotency_key
                )
                raise


def provide_payment_service(
    session: AsyncSession = Depends(provide_db_session),
) -> PaymentService:
    return PaymentService(session=session)


PaymentServiceDependency: TypeAlias = Annotated[
    PaymentService, Depends(provide_payment_service)
]
