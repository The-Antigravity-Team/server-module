import pytest
import respx
import httpx

from payment.core.enums import PaymentMethod, PaymentStatus
from payment.core.exceptions import (
    PaymentAmountMismatchError,
    PaymentNotFoundError,
    ProviderAPIError,
)
from payment.core.models import PaymentCancelRequest, PaymentConfirmRequest
from payment.providers.toss import TossPaymentsProvider, TossPaymentsSettings

TOSS_API = "https://api.tosspayments.com/v1"

# ── 샘플 응답 픽스처 ─────────────────────────────────────────────────────

DONE_RESPONSE = {
    "paymentKey": "tviva20230410171218Ygm3r",
    "orderId": "order-001",
    "orderName": "테스트 상품",
    "status": "DONE",
    "method": "카드",
    "totalAmount": 50000,
    "balanceAmount": 50000,
    "requestedAt": "2023-04-10T15:22:18+09:00",
    "approvedAt": "2023-04-10T15:22:24+09:00",
    "card": {
        "amount": 50000,
        "issuerCode": "71",
        "acquirerCode": "71",
        "number": "54320012****323*",
        "installmentPlanMonths": 0,
        "approveNo": "00000000",
        "useCardPoint": False,
        "cardType": "신용",
        "ownerType": "개인",
        "acquireStatus": "READY",
        "isInterestFree": False,
        "interestPayer": None,
    },
    "easyPay": None,
    "virtualAccount": None,
    "mobilePhone": None,
    "cancels": None,
}

CANCELED_RESPONSE = {
    **DONE_RESPONSE,
    "status": "CANCELED",
    "balanceAmount": 0,
    "cancels": [
        {
            "cancelAmount": 50000,
            "cancelReason": "고객 요청",
            "taxFreeAmount": 0,
            "refundableAmount": 0,
            "canceledAt": "2023-04-10T16:00:00+09:00",
            "transactionKey": "cancel-tx-001",
        }
    ],
}

PARTIAL_CANCELED_RESPONSE = {
    **DONE_RESPONSE,
    "status": "PARTIAL_CANCELED",
    "balanceAmount": 30000,
    "cancels": [
        {
            "cancelAmount": 20000,
            "cancelReason": "부분 환불",
            "taxFreeAmount": 0,
            "refundableAmount": 30000,
            "canceledAt": "2023-04-10T16:00:00+09:00",
            "transactionKey": "cancel-tx-002",
        }
    ],
}


@pytest.fixture
def provider() -> TossPaymentsProvider:
    return TossPaymentsProvider(
        TossPaymentsSettings(secret_key="test_sk", client_key="test_ck")
    )


# ── confirm_payment ───────────────────────────────────────────────────────


class TestConfirmPayment:
    @pytest.mark.asyncio
    async def test_success_maps_to_common_model(
        self, provider: TossPaymentsProvider
    ) -> None:
        with respx.mock:
            respx.post(f"{TOSS_API}/payments/confirm").mock(
                return_value=httpx.Response(200, json=DONE_RESPONSE)
            )
            result = await provider.confirm_payment(
                PaymentConfirmRequest(
                    payment_key="tviva20230410171218Ygm3r",
                    order_id="order-001",
                    amount=50000,
                )
            )

        assert result.status == PaymentStatus.DONE
        assert result.method == PaymentMethod.CARD
        assert result.amount == 50000
        assert result.order_id == "order-001"
        assert result.order_name == "테스트 상품"
        assert result.raw == DONE_RESPONSE

    @pytest.mark.asyncio
    async def test_amount_mismatch_raises(self, provider: TossPaymentsProvider) -> None:
        tampered = {**DONE_RESPONSE, "totalAmount": 1000}
        with respx.mock:
            respx.post(f"{TOSS_API}/payments/confirm").mock(
                return_value=httpx.Response(200, json=tampered)
            )
            with pytest.raises(PaymentAmountMismatchError) as exc:
                await provider.confirm_payment(
                    PaymentConfirmRequest(
                        payment_key="tviva20230410171218Ygm3r",
                        order_id="order-001",
                        amount=50000,
                    )
                )

        assert exc.value.expected == 50000
        assert exc.value.actual == 1000

    @pytest.mark.asyncio
    async def test_api_error_raises_provider_api_error(
        self, provider: TossPaymentsProvider
    ) -> None:
        with respx.mock:
            respx.post(f"{TOSS_API}/payments/confirm").mock(
                return_value=httpx.Response(
                    400,
                    json={"code": "INVALID_PAYMENT_KEY", "message": "잘못된 결제 키입니다."},
                )
            )
            with pytest.raises(ProviderAPIError) as exc:
                await provider.confirm_payment(
                    PaymentConfirmRequest(
                        payment_key="invalid",
                        order_id="order-001",
                        amount=50000,
                    )
                )

        assert exc.value.error_code == "INVALID_PAYMENT_KEY"
        assert exc.value.status_code == 400


# ── cancel_payment ────────────────────────────────────────────────────────


class TestCancelPayment:
    @pytest.mark.asyncio
    async def test_full_cancel(self, provider: TossPaymentsProvider) -> None:
        with respx.mock:
            respx.post(
                f"{TOSS_API}/payments/tviva20230410171218Ygm3r/cancel"
            ).mock(return_value=httpx.Response(200, json=CANCELED_RESPONSE))
            result = await provider.cancel_payment(
                PaymentCancelRequest(
                    payment_key="tviva20230410171218Ygm3r",
                    cancel_reason="고객 요청",
                )
            )

        assert result.status == PaymentStatus.CANCELED
        assert result.cancel_amount == 50000
        assert result.remaining_amount == 0

    @pytest.mark.asyncio
    async def test_partial_cancel(self, provider: TossPaymentsProvider) -> None:
        with respx.mock:
            respx.post(
                f"{TOSS_API}/payments/tviva20230410171218Ygm3r/cancel"
            ).mock(return_value=httpx.Response(200, json=PARTIAL_CANCELED_RESPONSE))
            result = await provider.cancel_payment(
                PaymentCancelRequest(
                    payment_key="tviva20230410171218Ygm3r",
                    cancel_reason="부분 환불",
                    cancel_amount=20000,
                )
            )

        assert result.status == PaymentStatus.PARTIAL_CANCELED
        assert result.cancel_amount == 20000
        assert result.remaining_amount == 30000


# ── get_payment ───────────────────────────────────────────────────────────


class TestGetPayment:
    @pytest.mark.asyncio
    async def test_get_by_payment_key(self, provider: TossPaymentsProvider) -> None:
        with respx.mock:
            respx.get(
                f"{TOSS_API}/payments/tviva20230410171218Ygm3r"
            ).mock(return_value=httpx.Response(200, json=DONE_RESPONSE))
            result = await provider.get_payment("tviva20230410171218Ygm3r")

        assert result.payment_key == "tviva20230410171218Ygm3r"
        assert result.status == PaymentStatus.DONE

    @pytest.mark.asyncio
    async def test_get_by_order_id(self, provider: TossPaymentsProvider) -> None:
        with respx.mock:
            respx.get(
                f"{TOSS_API}/payments/orders/order-001"
            ).mock(return_value=httpx.Response(200, json=DONE_RESPONSE))
            result = await provider.get_payment_by_order_id("order-001")

        assert result.order_id == "order-001"

    @pytest.mark.asyncio
    async def test_not_found_raises(self, provider: TossPaymentsProvider) -> None:
        with respx.mock:
            respx.get(f"{TOSS_API}/payments/nonexistent").mock(
                return_value=httpx.Response(
                    404,
                    json={"code": "NOT_FOUND_PAYMENT", "message": "존재하지 않는 결제입니다."},
                )
            )
            with pytest.raises(PaymentNotFoundError):
                await provider.get_payment("nonexistent")
