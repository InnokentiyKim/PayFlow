import asyncio
import uuid

import structlog
from asgi_correlation_id import CorrelationIdMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker
from typing import AsyncGenerator

from fastapi import FastAPI
from contextlib import asynccontextmanager

from app.api.routers.common import http_router_v1
from app.api.routers.health import router as health_router
from app.core.config import app_config
from app.core.logger import setup_logging
from app.setup.exception_handlers import general_exception_handler
from app.setup.middleware import AccessLogMiddleware
from app.integrations.database import engine
from app.integrations.redis import RedisClient
from app.common.exceptions import ExceptionBase
from app.services.cache import CacheService
from consumer.payment_event_consumer import PaymentEventConsumer


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

    # Start Kafka consumer as a background task
    session_factory = async_sessionmaker(
        engine,
        expire_on_commit=app_config.database.session.expire_on_commit,
    )

    # Initialize Redis client and cache service for consumer
    redis_client = RedisClient(
        url=app_config.redis.redis_url,
        socket_timeout=app_config.redis.socket_timeout,
        socket_connect_timeout=app_config.redis.socket_connect_timeout,
    )
    cache_service = CacheService(redis_client=redis_client, config=app_config)

    stop_event = asyncio.Event()

    consumer = PaymentEventConsumer(
        config=app_config,
        session_factory=session_factory,
        cache_service=cache_service,
        stop_event=stop_event,
    )
    consumer_task = asyncio.create_task(consumer.start())

    # Store references in app.state for health checks
    app.state.redis_client = redis_client
    app.state.engine = engine
    app.state.consumer = consumer
    app.state.kafka_config = app_config.broker

    yield

    # Graceful shutdown
    await logger.ainfo("Shutdown initiated, signalling consumer to stop...")
    await consumer.stop()

    await logger.ainfo("Waiting for consumer task to finish current batch...")
    try:
        await asyncio.wait_for(consumer_task, timeout=30.0)
    except asyncio.TimeoutError:
        await logger.awarning("Consumer task did not finish in time, cancelling...")
        consumer_task.cancel()

    await redis_client.close()

    await engine.dispose()
    await logger.ainfo(
        "Application shut down gracefully",
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
