from __future__ import annotations

from datetime import UTC, datetime

from payment.core.base import BasePaymentProvider
from payment.core.enums import PaymentMethod, PaymentStatus
from payment.core.exceptions import PaymentAmountMismatchError
from payment.core.models import (
    PaymentCancelRequest,
    PaymentCancelResult,
    PaymentConfirmRequest,
    PaymentConfirmResult,
    PaymentQueryResult,
)

from .client import NHNKCPClient
from .models import KCPCancelResponse, KCPConfirmResponse, KCPQueryResponse
from .settings import NHNKCPSettings

# KCP pay_method → 공통 PaymentMethod
_METHOD_MAP: dict[str, PaymentMethod] = {
    "CARD": PaymentMethod.CARD,
    "VCNT": PaymentMethod.VIRTUAL_ACCOUNT,
    "PCEL": PaymentMethod.MOBILE_PHONE,
    "TRAN": PaymentMethod.TRANSFER,
    "KWCP": PaymentMethod.EASY_PAY,   # KakaoPay
    "NPAY": PaymentMethod.EASY_PAY,   # NaverPay
    "TCSH": PaymentMethod.EASY_PAY,   # Toss
    "GIFT": PaymentMethod.CULTURE_GIFT_CERTIFICATE,
}


def _map_method(raw: str | None) -> PaymentMethod:
    if raw is None:
        return PaymentMethod.UNKNOWN
    return _METHOD_MAP.get(raw.upper(), PaymentMethod.UNKNOWN)


def _parse_kcp_datetime(date: str | None, time: str | None) -> datetime | None:
    """KCP 날짜(YYYYMMDD) + 시각(HHMMSS) → datetime (UTC)"""
    if not date or not time:
        return None
    try:
        return datetime.strptime(f"{date}{time}", "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


class NHNKCPProvider(BasePaymentProvider):
    provider_name = "nhn_kcp"

    def __init__(self, settings: NHNKCPSettings | None = None) -> None:
        self._settings = settings or NHNKCPSettings()
        self._client = NHNKCPClient(self._settings)

    async def confirm_payment(self, request: PaymentConfirmRequest) -> PaymentConfirmResult:
        raw = await self._client.confirm({
            "site_cd": self._settings.site_cd,
            "tno": request.payment_key,
            "enc_data": request.extra.get("enc_data", ""),
            "enc_info": request.extra.get("enc_info", ""),
            "pay_method": request.extra.get("pay_method", "CARD"),
            "ordr_idxx": request.order_id,
            "good_name": request.extra.get("good_name", ""),
            "good_mny": request.amount,
        })
        parsed = KCPConfirmResponse.model_validate(raw)

        if parsed.amount != request.amount:
            raise PaymentAmountMismatchError(
                expected=request.amount, actual=parsed.amount
            )

        approved_at = _parse_kcp_datetime(parsed.van_appro_date, parsed.van_appro_time)

        return PaymentConfirmResult(
            payment_key=parsed.tno,
            order_id=parsed.ordr_idxx or request.order_id,
            order_name=parsed.good_name or request.extra.get("good_name", ""),
            status=PaymentStatus.DONE,
            method=_map_method(parsed.pay_method),
            amount=parsed.amount,
            approved_at=approved_at or datetime.now(UTC),
            raw=raw,
        )

    async def cancel_payment(self, request: PaymentCancelRequest) -> PaymentCancelResult:
        # 잔여 금액은 caller가 extra로 전달하거나, 조회 후 계산해야 함
        # extra["total_amount"] 가 있으면 사용, 없으면 cancel_amount == total (전액 취소 가정)
        total = request.extra.get("total_amount", request.cancel_amount or 0)
        cancel_amount = request.cancel_amount or total
        rem_mny = total - cancel_amount
        mod_type = "PART" if rem_mny > 0 else "STAX"

        raw = await self._client.cancel({
            "site_cd": self._settings.site_cd,
            "tno": request.payment_key,
            "mod_type": mod_type,
            "mod_mny": cancel_amount,
            "rem_mny": rem_mny,
            "canc_memo": request.cancel_reason,
        })
        parsed = KCPCancelResponse.model_validate(raw)

        canceled_at = (
            _parse_kcp_datetime(parsed.mod_date, parsed.mod_time)
            or datetime.now(UTC)
        )
        actual_cancel = parsed.mod_mny if parsed.mod_mny is not None else cancel_amount
        actual_remaining = parsed.rem_mny if parsed.rem_mny is not None else rem_mny

        status = (
            PaymentStatus.PARTIAL_CANCELED if actual_remaining > 0 else PaymentStatus.CANCELED
        )

        return PaymentCancelResult(
            payment_key=request.payment_key,
            order_id=request.extra.get("order_id", ""),
            cancel_amount=actual_cancel,
            remaining_amount=actual_remaining,
            status=status,
            canceled_at=canceled_at,
            raw=raw,
        )

    async def get_payment(self, payment_key: str) -> PaymentQueryResult:
        raw = await self._client.get_by_tno(payment_key)
        return self._to_query_result(raw)

    async def get_payment_by_order_id(self, order_id: str) -> PaymentQueryResult:
        raw = await self._client.get_by_order_id(order_id)
        return self._to_query_result(raw)

    def _to_query_result(self, raw: dict) -> PaymentQueryResult:
        parsed = KCPQueryResponse.model_validate(raw)

        approved_at = _parse_kcp_datetime(parsed.van_appro_date, parsed.van_appro_time)
        canceled_at = _parse_kcp_datetime(parsed.mod_date, parsed.mod_time)

        if parsed.cancel_yn == "Y":
            status = (
                PaymentStatus.PARTIAL_CANCELED
                if parsed.part_cancel_yn == "Y"
                else PaymentStatus.CANCELED
            )
        else:
            status = PaymentStatus.DONE

        return PaymentQueryResult(
            payment_key=parsed.tno or "",
            order_id=parsed.ordr_idxx or "",
            order_name=parsed.good_name or "",
            status=status,
            method=_map_method(parsed.pay_method),
            amount=parsed.amount or 0,
            approved_at=approved_at,
            canceled_at=canceled_at,
            raw=raw,
        )
