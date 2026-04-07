import uuid
from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest

from app.common.enums import PaymentStatusEnum
from app.common.exceptions import (
    DatabaseError,
    PaymentProviderClientError,
    PaymentProviderError,
    PaymentProviderUnavailableError,
)
from app.integrations.payment import ProviderPaymentResult
from app.models.payments import Payment


def _make_payment(
    *,
    payment_id: uuid.UUID | None = None,
    amount: Decimal = Decimal("10.0000"),
    currency: str = "USD",
    status: PaymentStatusEnum = PaymentStatusEnum.PENDING,
    description: str | None = "test payment",
    idempotency_key: str = "key-1",
) -> Payment:
    payment = Payment(
        amount=amount,
        currency=currency,
        status=status,
        description=description,
        idempotency_key=idempotency_key,
    )
    if payment_id is not None:
        payment.id = payment_id
    return payment


_VALID_PAYLOAD = {
    "amount": "10.00",
    "currency": "USD",
    "idempotency_key": "key-1",
    "description": "unit test",
}


@pytest.mark.asyncio
class TestCreatePayment:
    async def test_create_payment_201(
        self, client: httpx.AsyncClient, mock_dao: AsyncMock
    ):
        mock_dao.get_payment_by_idempotency_key.return_value = None
        mock_dao.add_payment.side_effect = lambda session, payment: payment.id

        resp = await client.post("/api/v1/payments", json=_VALID_PAYLOAD)

        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert body["status"] == PaymentStatusEnum.PENDING
        assert body["idempotency_key"] == "key-1"
        mock_dao.get_payment_by_idempotency_key.assert_awaited_once()
        mock_dao.add_payment.assert_awaited_once()

    async def test_create_payment_idempotent_200(
        self, client: httpx.AsyncClient, mock_dao: AsyncMock
    ):
        existing = _make_payment(idempotency_key="key-1")
        mock_dao.get_payment_by_idempotency_key.return_value = existing

        resp = await client.post("/api/v1/payments", json=_VALID_PAYLOAD)

        assert resp.status_code == 200
        body = resp.json()
        assert body["idempotency_key"] == "key-1"
        mock_dao.add_payment.assert_not_awaited()

    async def test_negative_amount_422(self, client: httpx.AsyncClient):
        payload = {**_VALID_PAYLOAD, "amount": "-5.00"}
        resp = await client.post("/api/v1/payments", json=payload)
        assert resp.status_code == 422

    async def test_invalid_currency_422(self, client: httpx.AsyncClient):
        payload = {**_VALID_PAYLOAD, "currency": "INVALID"}
        resp = await client.post("/api/v1/payments", json=payload)
        assert resp.status_code == 422

    async def test_zero_amount_422(self, client: httpx.AsyncClient):
        payload = {**_VALID_PAYLOAD, "amount": "0"}
        resp = await client.post("/api/v1/payments", json=payload)
        assert resp.status_code == 422

    async def test_missing_fields_422(self, client: httpx.AsyncClient):
        resp = await client.post("/api/v1/payments", json={})
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestGetPayment:
    async def test_get_payment_200(
        self, client: httpx.AsyncClient, mock_dao: AsyncMock
    ):
        pid = uuid.uuid4()
        payment = _make_payment(payment_id=pid)
        mock_dao.get_payment_by_id.return_value = payment

        resp = await client.get(f"/api/v1/payments/{pid}")

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(pid)
        assert body["currency"] == "USD"
        mock_dao.get_payment_by_id.assert_awaited_once()

    async def test_get_payment_not_found_404(
        self, client: httpx.AsyncClient, mock_dao: AsyncMock
    ):
        mock_dao.get_payment_by_id.return_value = None

        resp = await client.get(f"/api/v1/payments/{uuid.uuid4()}")

        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"][0]["type"] == "ItemNotFoundError"


@pytest.mark.asyncio
class TestGetPayments:
    async def test_get_payments_200(
        self, client: httpx.AsyncClient, mock_dao: AsyncMock
    ):
        mock_dao.get_payments.return_value = [
            _make_payment(),
            _make_payment(idempotency_key="key-2"),
        ]

        resp = await client.get("/api/v1/payments")

        assert resp.status_code == 200
        assert len(resp.json()) == 2
        mock_dao.get_payments.assert_awaited_once()

    async def test_get_payments_empty(
        self, client: httpx.AsyncClient, mock_dao: AsyncMock
    ):
        mock_dao.get_payments.return_value = []

        resp = await client.get("/api/v1/payments")

        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
class TestProcessPayment:
    async def test_process_payment_200(
        self,
        client: httpx.AsyncClient,
        mock_dao: AsyncMock,
        mock_provider: AsyncMock,
    ):
        pid = uuid.uuid4()
        payment = _make_payment(payment_id=pid)
        mock_dao.get_payment_by_id.return_value = payment
        mock_provider.process_payment.return_value = ProviderPaymentResult(
            provider_transaction_id="tx-123",
            status="success",
            raw={"id": "tx-123"},
        )
        mock_dao.update_payment_status.return_value = None

        resp = await client.post(f"/api/v1/payments/{pid}/process")

        assert resp.status_code == 200
        assert resp.json()["id"] == str(pid)
        mock_provider.process_payment.assert_awaited_once()
        mock_dao.update_payment_status.assert_awaited_once()

    async def test_process_payment_not_found_404(
        self, client: httpx.AsyncClient, mock_dao: AsyncMock
    ):
        mock_dao.get_payment_by_id.return_value = None

        resp = await client.post(f"/api/v1/payments/{uuid.uuid4()}/process")

        assert resp.status_code == 404

    async def test_process_already_completed_skips_provider(
        self,
        client: httpx.AsyncClient,
        mock_dao: AsyncMock,
        mock_provider: AsyncMock,
    ):
        pid = uuid.uuid4()
        payment = _make_payment(payment_id=pid, status=PaymentStatusEnum.COMPLETED)
        mock_dao.get_payment_by_id.return_value = payment

        resp = await client.post(f"/api/v1/payments/{pid}/process")

        assert resp.status_code == 200
        assert resp.json()["status"] == PaymentStatusEnum.COMPLETED
        mock_provider.process_payment.assert_not_awaited()
        mock_dao.update_payment_status.assert_not_awaited()

    async def test_process_already_failed_skips_provider(
        self,
        client: httpx.AsyncClient,
        mock_dao: AsyncMock,
        mock_provider: AsyncMock,
    ):
        pid = uuid.uuid4()
        payment = _make_payment(payment_id=pid, status=PaymentStatusEnum.FAILED)
        mock_dao.get_payment_by_id.return_value = payment

        resp = await client.post(f"/api/v1/payments/{pid}/process")

        assert resp.status_code == 200
        assert resp.json()["status"] == PaymentStatusEnum.FAILED
        mock_provider.process_payment.assert_not_awaited()
        mock_dao.update_payment_status.assert_not_awaited()

    async def test_process_provider_error_marks_failed(
        self,
        client: httpx.AsyncClient,
        mock_dao: AsyncMock,
        mock_provider: AsyncMock,
    ):
        pid = uuid.uuid4()
        payment = _make_payment(payment_id=pid)
        mock_dao.get_payment_by_id.return_value = payment
        mock_provider.process_payment.side_effect = PaymentProviderError(
            message="unexpected provider error"
        )
        mock_dao.update_payment_status.return_value = None

        resp = await client.post(f"/api/v1/payments/{pid}/process")

        assert resp.status_code == 200
        mock_dao.update_payment_status.assert_awaited_once()
        call_args = mock_dao.update_payment_status.call_args
        assert call_args[0][2] == PaymentStatusEnum.FAILED

    async def test_process_provider_unavailable_marks_failed(
        self,
        client: httpx.AsyncClient,
        mock_dao: AsyncMock,
        mock_provider: AsyncMock,
    ):
        pid = uuid.uuid4()
        payment = _make_payment(payment_id=pid)
        mock_dao.get_payment_by_id.return_value = payment
        mock_provider.process_payment.side_effect = PaymentProviderUnavailableError(
            message="circuit breaker open"
        )
        mock_dao.update_payment_status.return_value = None

        resp = await client.post(f"/api/v1/payments/{pid}/process")

        assert resp.status_code == 200
        mock_dao.update_payment_status.assert_awaited_once()
        call_args = mock_dao.update_payment_status.call_args
        assert call_args[0][2] == PaymentStatusEnum.FAILED

    async def test_process_provider_client_error_marks_failed(
        self,
        client: httpx.AsyncClient,
        mock_dao: AsyncMock,
        mock_provider: AsyncMock,
    ):
        pid = uuid.uuid4()
        payment = _make_payment(payment_id=pid)
        mock_dao.get_payment_by_id.return_value = payment
        mock_provider.process_payment.side_effect = PaymentProviderClientError(
            message="invalid request data"
        )
        mock_dao.update_payment_status.return_value = None

        resp = await client.post(f"/api/v1/payments/{pid}/process")

        assert resp.status_code == 200
        mock_dao.update_payment_status.assert_awaited_once()
        call_args = mock_dao.update_payment_status.call_args
        assert call_args[0][2] == PaymentStatusEnum.FAILED

    async def test_process_dao_update_raises_db_error(
        self,
        client: httpx.AsyncClient,
        mock_dao: AsyncMock,
        mock_provider: AsyncMock,
    ):
        pid = uuid.uuid4()
        payment = _make_payment(payment_id=pid)
        mock_dao.get_payment_by_id.return_value = payment
        mock_provider.process_payment.return_value = ProviderPaymentResult(
            provider_transaction_id="tx-456",
            status="success",
            raw={"id": "tx-456"},
        )
        mock_dao.update_payment_status.side_effect = DatabaseError(
            message="DB write failed"
        )

        resp = await client.post(f"/api/v1/payments/{pid}/process")

        assert resp.status_code == 500
        body = resp.json()
        assert body["detail"][0]["type"] == "DatabaseError"
