import pytest
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import httpx
from fastapi import FastAPI

from app.integrations.dao.payment import PaymentDAO
from app.integrations.payment import PaymentProviderClient
from app.services.payment import PaymentService, provide_payment_service
from app.setup.fastapi_app import create_fastapi_app


@asynccontextmanager
async def _noop_lifespan(app: FastAPI) -> AsyncGenerator:
    yield


@pytest.fixture()
def mock_dao() -> AsyncMock:
    return AsyncMock(spec=PaymentDAO)


@pytest.fixture()
def mock_provider() -> AsyncMock:
    return AsyncMock(spec=PaymentProviderClient)


@pytest.fixture()
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def app(
    mock_dao: AsyncMock, mock_provider: AsyncMock, mock_session: AsyncMock
) -> FastAPI:
    application = create_fastapi_app()
    application.router.lifespan_context = _noop_lifespan

    def _override_service() -> PaymentService:
        return PaymentService(
            session=mock_session,
            dao=mock_dao,
            provider=mock_provider,
        )

    application.dependency_overrides[provide_payment_service] = _override_service
    return application


@pytest.fixture()
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
