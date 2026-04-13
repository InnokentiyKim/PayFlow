import redis.asyncio as redis
import structlog

logger = structlog.get_logger(__name__)


class RedisClient:
    """Simple Redis client wrapper for caching and other operations."""

    def __init__(
        self,
        url: str,
        socket_timeout: float = 0.5,
        socket_connect_timeout: float = 0.5,
        decode_responses: bool = True,
    ):
        self._client = redis.from_url(
            url,
            socket_timeout=socket_timeout,
            socket_connect_timeout=socket_connect_timeout,
            decode_responses=decode_responses,
        )

    async def set(self, key: str, value: str, expire_seconds: int | None = None):
        """Set a value in the cache with an optional expiration."""
        await self._client.set(key, value, ex=expire_seconds)

    async def get(self, key: str) -> str | None:
        """Get a value from the cache. Returns None if not found."""
        value = await self._client.get(key)
        return value if value is not None else None

    async def delete(self, key: str):
        """Delete a key from the cache."""
        await self._client.delete(key)

    async def delete_by_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern. Returns deleted count."""
        deleted = 0
        async for key in self._client.scan_iter(match=pattern):
            await self._client.delete(key)
            deleted += 1
        return deleted

    async def ping(self) -> bool:
        """Ping the Redis server. Returns True if reachable."""
        return await self._client.ping()  # type: ignore

    async def close(self):
        """Gracefully close the Redis connection."""
        await self._client.aclose()
