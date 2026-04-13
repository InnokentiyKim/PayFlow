from app.services.cache import CacheService


async def test_set_and_get_cache(cache_service: CacheService) -> None:
    """A value written via set_cache should be readable via get_cache."""
    await cache_service.set_cache("test:key:1", '{"data": 42}')

    result = await cache_service.get_cache("test:key:1")

    assert result == '{"data": 42}'


async def test_get_cache_miss(cache_service: CacheService) -> None:
    """get_cache should return None for a non-existent key."""
    result = await cache_service.get_cache("test:nonexistent")

    assert result is None


async def test_invalidate_by_key(cache_service: CacheService) -> None:
    """invalidate_by_key should remove a single key."""
    await cache_service.set_cache("test:del:1", "v")
    await cache_service.invalidate_by_key("test:del:1")

    result = await cache_service.get_cache("test:del:1")
    assert result is None


async def test_invalidate_cache_by_prefix(cache_service: CacheService) -> None:
    """invalidate_cache should remove all keys matching the prefix pattern."""
    await cache_service.set_cache("analytics:summary:USD", "a")
    await cache_service.set_cache("analytics:summary:EUR", "b")
    await cache_service.set_cache("analytics:other:USD", "c")

    await cache_service.invalidate_cache("analytics:summary")

    assert await cache_service.get_cache("analytics:summary:USD") is None
    assert await cache_service.get_cache("analytics:summary:EUR") is None
    # Key with a different prefix should survive
    assert await cache_service.get_cache("analytics:other:USD") == "c"


async def test_get_cache_returns_none_when_redis_down(
    broken_cache_service: CacheService,
) -> None:
    """When Redis is unreachable, get_cache should silently return None."""
    result = await broken_cache_service.get_cache("any:key")

    assert result is None


async def test_set_cache_does_not_raise_when_redis_down(
    broken_cache_service: CacheService,
) -> None:
    """When Redis is unreachable, set_cache should not raise."""
    # Should NOT raise
    await broken_cache_service.set_cache("any:key", "value")


def test_build_cache_key_with_all_params() -> None:
    key = CacheService.build_cache_key(
        cache_prefix="analytics:summary",
        date_from="2025-01-01",
        date_to="2025-12-31",
        currency="USD",
    )
    assert key == "analytics:summary:2025-01-01&2025-12-31&USD"


def test_build_cache_key_with_none_params() -> None:
    key = CacheService.build_cache_key(
        cache_prefix="analytics:summary",
        date_from=None,
        date_to=None,
        currency="EUR",
    )
    assert key == "analytics:summary:EUR"


def test_build_cache_key_no_params() -> None:
    key = CacheService.build_cache_key(
        cache_prefix="analytics:summary",
        date_from=None,
        date_to=None,
        currency=None,
    )
    assert key == "analytics:summary:"
