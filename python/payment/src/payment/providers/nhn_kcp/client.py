from __future__ import annotations

import base64

import httpx

from payment.core.exceptions import PaymentNotFoundError, ProviderAPIError

from .settings import NHNKCPSettings

_KCP_SUCCESS = "0000"
_KCP_NOT_FOUND = ("8131", "8133")  # KCP 거래 없음 코드


class NHNKCPClient:
    def __init__(self, settings: NHNKCPSettings) -> None:
        token = base64.b64encode(
            f"{settings.site_cd}:{settings.site_key}".encode()
        ).decode()
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
            resp = await client.post(f"{self._base}/payment", json=payload)
        return self._handle(resp)

    async def cancel(self, payload: dict) -> dict:
        async with self._make_client() as client:
            resp = await client.post(f"{self._base}/payment/cancel", json=payload)
        return self._handle(resp)

    async def get_by_tno(self, tno: str) -> dict:
        async with self._make_client() as client:
            resp = await client.get(f"{self._base}/payment/{tno}")
        return self._handle(resp)

    async def get_by_order_id(self, order_id: str) -> dict:
        async with self._make_client() as client:
            resp = await client.get(
                f"{self._base}/payment", params={"ordr_idxx": order_id}
            )
        return self._handle(resp)

    def _handle(self, resp: httpx.Response) -> dict:
        data: dict = resp.json()

        if resp.status_code == 404:
            raise PaymentNotFoundError(data.get("res_msg", "Payment not found"))

        if not resp.is_success:
            raise ProviderAPIError(
                status_code=resp.status_code,
                error_code=data.get("res_cd", "UNKNOWN"),
                message=data.get("res_msg", "Unknown error"),
            )

        # KCP는 HTTP 200이어도 res_cd로 오류를 반환
        res_cd: str = data.get("res_cd", "")
        if res_cd in _KCP_NOT_FOUND:
            raise PaymentNotFoundError(data.get("res_msg", "Payment not found"))
        if res_cd != _KCP_SUCCESS:
            raise ProviderAPIError(
                status_code=resp.status_code,
                error_code=res_cd,
                message=data.get("res_msg", "Unknown error"),
            )

        return data
