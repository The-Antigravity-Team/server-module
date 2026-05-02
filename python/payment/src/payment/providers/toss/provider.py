from __future__ import annotations

from datetime import datetime, timezone

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

from .client import TossPaymentsClient
from .models import TossPaymentResponse
from .settings import TossPaymentsSettings

# TossPayments status → 공통 PaymentStatus
_STATUS_MAP: dict[str, PaymentStatus] = {
    "READY": PaymentStatus.READY,
    "IN_PROGRESS": PaymentStatus.IN_PROGRESS,
    "WAITING_FOR_DEPOSIT": PaymentStatus.IN_PROGRESS,  # 가상계좌 입금 대기
    "DONE": PaymentStatus.DONE,
    "CANCELED": PaymentStatus.CANCELED,
    "PARTIAL_CANCELED": PaymentStatus.PARTIAL_CANCELED,
    "ABORTED": PaymentStatus.ABORTED,
    "EXPIRED": PaymentStatus.EXPIRED,
}

# TossPayments method (한글) → 공통 PaymentMethod
_METHOD_MAP: dict[str, PaymentMethod] = {
    "카드": PaymentMethod.CARD,
    "가상계좌": PaymentMethod.VIRTUAL_ACCOUNT,
    "간편결제": PaymentMethod.EASY_PAY,
    "휴대폰": PaymentMethod.MOBILE_PHONE,
    "계좌이체": PaymentMethod.TRANSFER,
    "문화상품권": PaymentMethod.CULTURE_GIFT_CERTIFICATE,
    "도서문화상품권": PaymentMethod.BOOK_CULTURE_GIFT_CERTIFICATE,
    "게임문화상품권": PaymentMethod.GAME_CULTURE_GIFT_CERTIFICATE,
}


def _map_status(raw: str) -> PaymentStatus:
    return _STATUS_MAP.get(raw, PaymentStatus.ABORTED)


def _map_method(raw: str | None) -> PaymentMethod:
    if raw is None:
        return PaymentMethod.UNKNOWN
    return _METHOD_MAP.get(raw, PaymentMethod.UNKNOWN)


class TossPaymentsProvider(BasePaymentProvider):
    provider_name = "toss"

    def __init__(self, settings: TossPaymentsSettings | None = None) -> None:
        self._client = TossPaymentsClient(settings or TossPaymentsSettings())

    async def confirm_payment(self, request: PaymentConfirmRequest) -> PaymentConfirmResult:
        raw = await self._client.confirm({
            "paymentKey": request.payment_key,
            "orderId": request.order_id,
            "amount": request.amount,
        })
        parsed = TossPaymentResponse.model_validate(raw)

        if parsed.total_amount != request.amount:
            raise PaymentAmountMismatchError(
                expected=request.amount, actual=parsed.total_amount
            )

        return PaymentConfirmResult(
            payment_key=parsed.payment_key,
            order_id=parsed.order_id,
            order_name=parsed.order_name,
            status=_map_status(parsed.status),
            method=_map_method(parsed.method),
            amount=parsed.total_amount,
            approved_at=parsed.approved_at,
            raw=raw,
        )

    async def cancel_payment(self, request: PaymentCancelRequest) -> PaymentCancelResult:
        payload: dict = {"cancelReason": request.cancel_reason}
        if request.cancel_amount is not None:
            payload["cancelAmount"] = request.cancel_amount

        raw = await self._client.cancel(request.payment_key, payload)
        parsed = TossPaymentResponse.model_validate(raw)

        latest = parsed.cancels[-1] if parsed.cancels else None
        cancel_amount = latest.cancel_amount if latest else (
            request.cancel_amount or parsed.total_amount
        )
        canceled_at = latest.canceled_at if latest else datetime.now(timezone.utc)

        return PaymentCancelResult(
            payment_key=parsed.payment_key,
            order_id=parsed.order_id,
            cancel_amount=cancel_amount,
            remaining_amount=parsed.balance_amount,
            status=_map_status(parsed.status),
            canceled_at=canceled_at,
            raw=raw,
        )

    async def get_payment(self, payment_key: str) -> PaymentQueryResult:
        raw = await self._client.get_by_key(payment_key)
        return self._to_query_result(raw)

    async def get_payment_by_order_id(self, order_id: str) -> PaymentQueryResult:
        raw = await self._client.get_by_order(order_id)
        return self._to_query_result(raw)

    def _to_query_result(self, raw: dict) -> PaymentQueryResult:
        parsed = TossPaymentResponse.model_validate(raw)
        canceled_at = parsed.cancels[-1].canceled_at if parsed.cancels else None
        return PaymentQueryResult(
            payment_key=parsed.payment_key,
            order_id=parsed.order_id,
            order_name=parsed.order_name,
            status=_map_status(parsed.status),
            method=_map_method(parsed.method),
            amount=parsed.total_amount,
            approved_at=parsed.approved_at,
            canceled_at=canceled_at,
            raw=raw,
        )
