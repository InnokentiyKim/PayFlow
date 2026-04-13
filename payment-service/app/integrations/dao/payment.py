from uuid import UUID
from datetime import datetime, UTC

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.payments import Payment
from app.models.outbox_events import OutboxEvent
from app.schemas.event import PaymentEvent
from app.common import exceptions
from app.common.enums import PaymentStatusEnum


class PaymentDAO:
    @staticmethod
    async def get_payment_by_id(
        session: AsyncSession, payment_id: UUID
    ) -> Payment | None:
        query = select(Payment).filter_by(id=payment_id)
        row = await session.execute(query)
        return row.scalar_one_or_none()

    @staticmethod
    async def get_payment_by_idempotency_key(
        session: AsyncSession, idempotency_key: str
    ) -> Payment | None:
        stmt = select(Payment).where(Payment.idempotency_key == idempotency_key)
        row = await session.execute(stmt)
        return row.scalar_one_or_none()

    @staticmethod
    async def get_payments(
        session: AsyncSession, filter_by: dict | None = None
    ) -> list[Payment]:
        filters = filter_by or {}
        query = select(Payment).filter_by(**filters)
        rows = await session.execute(query)
        return list(rows.scalars())

    @staticmethod
    async def get_outbox_events(session: AsyncSession) -> list[OutboxEvent]:
        query = select(OutboxEvent)
        rows = await session.execute(query)
        return list(rows.scalars())

    @staticmethod
    async def add_payment(session: AsyncSession, payment: Payment) -> UUID:
        session.add(payment)
        try:
            await session.commit()
            return payment.id
        except IntegrityError as err:
            await session.rollback()
            raise exceptions.ItemAlreadyExistsError("Payment already exists") from err

    _OUTBOX_EVENT_TYPES: dict[PaymentStatusEnum, str] = {
        PaymentStatusEnum.COMPLETED: "payment.completed",
        PaymentStatusEnum.FAILED: "payment.failed",
    }

    @staticmethod
    async def update_payment_status(
        session: AsyncSession,
        payment: Payment,
        new_status: PaymentStatusEnum,
        failure_reason: str | None = None,
    ) -> None:
        try:
            now = datetime.now(UTC)
            payment.status = new_status
            payment.updated_at = now

            if new_status == PaymentStatusEnum.COMPLETED:
                payment.completed_at = now
            elif new_status == PaymentStatusEnum.FAILED:
                payment.failed_at = now
                payment.failure_reason = failure_reason

            event_type = PaymentDAO._OUTBOX_EVENT_TYPES.get(new_status)
            if event_type is not None:
                event = PaymentEvent(
                    event_type=event_type,
                    payment_id=payment.id,
                    amount=payment.amount,
                    currency=payment.currency,
                    status=new_status,
                    timestamp=now,
                    failure_reason=failure_reason,
                )

                outbox = OutboxEvent(
                    event_type=event_type,
                    payload=event.model_dump(mode="json"),
                )
                session.add(outbox)

            await session.commit()
        except SQLAlchemyError as err:
            await session.rollback()
            raise exceptions.DatabaseError(
                "Failed to update payment status",
            ) from err

    @staticmethod
    async def delete_payment(session: AsyncSession, payment: Payment) -> None:
        await session.delete(payment)
        try:
            await session.commit()
        except SQLAlchemyError as err:
            await session.rollback()
            raise exceptions.DatabaseError("Failed to delete payment") from err
