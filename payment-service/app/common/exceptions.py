from fastapi import status


class ExceptionBase(Exception):
    """Base class for all exceptions in the application."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "An internal server error occurred"

    def __init__(self, message: str = "", status_code: int = 0):
        self.message = message or self.message
        self.status_code = status_code or self.status_code

        super().__init__(self.message)


class ItemAlreadyExistsError(ExceptionBase):
    """Payment already exists."""

    status_code: int = status.HTTP_409_CONFLICT
    message: str = "Item already exists."


class ItemNotFoundError(ExceptionBase):
    """Payment not found."""

    status_code: int = status.HTTP_404_NOT_FOUND
    message: str = "Item not found."


class DatabaseError(ExceptionBase):
    """Database error."""

    status_code: int = status.HTTP_409_CONFLICT
    message: str = "Database error."


class PaymentProcessingError(ExceptionBase):
    """Payment processing error (e.g. database failure during processing, unexpected exception)."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    message: str = "Payment processing error."


class PaymentProviderError(ExceptionBase):
    """Payment provider returned an unexpected error."""

    status_code: int = status.HTTP_502_BAD_GATEWAY
    message: str = "Payment provider error."


class PaymentProviderUnavailableError(ExceptionBase):
    """Payment provider is unavailable (circuit breaker open or retries exhausted)."""

    status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE
    message: str = "Payment provider is temporarily unavailable."


class PaymentProviderClientError(ExceptionBase):
    """Payment provider returned a 4xx client error (not retryable)."""

    status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY
    message: str = "Payment provider rejected the request."
