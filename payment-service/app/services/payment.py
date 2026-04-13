from typing import TypeAlias, Annotated
from uuid import UUID

from structlog import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.common import exceptions
from app.common.enums import PaymentStatusEnum
from app.core.config import app_config
from app.integrations.dao.payment import PaymentDAO
from app.integrations.database import provide_db_session
from app.integrations.payment import PaymentProviderClient
from app.models.payments import Payment
from app.schemas.fetch import GetPaymentInfo
from app.schemas.command import CreatePaymentCommand
from app.schemas import result


logger = get_logger(__name__)


class PaymentService:
    def __init__(
        self,
        session: AsyncSession,
        dao: PaymentDAO | None = None,
        provider: PaymentProviderClient | None = None,
    ):
        self._session = session
        self._dao = dao or PaymentDAO()
        self._provider = provider or PaymentProviderClient(
            base_url=app_config.provider.payment_provider_base_url,
            timeout=app_config.provider.payment_provider_timeout,
            max_retries=app_config.provider.payment_provider_max_retries,
            retry_delay=app_config.provider.payment_provider_retry_delay,
            cb_failure_threshold=app_config.provider.payment_provider_cb_failure_threshold,
            cb_recovery_timeout=app_config.provider.payment_provider_cb_recovery_timeout,
        )

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

    async def get_outbox_events(self) -> list[result.GetOutboxEventResult]:
        outbox_events = await self._dao.get_outbox_events(self._session)

        return [result.GetOutboxEventResult.from_model(outbox_event) for outbox_event in outbox_events]

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

    async def process_payment(self, payment_id: UUID) -> result.GetPaymentResult:
        """Call the payment provider and update the payment status in DB.

        Success → COMPLETED, any provider error → FAILED.
        """
        payment = await self._dao.get_payment_by_id(self._session, payment_id)
        if payment is None:
            raise exceptions.ItemNotFoundError(message="Payment not found")

        if payment.status != PaymentStatusEnum.PENDING:
            await logger.awarn(
                "Payment is not in PENDING status, skipping processing",
                payment_id=str(payment_id),
                current_status=payment.status,
            )
            return result.GetPaymentResult.from_model(payment)

        await logger.ainfo(
            "Processing payment via provider", payment_id=str(payment_id)
        )

        try:
            provider_result = await self._provider.process_payment(
                payment_id=str(payment_id),
                amount=payment.amount,
                currency=payment.currency,
            )

            await logger.ainfo(
                "Provider returned success",
                payment_id=str(payment_id),
                provider_tx_id=provider_result.provider_transaction_id,
                provider_status=provider_result.status,
            )

            await self._dao.update_payment_status(
                self._session, payment, PaymentStatusEnum.COMPLETED
            )

        except (
            exceptions.PaymentProviderError,
            exceptions.PaymentProviderUnavailableError,
            exceptions.PaymentProviderClientError,
        ) as exc:
            await logger.aerror(
                "Provider call failed, marking payment as FAILED",
                payment_id=str(payment_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )
            await self._dao.update_payment_status(
                self._session, payment, PaymentStatusEnum.FAILED,
                failure_reason=str(exc),
            )

        return result.GetPaymentResult.from_model(payment)


def provide_payment_service(
    session: AsyncSession = Depends(provide_db_session),
) -> PaymentService:
    return PaymentService(session=session)


PaymentServiceDependency: TypeAlias = Annotated[
    PaymentService, Depends(provide_payment_service)
]
