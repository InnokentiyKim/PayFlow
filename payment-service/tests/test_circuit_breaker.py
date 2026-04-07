import time
from unittest.mock import patch

import pytest

from app.integrations.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerException,
    CircuitState,
)


@pytest.fixture()
def cb() -> CircuitBreaker:
    """Circuit breaker with small thresholds for fast tests."""
    return CircuitBreaker(
        failure_threshold=3,
        reset_timeout=10.0,
        success_threshold=2,
    )


class TestInitialState:
    async def test_initial_state_is_closed(self, cb: CircuitBreaker):
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0


class TestClosedToOpen:
    async def test_stays_closed_below_threshold(self, cb: CircuitBreaker):
        for _ in range(cb._failure_threshold - 1):
            await cb.on_failure()
        assert cb.state == CircuitState.CLOSED

    async def test_opens_on_threshold(self, cb: CircuitBreaker):
        for _ in range(cb._failure_threshold):
            await cb.on_failure()
        assert cb.state == CircuitState.OPEN

    async def test_open_rejects_requests(self, cb: CircuitBreaker):
        for _ in range(cb._failure_threshold):
            await cb.on_failure()

        with pytest.raises(CircuitBreakerException) as exc_info:
            await cb.before_request()

        assert exc_info.value.remaining_timeout > 0


class TestOpenToHalfOpen:
    async def test_half_open_after_timeout(self, cb: CircuitBreaker):
        for _ in range(cb._failure_threshold):
            await cb.on_failure()
        assert cb.state == CircuitState.OPEN

        # Simulate time passing beyond reset_timeout
        future = time.monotonic() + cb._reset_timeout + 1
        with patch(
            "app.integrations.utils.circuit_breaker.time.monotonic",
            return_value=future,
        ):
            assert cb.state == CircuitState.HALF_OPEN
            # before_request should NOT raise
            await cb.before_request()

    async def test_still_open_before_timeout(self, cb: CircuitBreaker):
        for _ in range(cb._failure_threshold):
            await cb.on_failure()

        # Time has NOT passed enough
        almost = time.monotonic() + cb._reset_timeout - 2
        with patch(
            "app.integrations.utils.circuit_breaker.time.monotonic",
            return_value=almost,
        ):
            assert cb.state == CircuitState.OPEN


class TestHalfOpenToClosed:
    async def test_success_in_half_open_closes(self, cb: CircuitBreaker):
        # Move to OPEN
        for _ in range(cb._failure_threshold):
            await cb.on_failure()

        # Move to HALF_OPEN by advancing time
        future = time.monotonic() + cb._reset_timeout + 1
        with patch(
            "app.integrations.utils.circuit_breaker.time.monotonic",
            return_value=future,
        ):
            assert cb.state == CircuitState.HALF_OPEN

            # Enough successes to close the circuit
            for _ in range(cb._success_threshold):
                await cb.on_success()

            assert cb.state == CircuitState.CLOSED
            assert cb.failure_count == 0


class TestHalfOpenToOpen:
    async def test_failure_in_half_open_reopens(self, cb: CircuitBreaker):
        # Move to OPEN
        for _ in range(cb._failure_threshold):
            await cb.on_failure()

        # Move to HALF_OPEN
        future = time.monotonic() + cb._reset_timeout + 1
        with patch(
            "app.integrations.utils.circuit_breaker.time.monotonic",
            return_value=future,
        ):
            assert cb.state == CircuitState.HALF_OPEN

            # A single failure should re-open
            await cb.on_failure()

        assert cb.state == CircuitState.OPEN


class TestOnSuccessResets:
    async def test_on_success_resets_failure_count(self, cb: CircuitBreaker):
        # Accumulate some failures (below threshold)
        await cb.on_failure()
        await cb.on_failure()
        assert cb.failure_count == 2

        await cb.on_success()
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED
