from decimal import Decimal
from unittest.mock import AsyncMock

import httpx

from app.services.cache import CacheService
from tests.conftest import make_summary_report


def _setup_service_mock(mock: AsyncMock) -> None:
    """Configure the service mock to return a default summary report."""
    mock.get_summary.return_value = make_summary_report(
        total_transactions=3,
        total_amount=Decimal("300.0000"),
        average_amount=Decimal("100.0000"),
    )


async def test_first_call_misses_cache_and_queries_service(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """First request should miss the cache and call the service."""
    _setup_service_mock(analytics_service_mock)

    resp = await async_client.get("/api/v1/analytics/summary")

    assert resp.status_code == 200
    analytics_service_mock.get_summary.assert_awaited_once()


async def test_second_call_hits_cache(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """Second identical request should return from cache; service NOT called again."""
    _setup_service_mock(analytics_service_mock)

    resp1 = await async_client.get("/api/v1/analytics/summary")
    assert resp1.status_code == 200

    resp2 = await async_client.get("/api/v1/analytics/summary")
    assert resp2.status_code == 200

    # Service was only called once (first request)
    assert analytics_service_mock.get_summary.await_count == 1
    # deserialize_report was called for the cache HIT
    analytics_service_mock.deserialize_report.assert_called_once()


async def test_cache_hit_returns_same_data(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """Both responses (cache miss + cache hit) should contain the same payload."""
    _setup_service_mock(analytics_service_mock)

    resp1 = await async_client.get("/api/v1/analytics/summary")
    resp2 = await async_client.get("/api/v1/analytics/summary")

    body1 = resp1.json()
    body2 = resp2.json()
    assert body1["total_transactions"] == body2["total_transactions"]
    assert body1["total_amount"] == body2["total_amount"]


async def test_different_filters_do_not_share_cache(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """Requests with different query parameters must each hit the service."""
    _setup_service_mock(analytics_service_mock)

    await async_client.get("/api/v1/analytics/summary")
    await async_client.get("/api/v1/analytics/summary", params={"currency": "EUR"})

    assert analytics_service_mock.get_summary.await_count == 2


async def test_same_filters_share_cache(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """Two requests with the same filter should share the cache entry."""
    _setup_service_mock(analytics_service_mock)

    await async_client.get("/api/v1/analytics/summary", params={"currency": "USD"})
    await async_client.get("/api/v1/analytics/summary", params={"currency": "USD"})

    assert analytics_service_mock.get_summary.await_count == 1


async def test_invalidation_forces_fresh_service_call(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
    cache_service: CacheService,
) -> None:
    """After cache invalidation, the next request must call the service again."""
    _setup_service_mock(analytics_service_mock)

    # Populate cache
    await async_client.get("/api/v1/analytics/summary")
    assert analytics_service_mock.get_summary.await_count == 1

    # Invalidate
    await cache_service.invalidate_cache("analytics:summary")

    # Next call should go to the service
    await async_client.get("/api/v1/analytics/summary")
    assert analytics_service_mock.get_summary.await_count == 2


async def test_invalidation_affects_all_filter_variants(
    async_client: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
    cache_service: CacheService,
) -> None:
    """invalidate_cache should clear entries for ALL filter combinations."""
    _setup_service_mock(analytics_service_mock)

    # Populate caches for two different filter sets
    await async_client.get("/api/v1/analytics/summary")
    await async_client.get("/api/v1/analytics/summary", params={"currency": "EUR"})
    assert analytics_service_mock.get_summary.await_count == 2

    # Invalidate all summary caches
    await cache_service.invalidate_cache("analytics:summary")

    # Both should now miss
    await async_client.get("/api/v1/analytics/summary")
    await async_client.get("/api/v1/analytics/summary", params={"currency": "EUR"})
    assert analytics_service_mock.get_summary.await_count == 4


async def test_summary_works_when_redis_down(
    async_client_broken_cache: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """When Redis is unreachable, the endpoint must still return data from the service."""
    _setup_service_mock(analytics_service_mock)

    resp = await async_client_broken_cache.get("/api/v1/analytics/summary")

    assert resp.status_code == 200
    assert resp.json()["total_transactions"] == 3
    analytics_service_mock.get_summary.assert_awaited_once()


async def test_every_call_queries_service_when_redis_down(
    async_client_broken_cache: httpx.AsyncClient,
    analytics_service_mock: AsyncMock,
) -> None:
    """With Redis down, cache never works, so every request hits the service."""
    _setup_service_mock(analytics_service_mock)

    await async_client_broken_cache.get("/api/v1/analytics/summary")
    await async_client_broken_cache.get("/api/v1/analytics/summary")

    assert analytics_service_mock.get_summary.await_count == 2
