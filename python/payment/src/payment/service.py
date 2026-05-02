from __future__ import annotations

from payment.core.models import (
    PaymentCancelRequest,
    PaymentCancelResult,
    PaymentConfirmRequest,
    PaymentConfirmResult,
    PaymentQueryResult,
)
from payment.dummy.store import CancelRecord, DummyPaymentStore, PaymentRecord
from payment.registry import ProviderRegistry


class PaymentService:
    """
    외부 진입점.

    store 를 주입하면 승인/취소 결과를 인메모리 더미 저장소에 자동 저장한다.
    실제 서비스에서는 DummyPaymentStore 대신 실제 DB Repository 를 주입한다.

    Usage (FastAPI)::

        registry = ProviderRegistry()
        registry.register(TossPaymentsProvider(TossPaymentsSettings()))

        payment_service = PaymentService(registry)

        @router.post("/confirm")
        async def confirm(body: ConfirmBody):
            return await payment_service.confirm_payment(
                "toss",
                PaymentConfirmRequest(
                    payment_key=body.payment_key,
                    order_id=body.order_id,
                    amount=body.amount,
                ),
            )
    """

    def __init__(
        self,
        registry: ProviderRegistry,
        store: DummyPaymentStore | None = None,
    ) -> None:
        self._registry = registry
        self._store = store

    async def confirm_payment(
        self, provider: str, request: PaymentConfirmRequest
    ) -> PaymentConfirmResult:
        result = await self._registry.get(provider).confirm_payment(request)

        if self._store:
            await self._store.save_payment(
                PaymentRecord(
                    payment_key=result.payment_key,
                    order_id=result.order_id,
                    order_name=result.order_name,
                    provider=provider,
                    status=result.status,
                    method=result.method,
                    amount=result.amount,
                    approved_at=result.approved_at,
                    raw_response=result.raw,
                )
            )

        return result

    async def cancel_payment(
        self, provider: str, request: PaymentCancelRequest
    ) -> PaymentCancelResult:
        result = await self._registry.get(provider).cancel_payment(request)

        if self._store:
            record = await self._store.get_by_payment_key(result.payment_key)
            if record:
                await self._store.update_status(result.payment_key, result.status)
                await self._store.save_cancel(
                    CancelRecord(
                        payment_id=record.id,
                        payment_key=result.payment_key,
                        cancel_amount=result.cancel_amount,
                        cancel_reason=request.cancel_reason,
                        canceled_at=result.canceled_at,
                        raw_response=result.raw,
                    )
                )

        return result

    async def get_payment(
        self, provider: str, payment_key: str
    ) -> PaymentQueryResult:
        return await self._registry.get(provider).get_payment(payment_key)

    async def get_payment_by_order_id(
        self, provider: str, order_id: str
    ) -> PaymentQueryResult:
        return await self._registry.get(provider).get_payment_by_order_id(order_id)
