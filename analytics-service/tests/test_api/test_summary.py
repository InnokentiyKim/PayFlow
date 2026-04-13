from decimal import Decimal
from unittest.mock import AsyncMock

import httpx

from tests.conftest import make_summary_report
from app.schemas.results import StatusSummary, CurrencySummary


async def test_get_summary_returns_correct_aggregations(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """GET /summary should return correctly structured summary data."""
    report = make_summary_report(
        total_transactions=10,
        total_amount=Decimal("1500.0000"),
        average_amount=Decimal("150.0000"),
        by_status=[
            StatusSummary(
                status="completed", count=7, total_amount=Decimal("1200.0000")
            ),
            StatusSummary(status="failed", count=3, total_amount=Decimal("300.0000")),
        ],
        by_currency=[
            CurrencySummary(currency="USD", count=6, total_amount=Decimal("900.0000")),
            CurrencySummary(currency="EUR", count=4, total_amount=Decimal("600.0000")),
        ],
    )
    analytics_service_mock.get_summary.return_value = report

    resp = await async_client.get("/api/v1/analytics/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_transactions"] == 10
    assert Decimal(body["total_amount"]) == Decimal("1500.0000")
    assert Decimal(body["average_amount"]) == Decimal("150.0000")
    assert len(body["by_status"]) == 2
    assert len(body["by_currency"]) == 2
    assert body["by_status"][0]["status"] == "completed"
    assert body["by_currency"][0]["currency"] == "USD"


async def test_get_summary_with_filters(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """Query-string filters should be forwarded to the service."""
    analytics_service_mock.get_summary.return_value = make_summary_report()

    resp = await async_client.get(
        "/api/v1/analytics/summary",
        params={
            "date_from": "2025-01-01T00:00:00",
            "date_to": "2025-12-31T23:59:59",
            "currency": "EUR",
        },
    )

    assert resp.status_code == 200
    analytics_service_mock.get_summary.assert_awaited_once()
    fetch = analytics_service_mock.get_summary.call_args.kwargs["fetch"]
    assert fetch.currency == "EUR"
    assert fetch.date_from is not None
    assert fetch.date_to is not None


async def test_get_summary_empty_data(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """Summary with zero transactions should still return 200."""
    analytics_service_mock.get_summary.return_value = make_summary_report(
        total_transactions=0,
        total_amount=Decimal("0"),
        average_amount=Decimal("0"),
        by_status=[],
        by_currency=[],
    )

    resp = await async_client.get("/api/v1/analytics/summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_transactions"] == 0
    assert body["by_status"] == []
    assert body["by_currency"] == []
