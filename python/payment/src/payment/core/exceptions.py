class PaymentError(Exception):
    """결제 서비스 최상위 예외"""


class PaymentConfirmError(PaymentError):
    """결제 승인 실패"""


class PaymentCancelError(PaymentError):
    """결제 취소 실패"""


class PaymentNotFoundError(PaymentError):
    """결제 정보 없음"""


class PaymentAmountMismatchError(PaymentError):
    """금액 위변조 감지"""

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(f"Amount mismatch: expected={expected}, actual={actual}")
        self.expected = expected
        self.actual = actual


class ProviderAPIError(PaymentError):
    """PG사 API 오류"""

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(f"[{error_code}] {message} (HTTP {status_code})")
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
