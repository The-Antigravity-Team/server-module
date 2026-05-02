from abc import ABC, abstractmethod

from .models import (
    PaymentCancelRequest,
    PaymentCancelResult,
    PaymentConfirmRequest,
    PaymentConfirmResult,
    PaymentQueryResult,
)


class BasePaymentProvider(ABC):
    provider_name: str

    @abstractmethod
    async def confirm_payment(self, request: PaymentConfirmRequest) -> PaymentConfirmResult:
        """결제 승인"""

    @abstractmethod
    async def cancel_payment(self, request: PaymentCancelRequest) -> PaymentCancelResult:
        """결제 취소 (cancel_amount=None 이면 전액 취소)"""

    @abstractmethod
    async def get_payment(self, payment_key: str) -> PaymentQueryResult:
        """paymentKey 로 결제 조회"""

    @abstractmethod
    async def get_payment_by_order_id(self, order_id: str) -> PaymentQueryResult:
        """orderId 로 결제 조회"""
