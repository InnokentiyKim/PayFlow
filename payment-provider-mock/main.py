from contextlib import asynccontextmanager
import json
import logging
import sys

import structlog
import uvicorn
from fastapi import FastAPI, Request, Response

from service import (
    process_payment,
    ProcessPaymentResponse,
    ProcessPaymentRequest,
    ProviderErrorResponse,
)


def setup_logging() -> None:
    """Configure structlog so that all log output goes to stdout as JSON."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await logger.ainfo("Payment provider mock started")
    yield
    await logger.ainfo("Payment provider mock shutting down")


app = FastAPI(
    title="Mock Payment Provider",
    description="Simulates an unstable external payment gateway for development/testing.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(ProviderErrorResponse)
async def provider_error_handler(
    request: Request, exc: ProviderErrorResponse
) -> Response:
    return Response(
        status_code=exc.status_code,
        content=json.dumps({"detail": exc.detail}),
        media_type="application/json",
    )


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "mock-payment-provider"}


@app.post(
    "/process-payment",
    tags=["payments"],
    response_model=ProcessPaymentResponse,
)
async def process_payment_endpoint(
    payload: ProcessPaymentRequest,
) -> ProcessPaymentResponse:

    result = await process_payment(payload)
    return result


def main() -> None:
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        log_config=None,
        access_log=False,
        reload=False,
    )


if __name__ == "__main__":
    main()
