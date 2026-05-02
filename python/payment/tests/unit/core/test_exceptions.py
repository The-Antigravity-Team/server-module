"""payment.core.exceptions 테스트"""
import pytest

from payment.core.exceptions import (
    PaymentAmountMismatchError,
    PaymentCancelError,
    PaymentConfirmError,
    PaymentError,
    PaymentNotFoundError,
    ProviderAPIError,
)


# ── 예외 계층 구조 ────────────────────────────────────────────────────────


class TestExceptionHierarchy:
    def test_confirm_error_is_payment_error(self) -> None:
        assert issubclass(PaymentConfirmError, PaymentError)

    def test_cancel_error_is_payment_error(self) -> None:
        assert issubclass(PaymentCancelError, PaymentError)

    def test_not_found_is_payment_error(self) -> None:
        assert issubclass(PaymentNotFoundError, PaymentError)

    def test_amount_mismatch_is_payment_error(self) -> None:
        assert issubclass(PaymentAmountMismatchError, PaymentError)

    def test_provider_api_error_is_payment_error(self) -> None:
        assert issubclass(ProviderAPIError, PaymentError)

    def test_all_catchable_as_payment_error(self) -> None:
        errors = [
            PaymentConfirmError("confirm fail"),
            PaymentCancelError("cancel fail"),
            PaymentNotFoundError("not found"),
            PaymentAmountMismatchError(50000, 1000),
            ProviderAPIError(400, "ERR", "bad request"),
        ]
        for err in errors:
            with pytest.raises(PaymentError):
                raise err


# ── PaymentAmountMismatchError ────────────────────────────────────────────


class TestPaymentAmountMismatchError:
    def test_attributes(self) -> None:
        err = PaymentAmountMismatchError(expected=50000, actual=1000)
        assert err.expected == 50000
        assert err.actual == 1000

    def test_message_contains_both_amounts(self) -> None:
        err = PaymentAmountMismatchError(expected=50000, actual=1000)
        assert "50000" in str(err)
        assert "1000" in str(err)

    def test_zero_actual_is_valid(self) -> None:
        err = PaymentAmountMismatchError(expected=100, actual=0)
        assert err.actual == 0


# ── ProviderAPIError ──────────────────────────────────────────────────────


class TestProviderAPIError:
    def test_attributes(self) -> None:
        err = ProviderAPIError(
            status_code=400,
            error_code="INVALID_PAYMENT_KEY",
            message="잘못된 결제 키입니다.",
        )
        assert err.status_code == 400
        assert err.error_code == "INVALID_PAYMENT_KEY"
        assert err.message == "잘못된 결제 키입니다."

    def test_message_contains_code_and_status(self) -> None:
        err = ProviderAPIError(400, "INVALID_PAYMENT_KEY", "잘못된 결제 키입니다.")
        msg = str(err)
        assert "INVALID_PAYMENT_KEY" in msg
        assert "400" in msg

    def test_500_status_code(self) -> None:
        err = ProviderAPIError(500, "INTERNAL_ERROR", "서버 오류")
        assert err.status_code == 500


# ── PaymentNotFoundError ──────────────────────────────────────────────────


class TestPaymentNotFoundError:
    def test_message(self) -> None:
        err = PaymentNotFoundError("pi_xxx 결제를 찾을 수 없습니다.")
        assert "pi_xxx" in str(err)

    def test_is_exception(self) -> None:
        with pytest.raises(PaymentNotFoundError):
            raise PaymentNotFoundError("not found")
