from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx
import structlog
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.common.exceptions import (
    PaymentProviderClientError,
    PaymentProviderError,
    PaymentProviderUnavailableError,
    PaymentProcessingError,
)
from app.integrations.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerException,
)

logger = structlog.get_logger(__name__)


def _log_retry(retry_state: RetryCallState) -> None:
    """Structlog-compatible before_sleep callback for tenacity."""
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    structlog.get_logger(__name__).warning(
        "Retrying provider request",
        attempt=retry_state.attempt_number,
        wait=f"{retry_state.next_action.sleep:.2f}s"
        if retry_state.next_action
        else None,  # type: ignore[union-attr]
        error=str(exception) if exception else None,
        error_type=type(exception).__name__ if exception else None,
    )


@dataclass(slots=True, frozen=True)
class ProviderPaymentResult:
    """Parsed response from the payment provider mock."""

    provider_transaction_id: str
    status: str
    raw: dict[str, Any]


class PaymentProviderClient:
    def __init__(
        self,
        base_url: str = "http://payment-provider:8001",
        timeout: float = 5.0,
        max_retries: int = 3,
        retry_delay: float = 0.5,
        cb_failure_threshold: int = 5,
        cb_recovery_timeout: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay

        self._circuit_breaker = CircuitBreaker(
            failure_threshold=cb_failure_threshold,
            reset_timeout=cb_recovery_timeout,
        )

        self._do_request = retry(  # type: ignore
            retry=retry_if_exception_type(
                (
                    PaymentProviderError,
                    PaymentProviderUnavailableError,
                    PaymentProcessingError,
                ),
            ),
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential_jitter(
                initial=self._retry_delay,
                max=self._retry_delay * (2**self._max_retries),
                jitter=self._retry_delay,
            ),
            before_sleep=_log_retry,
            reraise=True,
        )(self._do_request)

    async def process_payment(
        self,
        payment_id: str,
        amount: Decimal,
        currency: str,
        url: str | None = None,
    ) -> ProviderPaymentResult:
        """Send a payment request to the provider with retry + circuit breaker.

        Args:
            payment_id (str): Unique identifier for the payment.
            amount (Decimal): Payment amount.
            currency (str): Currency code (e.g. "USD").
            url (str | None): Optional provider endpoint URL (for testing).

        Returns:
            ProviderPaymentResult: Parsed result from the provider response.

        Raises
        ------
        PaymentProviderClientError
            On 4xx (client) errors — not retried.
        PaymentProviderUnavailableError
            When retries are exhausted, or the circuit breaker is open.
        PaymentProviderError
            On other unexpected provider errors.
        """
        url = url or f"{self._base_url}/process-payment"
        payload: dict[str, Any] = {
            "payment_id": payment_id,
            "amount": str(amount),
            "currency": currency,
        }

        try:
            # noinspection PyArgumentList
            return await self._do_request(
                method="POST",
                url=url,
                json_payload=payload,
            )
        except CircuitBreakerException as exc:
            raise PaymentProviderUnavailableError(
                message=f"Circuit breaker open: retry after {exc.remaining_timeout:.1f}s",
            ) from exc

    async def _do_request(
        self,
        method: str,
        url: str,
        json_payload: dict[str, Any] | None,
    ) -> ProviderPaymentResult:
        """Internal method that performs the actual HTTP request to the provider."""

        await self._circuit_breaker.before_request()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json_payload,
                )

            if response.status_code >= 500:
                await self._circuit_breaker.on_failure()
                raise PaymentProviderError(
                    message=f"Provider returned {response.status_code}: {response.text}",
                )

            if response.status_code >= 400:
                raise PaymentProviderClientError(
                    message=f"Provider returned {response.status_code}: {response.text}",
                )

            await self._circuit_breaker.on_success()
            data = response.json()

            return ProviderPaymentResult(
                provider_transaction_id=data.get("transaction_id", ""),
                status=data.get("status", "unknown"),
                raw=data,
            )

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            await self._circuit_breaker.on_failure()
            raise PaymentProviderUnavailableError(
                message=f"Provider request failed: {exc}",
            ) from exc
