import uuid
from unittest.mock import AsyncMock

import httpx

from app.common.exceptions import ItemNotFoundError
from tests.conftest import make_transaction_result


async def test_get_transaction_by_payment_id_ok(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """Existing payment_id should return 200 with transaction details."""
    pid = uuid.uuid4()
    txn = make_transaction_result(payment_id=pid)
    analytics_service_mock.get_transaction_by_payment_id.return_value = txn

    resp = await async_client.get(f"/api/v1/analytics/transactions/{pid}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["payment_id"] == str(pid)
    assert body["currency"] == txn.currency


async def test_get_transaction_not_found_returns_404(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """Missing payment_id should return 404."""
    pid = uuid.uuid4()
    analytics_service_mock.get_transaction_by_payment_id.side_effect = (
        ItemNotFoundError(message=f"Transaction with payment_id={pid} not found.")
    )

    resp = await async_client.get(f"/api/v1/analytics/transactions/{pid}")

    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"][0]["type"] == "ItemNotFoundError"


async def test_get_transaction_invalid_uuid_returns_422(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """A non-UUID payment_id should return 422."""
    resp = await async_client.get("/api/v1/analytics/transactions/not-a-uuid")

    assert resp.status_code == 422
