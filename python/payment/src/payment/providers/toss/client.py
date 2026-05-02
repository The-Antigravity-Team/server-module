from __future__ import annotations

import base64

import httpx

from payment.core.exceptions import PaymentNotFoundError, ProviderAPIError

from .settings import TossPaymentsSettings


class TossPaymentsClient:
    def __init__(self, settings: TossPaymentsSettings) -> None:
        token = base64.b64encode(f"{settings.secret_key}:".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }
        self._base = f"{settings.base_url}/{settings.api_version}"
        self._timeout = settings.timeout_seconds

    def _make_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self._headers, timeout=self._timeout)

    async def confirm(self, payload: dict) -> dict:
        async with self._make_client() as client:
            resp = await client.post(f"{self._base}/payments/confirm", json=payload)
        return self._handle(resp)

    async def cancel(self, payment_key: str, payload: dict) -> dict:
        async with self._make_client() as client:
            resp = await client.post(
                f"{self._base}/payments/{payment_key}/cancel", json=payload
            )
        return self._handle(resp)

    async def get_by_key(self, payment_key: str) -> dict:
        async with self._make_client() as client:
            resp = await client.get(f"{self._base}/payments/{payment_key}")
        return self._handle(resp)

    async def get_by_order(self, order_id: str) -> dict:
        async with self._make_client() as client:
            resp = await client.get(f"{self._base}/payments/orders/{order_id}")
        return self._handle(resp)

    def _handle(self, resp: httpx.Response) -> dict:
        data: dict = resp.json()
        if resp.status_code == 404:
            raise PaymentNotFoundError(data.get("message", "Payment not found"))
        if not resp.is_success:
            raise ProviderAPIError(
                status_code=resp.status_code,
                error_code=data.get("code", "UNKNOWN"),
                message=data.get("message", "Unknown error"),
            )
        return data
