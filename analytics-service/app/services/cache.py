from typing import Any, TypeAlias, Annotated

import structlog
from fastapi import Depends
from redis.asyncio import ConnectionError, TimeoutError

from app.core.config import Configs
from app.integrations.redis import RedisClient

logger = structlog.get_logger(__name__)

SUMMARY_CACHE_PREFIX = "analytics:summary"


class CacheService:
    """Service for caching data using Redis with graceful degradation."""

    def __init__(
        self,
        redis_client: RedisClient,
        config: Configs,
    ):
        self._redis_client = redis_client
        self._redis_config = config.redis

    async def set_cache(self, key: str, value: str) -> None:
        """Set a value in the cache with TTL from config. Silently fails if Redis is down."""
        try:
            await self._redis_client.set(key, value, self._redis_config.TTL)
            await logger.ainfo("Cache set", key=key, ttl=self._redis_config.TTL)
        except (ConnectionError, TimeoutError, OSError) as e:
            await logger.awarning(
                "Redis unavailable on SET, skipping cache", key=key, error=str(e)
            )

    async def get_cache(self, key: str) -> str | None:
        """Get a value from the cache. Returns None on miss or if Redis is unavailable."""
        try:
            cache_value = await self._redis_client.get(key)
            if cache_value is not None:
                await logger.ainfo("Cache HIT", key=key)
                return cache_value
            await logger.ainfo("Cache MISS", key=key)
            return None
        except (ConnectionError, TimeoutError, OSError) as e:
            await logger.awarning(
                "Redis unavailable on GET, falling back to DB", key=key, error=str(e)
            )
            return None

    async def invalidate_by_key(self, key: str) -> None:
        """Delete a single key from the cache. Silently fails if Redis is down."""
        try:
            await self._redis_client.delete(key)
            await logger.ainfo("Cache invalidated", key=key)
        except (ConnectionError, TimeoutError, OSError) as e:
            await logger.awarning(
                "Redis unavailable on DELETE, skipping invalidation",
                key=key,
                error=str(e),
            )

    async def invalidate_cache(self, cache_prefix: str) -> None:
        """
        Invalidate ALL cache entries regardless of filter parameters.
        Called when new payment events are consumed so users never see stale data.
        """
        cache_prefix = cache_prefix.lower().strip()
        pattern = f"{cache_prefix}:*"
        try:
            deleted = await self._redis_client.delete_by_pattern(pattern)
            await logger.ainfo(
                "Cache invalidated", pattern=pattern, deleted_keys=deleted
            )
        except (ConnectionError, TimeoutError, OSError) as e:
            await logger.awarning(
                "Redis unavailable, skipping cache invalidation", error=str(e)
            )

    @staticmethod
    def build_cache_key(
        cache_prefix: str,
        **kwargs: Any,
    ) -> str:
        """Build a deterministic cache key for queries. Different filter combinations produce different keys."""
        parts = [value for value in kwargs.values() if value is not None]
        return f"{cache_prefix}:{'&'.join(parts)}"


def _get_cache_service() -> CacheService | None:
    """Create CacheService from app config. Returns None if Redis URL is not configured."""
    from app.core.config import app_config
    from app.integrations.redis import RedisClient

    redis_client = RedisClient(
        url=app_config.redis.redis_url,
        socket_timeout=app_config.redis.socket_timeout,
        socket_connect_timeout=app_config.redis.socket_connect_timeout,
    )
    return CacheService(redis_client=redis_client, config=app_config)


CacheServiceDependency: TypeAlias = Annotated[CacheService, Depends(_get_cache_service)]
