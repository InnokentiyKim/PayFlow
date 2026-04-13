import asyncio
import uuid

import structlog
from asgi_correlation_id import CorrelationIdMiddleware
from typing import AsyncGenerator

from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.routers.common import http_router_v1
from app.api.routers.health import router as health_router
from app.core.config import app_config
from app.core.logger import setup_logging
from app.setup.exception_handlers import general_exception_handler
from app.setup.middleware import AccessLogMiddleware
from app.integrations.database import engine
from app.integrations.kafka import OutboxRelay
from app.common.exceptions import ExceptionBase


logger = structlog.get_logger(app_config.logger.app_logger_name)


def _is_valid_uuid(value: str) -> bool:
    """Validator that accepts UUIDs with or without hyphens."""
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError):
        return False


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    await logger.ainfo(
        "Application starting up",
        service=app_config.general.service_name,
        version=app_config.general.service_version,
        environment=app_config.general.environment,
    )

    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=False,
    )
    outbox_relay = OutboxRelay(session_factory=session_factory)
    relay_task = asyncio.create_task(outbox_relay.start())

    def _relay_task_done(task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error(
                "Outbox relay task crashed",
                error=str(exc),
                error_type=type(exc).__name__,
            )

    relay_task.add_done_callback(_relay_task_done)

    yield

    await outbox_relay.stop()
    relay_task.cancel()
    try:
        await relay_task
    except asyncio.CancelledError:
        pass

    await engine.dispose()
    await logger.ainfo(
        "Application shutting down",
        service=app_config.general.service_name,
    )


def create_fastapi_app() -> FastAPI:
    """
    Creates and configures the FastAPI application.

    This single factory function handles app creation for HTTP services

    Returns:
        The fully configured FastAPI application.
    """
    # Logging setup
    setup_logging(app_config)

    # Application Initialization
    app = FastAPI(
        title="Payment service API",
        version="1.0.0",
        terms_of_service="",
        description="A payment service API built with FastAPI",
        lifespan=lifespan,
    )
    # Register exception handlers
    app.add_exception_handler(ExceptionBase, general_exception_handler)

    # Middleware Configuration
    app.add_middleware(AccessLogMiddleware)  # type: ignore[arg-type]
    app.add_middleware(CorrelationIdMiddleware, validator=_is_valid_uuid)  # type: ignore[arg-type]

    # API routing
    app.include_router(health_router)
    app.include_router(http_router_v1)

    return app
