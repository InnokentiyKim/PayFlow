import json
from typing import TypeAlias, Annotated
from uuid import UUID

from structlog import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

from app.schemas import fetch as fetches
from app.schemas.results import (
    SummaryReport,
    StatusSummary,
    CurrencySummary,
    TransactionResult,
)
from app.common.exceptions import ItemNotFoundError
from app.integrations.dao.analytics import AnalyticsDAO
from app.integrations.database import provide_db_session


logger = get_logger(__name__)

SUMMARY_CACHE_PREFIX = "analytics:summary"


class AnalyticsService:
    def __init__(
        self,
        session: AsyncSession,
    ):
        self._session = session

    async def get_summary(self, fetch: fetches.GetAnalyticsSummary) -> SummaryReport:
        data = await AnalyticsDAO.get_summary(
            self._session,
            date_from=fetch.date_from,
            date_to=fetch.date_to,
            currency=fetch.currency,
        )

        report = SummaryReport(
            total_transactions=data["total_transactions"],
            total_amount=data["total_amount"],
            average_amount=data["average_amount"],
            by_status=[
                StatusSummary(
                    status=s["status"], count=s["count"], total_amount=s["total_amount"]
                )
                for s in data["by_status"]
            ],
            by_currency=[
                CurrencySummary(
                    currency=c["currency"],
                    count=c["count"],
                    total_amount=c["total_amount"],
                )
                for c in data["by_currency"]
            ],
            date_from=fetch.date_from,
            date_to=fetch.date_to,
        )

        return report

    async def get_transactions(
        self, fetch: fetches.GetTransactions
    ) -> list[TransactionResult]:
        rows = await AnalyticsDAO.get_transactions(
            self._session,
            date_from=fetch.date_from,
            date_to=fetch.date_to,
            currency=fetch.currency,
            status=fetch.status,
            limit=fetch.limit,
            offset=fetch.offset,
        )

        return [TransactionResult.from_model(row) for row in rows]

    async def get_transaction_by_payment_id(
        self,
        payment_id: UUID,
    ) -> TransactionResult:
        row = await AnalyticsDAO.get_transaction_by_payment_id(
            self._session,
            payment_id,
        )
        if row is None:
            raise ItemNotFoundError(
                message=f"Transaction with payment_id={payment_id} not found.",
            )

        return TransactionResult.from_model(row)

    @staticmethod
    def serialize_report(report: SummaryReport) -> str:
        """Serialize SummaryReport to JSON string for caching."""
        from decimal import Decimal

        def _default(obj):
            if isinstance(obj, Decimal):
                return str(obj)
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        import dataclasses

        return json.dumps(dataclasses.asdict(report), default=_default)

    @staticmethod
    def deserialize_report(raw: str) -> SummaryReport:
        """Deserialize a JSON string back into a SummaryReport."""
        from decimal import Decimal
        from datetime import datetime

        data = json.loads(raw)
        return SummaryReport(
            total_transactions=data["total_transactions"],
            total_amount=Decimal(data["total_amount"]),
            average_amount=Decimal(data["average_amount"]),
            by_status=[
                StatusSummary(
                    status=s["status"],
                    count=s["count"],
                    total_amount=Decimal(s["total_amount"]),
                )
                for s in data["by_status"]
            ],
            by_currency=[
                CurrencySummary(
                    currency=c["currency"],
                    count=c["count"],
                    total_amount=Decimal(c["total_amount"]),
                )
                for c in data["by_currency"]
            ],
            date_from=datetime.fromisoformat(data["date_from"])
            if data.get("date_from")
            else None,
            date_to=datetime.fromisoformat(data["date_to"])
            if data.get("date_to")
            else None,
        )


def provide_analytics_service(
    session: AsyncSession = Depends(provide_db_session),
) -> AnalyticsService:
    return AnalyticsService(session=session)


AnalyticsServiceDependency: TypeAlias = Annotated[
    AnalyticsService, Depends(provide_analytics_service)
]
