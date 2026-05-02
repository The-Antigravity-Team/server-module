"""payment.core.models Pydantic 유효성 검사 테스트"""
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from payment.core.enums import PaymentMethod, PaymentStatus
from payment.core.models import (
    PaymentCancelRequest,
    PaymentCancelResult,
    PaymentConfirmRequest,
    PaymentConfirmResult,
    PaymentQueryResult,
)


# ── PaymentConfirmRequest ─────────────────────────────────────────────────


class TestPaymentConfirmRequest:
    def test_valid_minimal(self) -> None:
        req = PaymentConfirmRequest(
            payment_key="pay_001",
            order_id="order-001",
            amount=50000,
        )
        assert req.extra == {}

    def test_extra_field_stores_arbitrary_data(self) -> None:
        req = PaymentConfirmRequest(
            payment_key="pay_001",
            order_id="order-001",
            amount=1000,
            extra={"enc_data": "abc", "enc_info": "xyz", "pay_method": "CARD"},
        )
        assert req.extra["enc_data"] == "abc"
        assert req.extra["pay_method"] == "CARD"

    def test_amount_zero_raises(self) -> None:
        with pytest.raises(ValidationError) as exc:
            PaymentConfirmRequest(payment_key="p", order_id="o", amount=0)
        assert "greater than 0" in str(exc.value).lower() or "gt" in str(exc.value).lower()

    def test_amount_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            PaymentConfirmRequest(payment_key="p", order_id="o", amount=-1)

    def test_amount_one_is_valid(self) -> None:
        req = PaymentConfirmRequest(payment_key="p", order_id="o", amount=1)
        assert req.amount == 1

    def test_missing_payment_key_raises(self) -> None:
        with pytest.raises(ValidationError):
            PaymentConfirmRequest(order_id="o", amount=1000)  # type: ignore[call-arg]

    def test_missing_order_id_raises(self) -> None:
        with pytest.raises(ValidationError):
            PaymentConfirmRequest(payment_key="p", amount=1000)  # type: ignore[call-arg]


# ── PaymentCancelRequest ──────────────────────────────────────────────────


class TestPaymentCancelRequest:
    def test_full_cancel_no_amount(self) -> None:
        req = PaymentCancelRequest(payment_key="pay_001", cancel_reason="고객 요청")
        assert req.cancel_amount is None

    def test_partial_cancel_with_amount(self) -> None:
        req = PaymentCancelRequest(
            payment_key="pay_001",
            cancel_reason="부분 환불",
            cancel_amount=20000,
        )
        assert req.cancel_amount == 20000

    def test_cancel_amount_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            PaymentCancelRequest(
                payment_key="p", cancel_reason="test", cancel_amount=0
            )

    def test_cancel_amount_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            PaymentCancelRequest(
                payment_key="p", cancel_reason="test", cancel_amount=-500
            )

    def test_extra_field(self) -> None:
        req = PaymentCancelRequest(
            payment_key="pay_001",
            cancel_reason="고객 요청",
            extra={"total_amount": 50000, "order_id": "order-001"},
        )
        assert req.extra["total_amount"] == 50000

    def test_extra_defaults_to_empty_dict(self) -> None:
        req = PaymentCancelRequest(payment_key="p", cancel_reason="test")
        assert req.extra == {}


# ── PaymentConfirmResult ──────────────────────────────────────────────────


class TestPaymentConfirmResult:
    def test_raw_defaults_to_empty(self) -> None:
        result = PaymentConfirmResult(
            payment_key="pay_001",
            order_id="order-001",
            order_name="상품",
            status=PaymentStatus.DONE,
            method=PaymentMethod.CARD,
            amount=50000,
        )
        assert result.raw == {}
        assert result.approved_at is None

    def test_with_all_fields(self) -> None:
        now = datetime.now(UTC)
        result = PaymentConfirmResult(
            payment_key="pay_001",
            order_id="order-001",
            order_name="상품",
            status=PaymentStatus.DONE,
            method=PaymentMethod.EASY_PAY,
            amount=10000,
            approved_at=now,
            raw={"key": "value"},
        )
        assert result.approved_at == now
        assert result.raw["key"] == "value"
        assert result.method == PaymentMethod.EASY_PAY


# ── PaymentCancelResult ───────────────────────────────────────────────────


class TestPaymentCancelResult:
    def test_partial_cancel_fields(self) -> None:
        now = datetime.now(UTC)
        result = PaymentCancelResult(
            payment_key="pay_001",
            order_id="order-001",
            cancel_amount=20000,
            remaining_amount=30000,
            status=PaymentStatus.PARTIAL_CANCELED,
            canceled_at=now,
        )
        assert result.cancel_amount == 20000
        assert result.remaining_amount == 30000
        assert result.status == PaymentStatus.PARTIAL_CANCELED

    def test_full_cancel_zero_remaining(self) -> None:
        result = PaymentCancelResult(
            payment_key="pay_001",
            order_id="order-001",
            cancel_amount=50000,
            remaining_amount=0,
            status=PaymentStatus.CANCELED,
            canceled_at=datetime.now(UTC),
        )
        assert result.remaining_amount == 0
        assert result.status == PaymentStatus.CANCELED


# ── PaymentQueryResult ────────────────────────────────────────────────────


class TestPaymentQueryResult:
    def test_optional_timestamps_default_none(self) -> None:
        result = PaymentQueryResult(
            payment_key="pay_001",
            order_id="order-001",
            order_name="상품",
            status=PaymentStatus.DONE,
            method=PaymentMethod.CARD,
            amount=50000,
        )
        assert result.approved_at is None
        assert result.canceled_at is None

    def test_all_payment_statuses(self) -> None:
        for status in PaymentStatus:
            result = PaymentQueryResult(
                payment_key="p",
                order_id="o",
                order_name="s",
                status=status,
                method=PaymentMethod.CARD,
                amount=1000,
            )
            assert result.status == status

    def test_all_payment_methods(self) -> None:
        for method in PaymentMethod:
            result = PaymentQueryResult(
                payment_key="p",
                order_id="o",
                order_name="s",
                status=PaymentStatus.DONE,
                method=method,
                amount=1000,
            )
            assert result.method == method
