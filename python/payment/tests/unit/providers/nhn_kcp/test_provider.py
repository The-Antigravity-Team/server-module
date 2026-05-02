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
from payment.providers.nhn_kcp import NHNKCPProvider, NHNKCPSettings

KCP_API = "https://api.kcp.co.kr/v1"

# ── 샘플 응답 ────────────────────────────────────────────────────────────

CONFIRM_RESPONSE = {
    "res_cd": "0000",
    "res_msg": "정상처리",
    "tno": "KCP20230410A1B2C3",
    "amount": 50000,
    "pay_method": "CARD",
    "ordr_idxx": "order-001",
    "good_name": "테스트 상품",
    "approve_no": "12345678",
    "card_no": "1234****5678",
    "noinf": "0",
    "quota": "00",
    "van_appro_date": "20230410",
    "van_appro_time": "152224",
}

CANCEL_FULL_RESPONSE = {
    "res_cd": "0000",
    "res_msg": "정상처리",
    "tno": "KCP20230410A1B2C3",
    "mod_mny": 50000,
    "rem_mny": 0,
    "mod_date": "20230410",
    "mod_time": "160000",
}

CANCEL_PARTIAL_RESPONSE = {
    "res_cd": "0000",
    "res_msg": "정상처리",
    "tno": "KCP20230410A1B2C3",
    "mod_mny": 20000,
    "rem_mny": 30000,
    "mod_date": "20230410",
    "mod_time": "160000",
}

QUERY_DONE_RESPONSE = {
    "res_cd": "0000",
    "res_msg": "정상처리",
    "tno": "KCP20230410A1B2C3",
    "amount": 50000,
    "pay_method": "CARD",
    "ordr_idxx": "order-001",
    "good_name": "테스트 상품",
    "cancel_yn": "N",
    "part_cancel_yn": "N",
    "van_appro_date": "20230410",
    "van_appro_time": "152224",
}

QUERY_CANCELED_RESPONSE = {
    **QUERY_DONE_RESPONSE,
    "cancel_yn": "Y",
    "part_cancel_yn": "N",
    "mod_date": "20230410",
    "mod_time": "160000",
}

QUERY_PARTIAL_CANCELED_RESPONSE = {
    **QUERY_DONE_RESPONSE,
    "cancel_yn": "Y",
    "part_cancel_yn": "Y",
    "mod_date": "20230410",
    "mod_time": "160000",
}

KCP_ERROR_RESPONSE = {
    "res_cd": "8101",
    "res_msg": "인증 실패",
}

KCP_NOT_FOUND_RESPONSE = {
    "res_cd": "8131",
    "res_msg": "존재하지 않는 거래입니다.",
}


@pytest.fixture
def provider() -> NHNKCPProvider:
    return NHNKCPProvider(
        NHNKCPSettings(site_cd="T0000", site_key="test_site_key")
    )


# ── confirm_payment ───────────────────────────────────────────────────────


class TestConfirmPayment:
    @pytest.mark.asyncio
    async def test_success_maps_to_common_model(
        self, provider: NHNKCPProvider
    ) -> None:
        with respx.mock:
            respx.post(f"{KCP_API}/payment").mock(
                return_value=httpx.Response(200, json=CONFIRM_RESPONSE)
            )
            result = await provider.confirm_payment(
                PaymentConfirmRequest(
                    payment_key="KCP20230410A1B2C3",
                    order_id="order-001",
                    amount=50000,
                    extra={
                        "enc_data": "encrypted_data",
                        "enc_info": "encrypted_info",
                        "pay_method": "CARD",
                        "good_name": "테스트 상품",
                    },
                )
            )

        assert result.status == PaymentStatus.DONE
        assert result.method == PaymentMethod.CARD
        assert result.amount == 50000
        assert result.payment_key == "KCP20230410A1B2C3"
        assert result.order_id == "order-001"

    @pytest.mark.asyncio
    async def test_amount_mismatch_raises(self, provider: NHNKCPProvider) -> None:
        tampered = {**CONFIRM_RESPONSE, "amount": 1000}
        with respx.mock:
            respx.post(f"{KCP_API}/payment").mock(
                return_value=httpx.Response(200, json=tampered)
            )
            with pytest.raises(PaymentAmountMismatchError) as exc:
                await provider.confirm_payment(
                    PaymentConfirmRequest(
                        payment_key="KCP20230410A1B2C3",
                        order_id="order-001",
                        amount=50000,
                        extra={"enc_data": "d", "enc_info": "i"},
                    )
                )

        assert exc.value.expected == 50000
        assert exc.value.actual == 1000

    @pytest.mark.asyncio
    async def test_kcp_error_code_raises_provider_api_error(
        self, provider: NHNKCPProvider
    ) -> None:
        with respx.mock:
            respx.post(f"{KCP_API}/payment").mock(
                return_value=httpx.Response(200, json=KCP_ERROR_RESPONSE)
            )
            with pytest.raises(ProviderAPIError) as exc:
                await provider.confirm_payment(
                    PaymentConfirmRequest(
                        payment_key="KCP20230410A1B2C3",
                        order_id="order-001",
                        amount=50000,
                        extra={"enc_data": "d", "enc_info": "i"},
                    )
                )

        assert exc.value.error_code == "8101"

    @pytest.mark.asyncio
    async def test_http_error_raises_provider_api_error(
        self, provider: NHNKCPProvider
    ) -> None:
        with respx.mock:
            respx.post(f"{KCP_API}/payment").mock(
                return_value=httpx.Response(
                    500, json={"res_cd": "9999", "res_msg": "내부 서버 오류"}
                )
            )
            with pytest.raises(ProviderAPIError) as exc:
                await provider.confirm_payment(
                    PaymentConfirmRequest(
                        payment_key="KCP20230410A1B2C3",
                        order_id="order-001",
                        amount=50000,
                        extra={"enc_data": "d", "enc_info": "i"},
                    )
                )

        assert exc.value.status_code == 500


# ── cancel_payment ────────────────────────────────────────────────────────


class TestCancelPayment:
    @pytest.mark.asyncio
    async def test_full_cancel(self, provider: NHNKCPProvider) -> None:
        with respx.mock:
            respx.post(f"{KCP_API}/payment/cancel").mock(
                return_value=httpx.Response(200, json=CANCEL_FULL_RESPONSE)
            )
            result = await provider.cancel_payment(
                PaymentCancelRequest(
                    payment_key="KCP20230410A1B2C3",
                    cancel_reason="고객 요청",
                    extra={"total_amount": 50000},
                )
            )

        assert result.status == PaymentStatus.CANCELED
        assert result.cancel_amount == 50000
        assert result.remaining_amount == 0

    @pytest.mark.asyncio
    async def test_partial_cancel(self, provider: NHNKCPProvider) -> None:
        with respx.mock:
            respx.post(f"{KCP_API}/payment/cancel").mock(
                return_value=httpx.Response(200, json=CANCEL_PARTIAL_RESPONSE)
            )
            result = await provider.cancel_payment(
                PaymentCancelRequest(
                    payment_key="KCP20230410A1B2C3",
                    cancel_reason="부분 환불",
                    cancel_amount=20000,
                    extra={"total_amount": 50000},
                )
            )

        assert result.status == PaymentStatus.PARTIAL_CANCELED
        assert result.cancel_amount == 20000
        assert result.remaining_amount == 30000


# ── get_payment ───────────────────────────────────────────────────────────


class TestGetPayment:
    @pytest.mark.asyncio
    async def test_get_done_payment(self, provider: NHNKCPProvider) -> None:
        with respx.mock:
            respx.get(f"{KCP_API}/payment/KCP20230410A1B2C3").mock(
                return_value=httpx.Response(200, json=QUERY_DONE_RESPONSE)
            )
            result = await provider.get_payment("KCP20230410A1B2C3")

        assert result.status == PaymentStatus.DONE
        assert result.amount == 50000
        assert result.canceled_at is None

    @pytest.mark.asyncio
    async def test_get_canceled_payment(self, provider: NHNKCPProvider) -> None:
        with respx.mock:
            respx.get(f"{KCP_API}/payment/KCP20230410A1B2C3").mock(
                return_value=httpx.Response(200, json=QUERY_CANCELED_RESPONSE)
            )
            result = await provider.get_payment("KCP20230410A1B2C3")

        assert result.status == PaymentStatus.CANCELED
        assert result.canceled_at is not None

    @pytest.mark.asyncio
    async def test_get_partial_canceled_payment(self, provider: NHNKCPProvider) -> None:
        with respx.mock:
            respx.get(f"{KCP_API}/payment/KCP20230410A1B2C3").mock(
                return_value=httpx.Response(200, json=QUERY_PARTIAL_CANCELED_RESPONSE)
            )
            result = await provider.get_payment("KCP20230410A1B2C3")

        assert result.status == PaymentStatus.PARTIAL_CANCELED

    @pytest.mark.asyncio
    async def test_get_by_order_id(self, provider: NHNKCPProvider) -> None:
        with respx.mock:
            respx.get(f"{KCP_API}/payment").mock(
                return_value=httpx.Response(200, json=QUERY_DONE_RESPONSE)
            )
            result = await provider.get_payment_by_order_id("order-001")

        assert result.order_id == "order-001"

    @pytest.mark.asyncio
    async def test_not_found_raises(self, provider: NHNKCPProvider) -> None:
        with respx.mock:
            respx.get(f"{KCP_API}/payment/nonexistent").mock(
                return_value=httpx.Response(200, json=KCP_NOT_FOUND_RESPONSE)
            )
            with pytest.raises(PaymentNotFoundError):
                await provider.get_payment("nonexistent")
