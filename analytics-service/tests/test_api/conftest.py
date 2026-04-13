from contextlib import asynccontextmanager
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import httpx
import fakeredis.aioredis
from fastapi import FastAPI

from app.api.routers.common import http_router_v1
from app.api.routers.health import router as health_router
from app.common.exceptions import ExceptionBase
from app.core.config import Configs
from app.integrations.redis import RedisClient
from app.services.analytics import AnalyticsService, provide_analytics_service
from app.services.cache import CacheService, _get_cache_service
from app.setup.exception_handlers import general_exception_handler


@asynccontextmanager
async def _noop_lifespan(app: FastAPI) -> AsyncGenerator:
    """No-op lifespan – skips Kafka consumer, Redis, DB engine."""
    yield


def _create_test_app(
    service_mock: AsyncMock,
    cache_service: CacheService,
) -> FastAPI:
    app = FastAPI(lifespan=_noop_lifespan)
    app.add_exception_handler(ExceptionBase, general_exception_handler)
    app.include_router(health_router)
    app.include_router(http_router_v1)

    app.dependency_overrides[provide_analytics_service] = lambda: service_mock
    app.dependency_overrides[_get_cache_service] = lambda: cache_service
    return app


@pytest.fixture()
def analytics_service_mock() -> AsyncMock:
    """A fully-mocked AnalyticsService."""
    mock = AsyncMock(spec=AnalyticsService)
    # serialize_report / deserialize_report are used by the API cache layer,
    # so we wire them to the real (static) implementations.
    mock.serialize_report.side_effect = AnalyticsService.serialize_report
    mock.deserialize_report.side_effect = AnalyticsService.deserialize_report
    return mock


@pytest.fixture()
def fake_redis_client() -> RedisClient:
    """A RedisClient whose internal connection is backed by fakeredis."""
    client = RedisClient.__new__(RedisClient)
    client._client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return client


@pytest.fixture()
def cache_service(fake_redis_client: RedisClient) -> CacheService:
    config = Configs()
    return CacheService(redis_client=fake_redis_client, config=config)


@pytest.fixture()
def broken_redis_client() -> RedisClient:
    """A RedisClient where every operation raises ConnectionError."""
    from redis.asyncio import ConnectionError as RedisConnectionError

    client = RedisClient.__new__(RedisClient)
    mock = AsyncMock()
    mock.set.side_effect = RedisConnectionError("Connection refused")
    mock.get.side_effect = RedisConnectionError("Connection refused")
    mock.delete.side_effect = RedisConnectionError("Connection refused")
    mock.delete_by_pattern.side_effect = RedisConnectionError("Connection refused")
    mock.scan_iter.side_effect = RedisConnectionError("Connection refused")
    client._client = mock
    return client


@pytest.fixture()
def broken_cache_service(broken_redis_client: RedisClient) -> CacheService:
    config = Configs()
    return CacheService(redis_client=broken_redis_client, config=config)


@pytest.fixture()
async def async_client(
    analytics_service_mock: AsyncMock,
    cache_service: CacheService,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Client with a working (fakeredis-backed) cache."""
    app = _create_test_app(analytics_service_mock, cache_service)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture()
async def async_client_broken_cache(
    analytics_service_mock: AsyncMock,
    broken_cache_service: CacheService,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Client where Redis is unavailable — cache ops silently fail."""
    app = _create_test_app(analytics_service_mock, broken_cache_service)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
