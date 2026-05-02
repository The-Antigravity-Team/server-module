from __future__ import annotations

from datetime import UTC, datetime

from payment.core.base import BasePaymentProvider
from payment.core.enums import PaymentMethod, PaymentStatus
from payment.core.exceptions import PaymentAmountMismatchError, PaymentConfirmError
from payment.core.models import (
    PaymentCancelRequest,
    PaymentCancelResult,
    PaymentConfirmRequest,
    PaymentConfirmResult,
    PaymentQueryResult,
)

from .client import StripeClient
from .models import StripePaymentIntentResponse, StripeRefundResponse
from .settings import StripeSettings

# Stripe PI status → 공통 PaymentStatus
_STATUS_MAP: dict[str, PaymentStatus] = {
    "succeeded": PaymentStatus.DONE,
    "requires_payment_method": PaymentStatus.READY,
    "requires_confirmation": PaymentStatus.IN_PROGRESS,
    "requires_action": PaymentStatus.IN_PROGRESS,
    "processing": PaymentStatus.IN_PROGRESS,
    "requires_capture": PaymentStatus.IN_PROGRESS,
    "canceled": PaymentStatus.CANCELED,
}

# Stripe payment_method_type → 공통 PaymentMethod
_METHOD_MAP: dict[str, PaymentMethod] = {
    "card": PaymentMethod.CARD,
    "us_bank_account": PaymentMethod.TRANSFER,
    "sepa_debit": PaymentMethod.TRANSFER,
    "bank_transfer": PaymentMethod.TRANSFER,
    "alipay": PaymentMethod.EASY_PAY,
    "wechat_pay": PaymentMethod.EASY_PAY,
    "grabpay": PaymentMethod.EASY_PAY,
    "klarna": PaymentMethod.EASY_PAY,
    "afterpay_clearpay": PaymentMethod.EASY_PAY,
    "paynow": PaymentMethod.EASY_PAY,
}

# Stripe refund reason 코드
_REFUND_REASON_MAP: dict[str, str] = {
    "fraudulent": "fraudulent",
    "fraud": "fraudulent",
    "사기": "fraudulent",
    "duplicate": "duplicate",
    "중복": "duplicate",
}


def _map_status(raw: str) -> PaymentStatus:
    return _STATUS_MAP.get(raw, PaymentStatus.ABORTED)


def _map_method(types: list[str]) -> PaymentMethod:
    if not types:
        return PaymentMethod.UNKNOWN
    return _METHOD_MAP.get(types[0], PaymentMethod.UNKNOWN)


def _map_refund_reason(reason: str) -> str:
    lower = reason.lower()
    for key, val in _REFUND_REASON_MAP.items():
        if key in lower or key in reason:
            return val
    return "requested_by_customer"


class StripeProvider(BasePaymentProvider):
    """
    Stripe PaymentIntents API 기반 결제 Provider.

    Confirm 흐름
    ------------
    A) 클라이언트 확인 방식 (기본): 클라이언트에서 Stripe.js로 결제 완료 →
       서버가 PaymentIntent를 조회(retrieve)하여 상태 검증.
       → extra 없이 사용.

    B) 서버 확인 방식: extra={"payment_method": "pm_xxx"} 전달 →
       서버가 직접 confirm 엔드포인트 호출.
       → 모바일 / 서버 사이드 결제 흐름에 사용.

    Cancel (환불) 흐름
    ------------------
    succeeded 상태의 PaymentIntent에 대해 Stripe Refund 생성.
    부분 환불: cancel_amount 지정.
    전액 환불: cancel_amount=None.
    잔여 금액 계산 시 extra={"total_amount": 50000} 전달 권장.
    """

    provider_name = "stripe"

    def __init__(self, settings: StripeSettings | None = None) -> None:
        self._settings = settings or StripeSettings()
        self._client = StripeClient(self._settings)

    async def confirm_payment(self, request: PaymentConfirmRequest) -> PaymentConfirmResult:
        pm = request.extra.get("payment_method")

        if pm:
            raw = await self._client.confirm_pi(
                request.payment_key, data={"payment_method": pm}
            )
        else:
            raw = await self._client.retrieve_pi(request.payment_key)

        parsed = StripePaymentIntentResponse.model_validate(raw)

        if parsed.status != "succeeded":
            raise PaymentConfirmError(
                f"PaymentIntent not completed (status={parsed.status!r}). "
                "Expected 'succeeded'."
            )

        if parsed.amount != request.amount:
            raise PaymentAmountMismatchError(
                expected=request.amount, actual=parsed.amount
            )

        order_id = parsed.metadata.order_id or request.order_id
        order_name = (
            parsed.metadata.order_name
            or parsed.description
            or request.extra.get("order_name", "")
        )
        approved_at = datetime.fromtimestamp(parsed.created, tz=UTC)

        return PaymentConfirmResult(
            payment_key=parsed.id,
            order_id=order_id,
            order_name=order_name,
            status=_map_status(parsed.status),
            method=_map_method(parsed.payment_method_types),
            amount=parsed.amount,
            approved_at=approved_at,
            raw=raw,
        )

    async def cancel_payment(self, request: PaymentCancelRequest) -> PaymentCancelResult:
        refund_data: dict = {
            "payment_intent": request.payment_key,
            "reason": _map_refund_reason(request.cancel_reason),
        }
        if request.cancel_amount is not None:
            refund_data["amount"] = request.cancel_amount

        raw = await self._client.create_refund(refund_data)
        parsed = StripeRefundResponse.model_validate(raw)

        total = request.extra.get("total_amount", 0)
        remaining = max(0, total - parsed.amount)
        status = (
            PaymentStatus.PARTIAL_CANCELED if remaining > 0 else PaymentStatus.CANCELED
        )
        canceled_at = datetime.fromtimestamp(parsed.created, tz=UTC)

        return PaymentCancelResult(
            payment_key=request.payment_key,
            order_id=request.extra.get("order_id", ""),
            cancel_amount=parsed.amount,
            remaining_amount=remaining,
            status=status,
            canceled_at=canceled_at,
            raw=raw,
        )

    async def get_payment(self, payment_key: str) -> PaymentQueryResult:
        raw = await self._client.retrieve_pi(payment_key)
        return self._to_query_result(raw)

    async def get_payment_by_order_id(self, order_id: str) -> PaymentQueryResult:
        raw = await self._client.search_by_order_id(order_id)
        return self._to_query_result(raw)

    def _to_query_result(self, raw: dict) -> PaymentQueryResult:
        parsed = StripePaymentIntentResponse.model_validate(raw)
        approved_at = (
            datetime.fromtimestamp(parsed.created, tz=UTC)
            if parsed.status == "succeeded"
            else None
        )
        order_id = parsed.metadata.order_id or ""
        order_name = parsed.metadata.order_name or parsed.description or ""

        return PaymentQueryResult(
            payment_key=parsed.id,
            order_id=order_id,
            order_name=order_name,
            status=_map_status(parsed.status),
            method=_map_method(parsed.payment_method_types),
            amount=parsed.amount,
            approved_at=approved_at,
            canceled_at=None,   # Stripe는 취소 시각을 PI에 직접 포함하지 않음
            raw=raw,
        )
