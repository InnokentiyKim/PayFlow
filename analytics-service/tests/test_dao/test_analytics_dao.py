import uuid
from datetime import datetime, UTC
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enums import PaymentStatusEnum
from app.integrations.dao.analytics import AnalyticsDAO
from tests.test_dao.conftest import make_transaction, seed_transactions


class TestGetSummaryEmpty:
    """Summary queries on an empty database."""

    async def test_empty_db_returns_zeros(self, session: AsyncSession) -> None:
        result = await AnalyticsDAO.get_summary(session)

        assert result["total_transactions"] == 0
        assert result["total_amount"] == 0
        assert result["average_amount"] == 0
        assert result["by_status"] == []
        assert result["by_currency"] == []


class TestGetSummaryBasic:
    """Summary queries with seeded data."""

    async def test_total_transactions_and_amounts(self, session: AsyncSession) -> None:
        txns = [
            make_transaction(amount=Decimal("100.0000")),
            make_transaction(amount=Decimal("200.0000")),
            make_transaction(amount=Decimal("300.0000")),
        ]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_summary(session)

        assert result["total_transactions"] == 3
        assert Decimal(str(result["total_amount"])) == Decimal("600.0000")
        assert Decimal(str(result["average_amount"])) == Decimal("200.0000")

    async def test_by_status_breakdown(self, session: AsyncSession) -> None:
        txns = [
            make_transaction(status=PaymentStatusEnum.COMPLETED, amount=Decimal("100")),
            make_transaction(status=PaymentStatusEnum.COMPLETED, amount=Decimal("200")),
            make_transaction(status=PaymentStatusEnum.FAILED, amount=Decimal("50")),
        ]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_summary(session)

        by_status = {r["status"]: r for r in result["by_status"]}
        assert len(by_status) == 2

        completed = by_status[PaymentStatusEnum.COMPLETED]
        assert completed["count"] == 2
        assert Decimal(str(completed["total_amount"])) == Decimal("300")

        failed = by_status[PaymentStatusEnum.FAILED]
        assert failed["count"] == 1
        assert Decimal(str(failed["total_amount"])) == Decimal("50")

    async def test_by_currency_breakdown(self, session: AsyncSession) -> None:
        txns = [
            make_transaction(currency="USD", amount=Decimal("100")),
            make_transaction(currency="USD", amount=Decimal("200")),
            make_transaction(currency="EUR", amount=Decimal("50")),
        ]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_summary(session)

        by_currency = {r["currency"]: r for r in result["by_currency"]}
        assert len(by_currency) == 2
        assert by_currency["USD"]["count"] == 2
        assert by_currency["EUR"]["count"] == 1


class TestGetSummaryFilters:
    """Summary queries with date/currency filters."""

    async def test_filter_by_currency(self, session: AsyncSession) -> None:
        txns = [
            make_transaction(currency="USD", amount=Decimal("100")),
            make_transaction(currency="EUR", amount=Decimal("200")),
        ]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_summary(session, currency="EUR")

        assert result["total_transactions"] == 1
        assert Decimal(str(result["total_amount"])) == Decimal("200")

    async def test_filter_by_date_from(self, session: AsyncSession) -> None:
        txns = [
            make_transaction(
                processed_at=datetime(2025, 1, 1, tzinfo=UTC),
                amount=Decimal("100"),
            ),
            make_transaction(
                processed_at=datetime(2025, 6, 1, tzinfo=UTC),
                amount=Decimal("200"),
            ),
        ]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_summary(
            session,
            date_from=datetime(2025, 3, 1, tzinfo=UTC),
        )

        assert result["total_transactions"] == 1
        assert Decimal(str(result["total_amount"])) == Decimal("200")

    async def test_filter_by_date_to(self, session: AsyncSession) -> None:
        txns = [
            make_transaction(
                processed_at=datetime(2025, 1, 1, tzinfo=UTC),
                amount=Decimal("100"),
            ),
            make_transaction(
                processed_at=datetime(2025, 6, 1, tzinfo=UTC),
                amount=Decimal("200"),
            ),
        ]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_summary(
            session,
            date_to=datetime(2025, 3, 1, tzinfo=UTC),
        )

        assert result["total_transactions"] == 1
        assert Decimal(str(result["total_amount"])) == Decimal("100")

    async def test_filter_by_date_range(self, session: AsyncSession) -> None:
        txns = [
            make_transaction(
                processed_at=datetime(2025, 1, 1, tzinfo=UTC),
                amount=Decimal("10"),
            ),
            make_transaction(
                processed_at=datetime(2025, 3, 15, tzinfo=UTC),
                amount=Decimal("20"),
            ),
            make_transaction(
                processed_at=datetime(2025, 6, 1, tzinfo=UTC),
                amount=Decimal("30"),
            ),
        ]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_summary(
            session,
            date_from=datetime(2025, 2, 1, tzinfo=UTC),
            date_to=datetime(2025, 5, 1, tzinfo=UTC),
        )

        assert result["total_transactions"] == 1
        assert Decimal(str(result["total_amount"])) == Decimal("20")

    async def test_filter_returns_nothing(self, session: AsyncSession) -> None:
        txns = [make_transaction(currency="USD")]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_summary(session, currency="RUB")

        assert result["total_transactions"] == 0
        assert result["by_status"] == []
        assert result["by_currency"] == []


class TestGetTransactionsEmpty:
    async def test_empty_db(self, session: AsyncSession) -> None:
        result = await AnalyticsDAO.get_transactions(session)
        assert result == []


class TestGetTransactionsPagination:
    async def test_default_limit(self, session: AsyncSession) -> None:
        txns = [make_transaction() for _ in range(25)]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_transactions(session)
        assert len(result) == 20  # default limit

    async def test_custom_limit(self, session: AsyncSession) -> None:
        txns = [make_transaction() for _ in range(10)]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_transactions(session, limit=3)
        assert len(result) == 3

    async def test_offset(self, session: AsyncSession) -> None:
        txns = [make_transaction() for _ in range(5)]
        await seed_transactions(session, txns)

        all_results = await AnalyticsDAO.get_transactions(session, limit=100)
        offset_results = await AnalyticsDAO.get_transactions(
            session, offset=2, limit=100
        )
        assert len(offset_results) == 3
        assert offset_results[0].id == all_results[2].id


class TestGetTransactionsOrdering:
    async def test_ordered_by_processed_at_desc(self, session: AsyncSession) -> None:
        txns = [
            make_transaction(processed_at=datetime(2025, 1, 1, tzinfo=UTC)),
            make_transaction(processed_at=datetime(2025, 6, 1, tzinfo=UTC)),
            make_transaction(processed_at=datetime(2025, 3, 1, tzinfo=UTC)),
        ]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_transactions(session)
        dates = [r.processed_at for r in result]
        assert dates == sorted(dates, reverse=True)


class TestGetTransactionsFilters:
    async def test_filter_by_status(self, session: AsyncSession) -> None:
        txns = [
            make_transaction(status=PaymentStatusEnum.COMPLETED),
            make_transaction(status=PaymentStatusEnum.COMPLETED),
            make_transaction(status=PaymentStatusEnum.FAILED),
        ]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_transactions(
            session, status=PaymentStatusEnum.FAILED
        )
        assert len(result) == 1
        assert result[0].status == PaymentStatusEnum.FAILED

    async def test_filter_by_currency(self, session: AsyncSession) -> None:
        txns = [
            make_transaction(currency="USD"),
            make_transaction(currency="EUR"),
        ]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_transactions(session, currency="EUR")
        assert len(result) == 1
        assert result[0].currency == "EUR"

    async def test_filter_by_date_range(self, session: AsyncSession) -> None:
        txns = [
            make_transaction(processed_at=datetime(2025, 1, 1, tzinfo=UTC)),
            make_transaction(processed_at=datetime(2025, 3, 15, tzinfo=UTC)),
            make_transaction(processed_at=datetime(2025, 6, 1, tzinfo=UTC)),
        ]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_transactions(
            session,
            date_from=datetime(2025, 2, 1, tzinfo=UTC),
            date_to=datetime(2025, 5, 1, tzinfo=UTC),
        )
        assert len(result) == 1

    async def test_combined_filters(self, session: AsyncSession) -> None:
        txns = [
            make_transaction(
                currency="USD",
                status=PaymentStatusEnum.COMPLETED,
                processed_at=datetime(2025, 3, 1, tzinfo=UTC),
            ),
            make_transaction(
                currency="USD",
                status=PaymentStatusEnum.FAILED,
                processed_at=datetime(2025, 3, 1, tzinfo=UTC),
            ),
            make_transaction(
                currency="EUR",
                status=PaymentStatusEnum.COMPLETED,
                processed_at=datetime(2025, 3, 1, tzinfo=UTC),
            ),
        ]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_transactions(
            session,
            currency="USD",
            status=PaymentStatusEnum.COMPLETED,
        )
        assert len(result) == 1
        assert result[0].currency == "USD"
        assert result[0].status == PaymentStatusEnum.COMPLETED


class TestGetTransactionByPaymentId:
    async def test_found(self, session: AsyncSession) -> None:
        pid = uuid.uuid4()
        txn = make_transaction(payment_id=pid)
        await seed_transactions(session, [txn])

        result = await AnalyticsDAO.get_transaction_by_payment_id(session, pid)

        assert result is not None
        assert result.payment_id == pid

    async def test_not_found(self, session: AsyncSession) -> None:
        result = await AnalyticsDAO.get_transaction_by_payment_id(session, uuid.uuid4())
        assert result is None

    async def test_returns_correct_one_among_many(self, session: AsyncSession) -> None:
        target_pid = uuid.uuid4()
        txns = [
            make_transaction(),
            make_transaction(payment_id=target_pid, amount=Decimal("999")),
            make_transaction(),
        ]
        await seed_transactions(session, txns)

        result = await AnalyticsDAO.get_transaction_by_payment_id(session, target_pid)

        assert result is not None
        assert result.payment_id == target_pid
        assert result.amount == Decimal("999")
