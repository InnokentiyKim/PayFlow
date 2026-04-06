from uuid import UUID
from datetime import datetime, UTC

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.payments import Payment
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
    async def add_payment(session: AsyncSession, payment: Payment) -> UUID:
        session.add(payment)
        try:
            await session.commit()
            return payment.id
        except IntegrityError as err:
            raise exceptions.ItemAlreadyExistsError("Payment already exists") from err

    @staticmethod
    async def update_payment_status(
        session: AsyncSession,
        payment: Payment,
        new_status: PaymentStatusEnum,
        failure_reason: str | None = None,
    ) -> None:
        now = datetime.now(UTC)
        payment.status = new_status
        payment.updated_at = now

        if new_status == PaymentStatusEnum.COMPLETED:
            payment.completed_at = now
        elif new_status == PaymentStatusEnum.FAILED:
            payment.failed_at = now
            payment.failure_reason = failure_reason

        try:
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
            raise exceptions.DatabaseError("Failed to delete payment") from err
