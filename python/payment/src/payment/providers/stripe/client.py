"""
Stripe REST API 클라이언트 (raw httpx).

Stripe API 특이사항:
- 인증:  Authorization: Bearer {secret_key}
- POST:  Content-Type: application/x-www-form-urlencoded  (data= 파라미터)
- GET:   query string (params= 파라미터)
- 오류:  HTTP 4xx/5xx + body {"error": {"code": "...", "message": "..."}}
"""
from __future__ import annotations

import httpx

from payment.core.exceptions import PaymentNotFoundError, ProviderAPIError

from .settings import StripeSettings


class StripeClient:
    BASE = "https://api.stripe.com/v1"

    def __init__(self, settings: StripeSettings) -> None:
        self._headers = {
            "Authorization": f"Bearer {settings.secret_key}",
            "Stripe-Version": settings.api_version,
        }
        self._timeout = settings.timeout_seconds

    def _make_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(headers=self._headers, timeout=self._timeout)

    async def retrieve_pi(self, pi_id: str) -> dict:
        """GET /v1/payment_intents/{id}"""
        async with self._make_client() as client:
            resp = await client.get(f"{self.BASE}/payment_intents/{pi_id}")
        return self._handle(resp)

    async def confirm_pi(self, pi_id: str, data: dict) -> dict:
        """POST /v1/payment_intents/{id}/confirm"""
        async with self._make_client() as client:
            resp = await client.post(
                f"{self.BASE}/payment_intents/{pi_id}/confirm", data=data
            )
        return self._handle(resp)

    async def create_refund(self, data: dict) -> dict:
        """POST /v1/refunds"""
        async with self._make_client() as client:
            resp = await client.post(f"{self.BASE}/refunds", data=data)
        return self._handle(resp)

    async def search_by_order_id(self, order_id: str) -> dict:
        """GET /v1/payment_intents?metadata[order_id]={order_id}&limit=1"""
        async with self._make_client() as client:
            resp = await client.get(
                f"{self.BASE}/payment_intents",
                params={"metadata[order_id]": order_id, "limit": 1},
            )
        data = self._handle(resp)
        items: list = data.get("data", [])
        if not items:
            raise PaymentNotFoundError(
                f"No PaymentIntent found for order_id={order_id!r}"
            )
        return items[0]

    def _handle(self, resp: httpx.Response) -> dict:
        data: dict = resp.json()

        if resp.status_code == 404:
            err = data.get("error", {})
            raise PaymentNotFoundError(err.get("message", "Payment not found"))

        if not resp.is_success:
            err = data.get("error", {})
            raise ProviderAPIError(
                status_code=resp.status_code,
                error_code=err.get("code", "UNKNOWN"),
                message=err.get("message", "Unknown error"),
            )

        return data
