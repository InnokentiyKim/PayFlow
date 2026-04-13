import pytest
from unittest.mock import AsyncMock

import fakeredis.aioredis

from app.core.config import Configs
from app.integrations.redis import RedisClient
from app.services.cache import CacheService


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
