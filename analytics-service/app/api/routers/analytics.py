from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query

from app.common.enums import PaymentStatusEnum
from app.schemas.response import AnalyticsSummaryResponseDTO, TransactionResponseDTO
from app.services.analytics import AnalyticsServiceDependency, SUMMARY_CACHE_PREFIX
from app.schemas import fetch as fetches
from app.services.cache import CacheServiceDependency

router = APIRouter(
    prefix="/analytics",
    tags=["analytics"],
)


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponseDTO,
    summary="Общая сводка аналитики",
    description=(
        "Количество транзакций, общая сумма, средний чек, "
        "разбивка по статусам и валютам. Поддерживает фильтрацию по периоду и валюте."
    ),
)
async def get_summary(
    service: AnalyticsServiceDependency,
    cache: CacheServiceDependency,
    date_from: datetime | None = Query(
        default=None, description="Начало периода (ISO 8601)"
    ),
    date_to: datetime | None = Query(
        default=None, description="Конец периода (ISO 8601)"
    ),
    currency: str | None = Query(
        default=None,
        min_length=3,
        max_length=3,
        description="Фильтр по валюте (USD, EUR, RUB)",
    ),
) -> AnalyticsSummaryResponseDTO:
    cache_key = cache.build_cache_key(
        cache_prefix=SUMMARY_CACHE_PREFIX,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
        currency=currency if currency else None,
    )
    cached = await cache.get_cache(cache_key)
    if cached is not None:
        report = service.deserialize_report(cached)
        return AnalyticsSummaryResponseDTO.from_report(report)

    # Cache miss – query the service and then store the result in cache
    report = await service.get_summary(
        fetch=fetches.GetAnalyticsSummary(
            date_from=date_from, date_to=date_to, currency=currency
        )
    )

    # Store in cache
    if cache_key is not None:
        await cache.set_cache(cache_key, service.serialize_report(report))

    return AnalyticsSummaryResponseDTO.from_report(report)


@router.get(
    "/transactions",
    response_model=list[TransactionResponseDTO],
    summary="Список транзакций",
    description="Список транзакций с пагинацией и фильтрацией по статусу, валюте и периоду.",
)
async def get_transactions(
    service: AnalyticsServiceDependency,
    date_from: datetime | None = Query(
        default=None, description="Начало периода (ISO 8601)"
    ),
    date_to: datetime | None = Query(
        default=None, description="Конец периода (ISO 8601)"
    ),
    currency: str | None = Query(
        default=None, max_length=3, description="Фильтр по валюте"
    ),
    status: PaymentStatusEnum | None = Query(
        default=None, description="Фильтр по статусу"
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Количество записей"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
) -> list[TransactionResponseDTO]:
    transactions = await service.get_transactions(
        fetch=fetches.GetTransactions(
            date_from=date_from,
            date_to=date_to,
            currency=currency,
            status=status,
            limit=limit,
            offset=offset,
        )
    )

    return [
        TransactionResponseDTO.model_validate(transaction)
        for transaction in transactions
    ]


@router.get(
    "/transactions/{payment_id}",
    response_model=TransactionResponseDTO,
    summary="Детали транзакции",
    description="Возвращает детали конкретной транзакции по payment_id. 404 если не найдена.",
)
async def get_transaction_by_payment_id(
    service: AnalyticsServiceDependency,
    payment_id: UUID,
) -> TransactionResponseDTO:
    transactions = await service.get_transaction_by_payment_id(payment_id)
    return TransactionResponseDTO.model_validate(transactions)
