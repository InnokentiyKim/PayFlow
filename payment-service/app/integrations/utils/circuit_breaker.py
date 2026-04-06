import time
from enum import StrEnum


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerException(Exception):
    def __init__(self, remaining_timeout: float) -> None:
        self.remaining_timeout = remaining_timeout
        super().__init__(
            f"Circuit breaker is OPEN. Retry after {remaining_timeout:.1f} seconds."
        )


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 30.0,
        success_threshold: int = 1,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._success_threshold = success_threshold

        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._last_failure_time: float = 0.0
        self._success_count: int = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._reset_timeout_elapsed():
            return CircuitState.HALF_OPEN
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def success_count(self) -> int:
        return self._success_count

    async def before_request(self) -> None:
        current = self.state

        if current == CircuitState.OPEN:
            remaining_time = self._reset_timeout - (
                time.monotonic() - self._last_failure_time
            )
            raise CircuitBreakerException(remaining_timeout=remaining_time)

    async def on_success(self) -> None:
        """Report a successful request to the circuit breaker."""
        current = self.state

        self._failure_count = 0
        self._success_count += 1

        if (
            current == CircuitState.HALF_OPEN
            and self._success_count >= self._success_threshold
        ):
            self._state = CircuitState.CLOSED

    async def on_failure(self) -> None:
        """Report a failed request to the circuit breaker."""
        self._success_count = 0
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN
            return

        if (
            self._state == CircuitState.CLOSED
            and self._failure_count >= self._failure_threshold
        ):
            self._state = CircuitState.OPEN

    def _reset_timeout_elapsed(self) -> bool:
        return (time.monotonic() - self._last_failure_time) >= self._reset_timeout
