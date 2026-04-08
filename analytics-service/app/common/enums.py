from enum import StrEnum


class PaymentStatusEnum(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CurrencyEnum(StrEnum):
    USD = "USD"
    EUR = "EUR"
    RUB = "RUB"
