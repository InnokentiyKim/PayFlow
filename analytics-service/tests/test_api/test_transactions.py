from unittest.mock import AsyncMock

import httpx

from tests.conftest import make_transaction_result


async def test_transactions_default_pagination(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """Default limit=20, offset=0 should be forwarded."""
    analytics_service_mock.get_transactions.return_value = [
        make_transaction_result() for _ in range(5)
    ]

    resp = await async_client.get("/api/v1/analytics/transactions")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 5

    fetch = analytics_service_mock.get_transactions.call_args.kwargs["fetch"]
    assert fetch.limit == 20
    assert fetch.offset == 0


async def test_transactions_custom_pagination(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """Custom limit/offset should be forwarded."""
    analytics_service_mock.get_transactions.return_value = [
        make_transaction_result() for _ in range(3)
    ]

    resp = await async_client.get(
        "/api/v1/analytics/transactions",
        params={"limit": 3, "offset": 10},
    )

    assert resp.status_code == 200
    assert len(resp.json()) == 3

    fetch = analytics_service_mock.get_transactions.call_args.kwargs["fetch"]
    assert fetch.limit == 3
    assert fetch.offset == 10


async def test_transactions_empty_list(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    analytics_service_mock.get_transactions.return_value = []

    resp = await async_client.get("/api/v1/analytics/transactions")

    assert resp.status_code == 200
    assert resp.json() == []


async def test_transactions_filter_by_status(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    analytics_service_mock.get_transactions.return_value = [
        make_transaction_result(status="failed")
    ]

    resp = await async_client.get(
        "/api/v1/analytics/transactions",
        params={"status": "failed"},
    )

    assert resp.status_code == 200
    fetch = analytics_service_mock.get_transactions.call_args.kwargs["fetch"]
    assert fetch.status == "failed"


async def test_transactions_filter_by_currency(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    analytics_service_mock.get_transactions.return_value = [
        make_transaction_result(currency="EUR")
    ]

    resp = await async_client.get(
        "/api/v1/analytics/transactions",
        params={"currency": "EUR"},
    )

    assert resp.status_code == 200
    fetch = analytics_service_mock.get_transactions.call_args.kwargs["fetch"]
    assert fetch.currency == "EUR"


async def test_transactions_filter_by_period(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    analytics_service_mock.get_transactions.return_value = []

    resp = await async_client.get(
        "/api/v1/analytics/transactions",
        params={
            "date_from": "2025-01-01T00:00:00",
            "date_to": "2025-06-30T23:59:59",
        },
    )

    assert resp.status_code == 200
    fetch = analytics_service_mock.get_transactions.call_args.kwargs["fetch"]
    assert fetch.date_from is not None
    assert fetch.date_to is not None
