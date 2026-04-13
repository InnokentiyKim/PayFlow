from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import PaymentStatusEnum
from app.models.transactions import Transactions


class AnalyticsDAO:
    """Data-access layer for analytics queries on the transactions table."""

    @staticmethod
    def _apply_filters(
        stmt,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        currency: str | None = None,
        status: PaymentStatusEnum | None = None,
    ):
        """Apply common WHERE filters to a SELECT statement."""
        if date_from is not None:
            stmt = stmt.where(Transactions.processed_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Transactions.processed_at <= date_to)
        if currency is not None:
            stmt = stmt.where(Transactions.currency == currency)
        if status is not None:
            stmt = stmt.where(Transactions.status == status)
        return stmt

    @staticmethod
    async def get_summary(
        session: AsyncSession,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        currency: str | None = None,
    ) -> dict:
        """
        Return aggregated summary:
        total_transactions, total_amount, average_amount,
        by_status breakdown, by_currency breakdown.
        """

        base = select(Transactions)
        base = AnalyticsDAO._apply_filters(
            base,
            date_from=date_from,
            date_to=date_to,
            currency=currency,
        )

        totals_stmt = select(
            func.count().label("total_transactions"),
            func.coalesce(func.sum(Transactions.amount), Decimal(0)).label(
                "total_amount"
            ),
            func.coalesce(func.avg(Transactions.amount), Decimal(0)).label(
                "average_amount"
            ),
        ).select_from(Transactions)
        totals_stmt = AnalyticsDAO._apply_filters(
            totals_stmt,
            date_from=date_from,
            date_to=date_to,
            currency=currency,
        )
        totals_row = (await session.execute(totals_stmt)).one()

        status_stmt = (
            select(
                Transactions.status.label("status"),
                func.count().label("count"),
                func.coalesce(func.sum(Transactions.amount), Decimal(0)).label(
                    "total_amount"
                ),
            )
            .select_from(Transactions)
            .group_by(Transactions.status)
        )
        status_stmt = AnalyticsDAO._apply_filters(
            status_stmt,
            date_from=date_from,
            date_to=date_to,
            currency=currency,
        )
        status_rows = (await session.execute(status_stmt)).all()

        currency_stmt = (
            select(
                Transactions.currency.label("currency"),
                func.count().label("count"),
                func.coalesce(func.sum(Transactions.amount), Decimal(0)).label(
                    "total_amount"
                ),
            )
            .select_from(Transactions)
            .group_by(Transactions.currency)
        )
        currency_stmt = AnalyticsDAO._apply_filters(
            currency_stmt,
            date_from=date_from,
            date_to=date_to,
            currency=currency,
        )
        currency_rows = (await session.execute(currency_stmt)).all()

        return {
            "total_transactions": totals_row.total_transactions,
            "total_amount": totals_row.total_amount,
            "average_amount": totals_row.average_amount,
            "by_status": [
                {"status": r.status, "count": r.count, "total_amount": r.total_amount}
                for r in status_rows
            ],
            "by_currency": [
                {
                    "currency": r.currency,
                    "count": r.count,
                    "total_amount": r.total_amount,
                }
                for r in currency_rows
            ],
        }

    @staticmethod
    async def get_transactions(
        session: AsyncSession,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        currency: str | None = None,
        status: PaymentStatusEnum | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Transactions]:
        """Return a paginated list of transactions with optional filters."""
        stmt = (
            select(Transactions)
            .order_by(Transactions.processed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        stmt = AnalyticsDAO._apply_filters(
            stmt,
            date_from=date_from,
            date_to=date_to,
            currency=currency,
            status=status,
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_transaction_by_payment_id(
        session: AsyncSession,
        payment_id: UUID,
    ) -> Transactions | None:
        """Return a single transaction by its payment_id, or None."""
        stmt = select(Transactions).where(Transactions.payment_id == payment_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
