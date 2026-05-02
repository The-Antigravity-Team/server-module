import pytest
import respx
import httpx

from payment.core.enums import PaymentMethod, PaymentStatus
from payment.core.exceptions import (
    PaymentAmountMismatchError,
    PaymentConfirmError,
    PaymentNotFoundError,
    ProviderAPIError,
)
from payment.core.models import PaymentCancelRequest, PaymentConfirmRequest
from payment.providers.stripe import StripeProvider, StripeSettings

STRIPE_API = "https://api.stripe.com/v1"

# ── 샘플 응답 ────────────────────────────────────────────────────────────

PI_SUCCEEDED = {
    "id": "pi_3NxxxxxxxxxX1X2X3",
    "object": "payment_intent",
    "amount": 50000,
    "amount_received": 50000,
    "currency": "krw",
    "status": "succeeded",
    "payment_method": "pm_xxx",
    "payment_method_types": ["card"],
    "metadata": {
        "order_id": "order-001",
        "order_name": "테스트 상품",
    },
    "created": 1696931734,
    "description": "테스트 상품",
    "client_secret": "pi_3Nxxx_secret_xxx",
}

PI_PROCESSING = {
    **PI_SUCCEEDED,
    "status": "processing",
    "amount_received": 0,
}

PI_CANCELED = {
    **PI_SUCCEEDED,
    "status": "canceled",
}

REFUND_FULL = {
    "id": "re_3NxxxxxxxxxX1Y2Z3",
    "object": "refund",
    "amount": 50000,
    "payment_intent": "pi_3NxxxxxxxxxX1X2X3",
    "status": "succeeded",
    "created": 1696932000,
    "reason": "requested_by_customer",
    "currency": "krw",
}

REFUND_PARTIAL = {
    **REFUND_FULL,
    "id": "re_3NxxxxxxxxxX1A2B3",
    "amount": 20000,
}

PI_LIST_RESPONSE = {
    "object": "list",
    "data": [PI_SUCCEEDED],
    "has_more": False,
}

PI_LIST_EMPTY = {
    "object": "list",
    "data": [],
    "has_more": False,
}

STRIPE_CARD_ERROR = {
    "error": {
        "code": "card_declined",
        "decline_code": "insufficient_funds",
        "message": "Your card has insufficient funds.",
        "type": "card_error",
    }
}

STRIPE_NOT_FOUND_ERROR = {
    "error": {
        "code": "resource_missing",
        "message": "No such payment_intent: 'pi_nonexistent'",
        "type": "invalid_request_error",
    }
}


@pytest.fixture
def provider() -> StripeProvider:
    return StripeProvider(StripeSettings(secret_key="sk_test_xxxx", currency="krw"))


# ── confirm_payment (retrieve 방식) ─────────────────────────────────────


class TestConfirmPaymentRetrieve:
    """클라이언트에서 Stripe.js로 결제 완료 → 서버가 PI 조회·검증하는 흐름"""

    @pytest.mark.asyncio
    async def test_success_maps_to_common_model(self, provider: StripeProvider) -> None:
        with respx.mock:
            respx.get(
                f"{STRIPE_API}/payment_intents/pi_3NxxxxxxxxxX1X2X3"
            ).mock(return_value=httpx.Response(200, json=PI_SUCCEEDED))
            result = await provider.confirm_payment(
                PaymentConfirmRequest(
                    payment_key="pi_3NxxxxxxxxxX1X2X3",
                    order_id="order-001",
                    amount=50000,
                )
            )

        assert result.status == PaymentStatus.DONE
        assert result.method == PaymentMethod.CARD
        assert result.amount == 50000
        assert result.payment_key == "pi_3NxxxxxxxxxX1X2X3"
        assert result.order_id == "order-001"
        assert result.order_name == "테스트 상품"
        assert result.approved_at is not None

    @pytest.mark.asyncio
    async def test_not_succeeded_raises_confirm_error(
        self, provider: StripeProvider
    ) -> None:
        with respx.mock:
            respx.get(
                f"{STRIPE_API}/payment_intents/pi_3NxxxxxxxxxX1X2X3"
            ).mock(return_value=httpx.Response(200, json=PI_PROCESSING))
            with pytest.raises(PaymentConfirmError) as exc:
                await provider.confirm_payment(
                    PaymentConfirmRequest(
                        payment_key="pi_3NxxxxxxxxxX1X2X3",
                        order_id="order-001",
                        amount=50000,
                    )
                )

        assert "processing" in str(exc.value)

    @pytest.mark.asyncio
    async def test_amount_mismatch_raises(self, provider: StripeProvider) -> None:
        with respx.mock:
            respx.get(
                f"{STRIPE_API}/payment_intents/pi_3NxxxxxxxxxX1X2X3"
            ).mock(return_value=httpx.Response(200, json=PI_SUCCEEDED))
            with pytest.raises(PaymentAmountMismatchError) as exc:
                await provider.confirm_payment(
                    PaymentConfirmRequest(
                        payment_key="pi_3NxxxxxxxxxX1X2X3",
                        order_id="order-001",
                        amount=99999,   # 위변조
                    )
                )

        assert exc.value.expected == 99999
        assert exc.value.actual == 50000

    @pytest.mark.asyncio
    async def test_not_found_raises(self, provider: StripeProvider) -> None:
        with respx.mock:
            respx.get(f"{STRIPE_API}/payment_intents/pi_nonexistent").mock(
                return_value=httpx.Response(404, json=STRIPE_NOT_FOUND_ERROR)
            )
            with pytest.raises(PaymentNotFoundError):
                await provider.confirm_payment(
                    PaymentConfirmRequest(
                        payment_key="pi_nonexistent",
                        order_id="order-001",
                        amount=50000,
                    )
                )


# ── confirm_payment (server-side confirm 방식) ───────────────────────────


class TestConfirmPaymentServerSide:
    """extra={"payment_method": "pm_xxx"} → 서버가 직접 PI confirm 호출하는 흐름"""

    @pytest.mark.asyncio
    async def test_server_confirm_success(self, provider: StripeProvider) -> None:
        with respx.mock:
            respx.post(
                f"{STRIPE_API}/payment_intents/pi_3NxxxxxxxxxX1X2X3/confirm"
            ).mock(return_value=httpx.Response(200, json=PI_SUCCEEDED))
            result = await provider.confirm_payment(
                PaymentConfirmRequest(
                    payment_key="pi_3NxxxxxxxxxX1X2X3",
                    order_id="order-001",
                    amount=50000,
                    extra={"payment_method": "pm_xxx"},
                )
            )

        assert result.status == PaymentStatus.DONE

    @pytest.mark.asyncio
    async def test_card_declined_raises_provider_api_error(
        self, provider: StripeProvider
    ) -> None:
        with respx.mock:
            respx.post(
                f"{STRIPE_API}/payment_intents/pi_3NxxxxxxxxxX1X2X3/confirm"
            ).mock(return_value=httpx.Response(402, json=STRIPE_CARD_ERROR))
            with pytest.raises(ProviderAPIError) as exc:
                await provider.confirm_payment(
                    PaymentConfirmRequest(
                        payment_key="pi_3NxxxxxxxxxX1X2X3",
                        order_id="order-001",
                        amount=50000,
                        extra={"payment_method": "pm_declined"},
                    )
                )

        assert exc.value.error_code == "card_declined"


# ── cancel_payment (환불) ─────────────────────────────────────────────────


class TestCancelPayment:
    @pytest.mark.asyncio
    async def test_full_refund(self, provider: StripeProvider) -> None:
        with respx.mock:
            respx.post(f"{STRIPE_API}/refunds").mock(
                return_value=httpx.Response(200, json=REFUND_FULL)
            )
            result = await provider.cancel_payment(
                PaymentCancelRequest(
                    payment_key="pi_3NxxxxxxxxxX1X2X3",
                    cancel_reason="고객 요청",
                    extra={"total_amount": 50000, "order_id": "order-001"},
                )
            )

        assert result.status == PaymentStatus.CANCELED
        assert result.cancel_amount == 50000
        assert result.remaining_amount == 0

    @pytest.mark.asyncio
    async def test_partial_refund(self, provider: StripeProvider) -> None:
        with respx.mock:
            respx.post(f"{STRIPE_API}/refunds").mock(
                return_value=httpx.Response(200, json=REFUND_PARTIAL)
            )
            result = await provider.cancel_payment(
                PaymentCancelRequest(
                    payment_key="pi_3NxxxxxxxxxX1X2X3",
                    cancel_reason="부분 환불",
                    cancel_amount=20000,
                    extra={"total_amount": 50000, "order_id": "order-001"},
                )
            )

        assert result.status == PaymentStatus.PARTIAL_CANCELED
        assert result.cancel_amount == 20000
        assert result.remaining_amount == 30000

    @pytest.mark.asyncio
    async def test_cancel_reason_fraud_maps_correctly(
        self, provider: StripeProvider
    ) -> None:
        """사기 사유 → Stripe 'fraudulent' reason"""
        captured_data: dict = {}

        def capture_request(request: httpx.Request) -> httpx.Response:
            import urllib.parse
            captured_data.update(urllib.parse.parse_qs(request.content.decode()))
            return httpx.Response(200, json=REFUND_FULL)

        with respx.mock:
            respx.post(f"{STRIPE_API}/refunds").mock(side_effect=capture_request)
            await provider.cancel_payment(
                PaymentCancelRequest(
                    payment_key="pi_3NxxxxxxxxxX1X2X3",
                    cancel_reason="사기 의심",
                    extra={"total_amount": 50000},
                )
            )

        assert captured_data.get("reason") == ["fraudulent"]


# ── get_payment ───────────────────────────────────────────────────────────


class TestGetPayment:
    @pytest.mark.asyncio
    async def test_get_by_payment_key(self, provider: StripeProvider) -> None:
        with respx.mock:
            respx.get(
                f"{STRIPE_API}/payment_intents/pi_3NxxxxxxxxxX1X2X3"
            ).mock(return_value=httpx.Response(200, json=PI_SUCCEEDED))
            result = await provider.get_payment("pi_3NxxxxxxxxxX1X2X3")

        assert result.status == PaymentStatus.DONE
        assert result.payment_key == "pi_3NxxxxxxxxxX1X2X3"
        assert result.order_id == "order-001"

    @pytest.mark.asyncio
    async def test_get_by_order_id(self, provider: StripeProvider) -> None:
        with respx.mock:
            respx.get(f"{STRIPE_API}/payment_intents").mock(
                return_value=httpx.Response(200, json=PI_LIST_RESPONSE)
            )
            result = await provider.get_payment_by_order_id("order-001")

        assert result.order_id == "order-001"
        assert result.status == PaymentStatus.DONE

    @pytest.mark.asyncio
    async def test_get_by_order_id_not_found_raises(
        self, provider: StripeProvider
    ) -> None:
        with respx.mock:
            respx.get(f"{STRIPE_API}/payment_intents").mock(
                return_value=httpx.Response(200, json=PI_LIST_EMPTY)
            )
            with pytest.raises(PaymentNotFoundError):
                await provider.get_payment_by_order_id("order-nonexistent")

    @pytest.mark.asyncio
    async def test_canceled_pi_maps_status(self, provider: StripeProvider) -> None:
        with respx.mock:
            respx.get(
                f"{STRIPE_API}/payment_intents/pi_3NxxxxxxxxxX1X2X3"
            ).mock(return_value=httpx.Response(200, json=PI_CANCELED))
            result = await provider.get_payment("pi_3NxxxxxxxxxX1X2X3")

        assert result.status == PaymentStatus.CANCELED
