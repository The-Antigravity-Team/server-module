"""payment.dummy.store.DummyPaymentStore 테스트"""
from datetime import UTC, datetime

import pytest

from payment.core.enums import PaymentMethod, PaymentStatus
from payment.dummy.store import CancelRecord, DummyPaymentStore, PaymentRecord


def _make_record(**overrides) -> PaymentRecord:
    defaults: dict = dict(
        payment_key="pay_001",
        order_id="order-001",
        order_name="테스트 상품",
        provider="toss",
        status=PaymentStatus.DONE,
        method=PaymentMethod.CARD,
        amount=50000,
    )
    return PaymentRecord(**{**defaults, **overrides})


def _make_cancel(payment_id: str, payment_key: str, **overrides) -> CancelRecord:
    defaults: dict = dict(
        payment_id=payment_id,
        payment_key=payment_key,
        cancel_amount=50000,
        cancel_reason="고객 요청",
        canceled_at=datetime.now(UTC),
    )
    return CancelRecord(**{**defaults, **overrides})


# ── PaymentRecord CRUD ────────────────────────────────────────────────────


class TestSaveAndRetrieve:
    @pytest.mark.asyncio
    async def test_save_and_get_by_payment_key(self) -> None:
        store = DummyPaymentStore()
        record = _make_record()
        returned = await store.save_payment(record)

        assert returned is record
        found = await store.get_by_payment_key("pay_001")
        assert found is not None
        assert found.order_id == "order-001"
        assert found.amount == 50000

    @pytest.mark.asyncio
    async def test_get_by_payment_key_not_found(self) -> None:
        store = DummyPaymentStore()
        assert await store.get_by_payment_key("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_by_order_id(self) -> None:
        store = DummyPaymentStore()
        await store.save_payment(_make_record())

        found = await store.get_by_order_id("order-001")
        assert found is not None
        assert found.payment_key == "pay_001"

    @pytest.mark.asyncio
    async def test_get_by_order_id_not_found(self) -> None:
        store = DummyPaymentStore()
        assert await store.get_by_order_id("nonexistent") is None

    @pytest.mark.asyncio
    async def test_overwrite_same_payment_key(self) -> None:
        store = DummyPaymentStore()
        await store.save_payment(_make_record(order_name="원본"))
        await store.save_payment(_make_record(order_name="덮어쓰기"))

        record = await store.get_by_payment_key("pay_001")
        assert record is not None
        assert record.order_name == "덮어쓰기"
        assert len(store.all_payments()) == 1

    @pytest.mark.asyncio
    async def test_multiple_records(self) -> None:
        store = DummyPaymentStore()
        await store.save_payment(_make_record(payment_key="pay_001", order_id="order-001"))
        await store.save_payment(_make_record(payment_key="pay_002", order_id="order-002"))
        await store.save_payment(_make_record(payment_key="pay_003", order_id="order-003"))

        assert len(store.all_payments()) == 3


# ── update_status ─────────────────────────────────────────────────────────


class TestUpdateStatus:
    @pytest.mark.asyncio
    async def test_update_to_canceled(self) -> None:
        store = DummyPaymentStore()
        await store.save_payment(_make_record(status=PaymentStatus.DONE))

        updated = await store.update_status("pay_001", PaymentStatus.CANCELED)

        assert updated is not None
        assert updated.status == PaymentStatus.CANCELED

        # 실제 저장 상태도 변경됐는지 확인
        record = await store.get_by_payment_key("pay_001")
        assert record is not None
        assert record.status == PaymentStatus.CANCELED

    @pytest.mark.asyncio
    async def test_update_to_partial_canceled(self) -> None:
        store = DummyPaymentStore()
        await store.save_payment(_make_record())

        await store.update_status("pay_001", PaymentStatus.PARTIAL_CANCELED)
        record = await store.get_by_payment_key("pay_001")
        assert record is not None
        assert record.status == PaymentStatus.PARTIAL_CANCELED

    @pytest.mark.asyncio
    async def test_update_nonexistent_returns_none(self) -> None:
        store = DummyPaymentStore()
        result = await store.update_status("nonexistent", PaymentStatus.CANCELED)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_preserves_other_fields(self) -> None:
        store = DummyPaymentStore()
        record = _make_record(amount=99000, order_name="보존 확인")
        await store.save_payment(record)

        await store.update_status("pay_001", PaymentStatus.CANCELED)

        updated = await store.get_by_payment_key("pay_001")
        assert updated is not None
        assert updated.amount == 99000
        assert updated.order_name == "보존 확인"


# ── CancelRecord CRUD ─────────────────────────────────────────────────────


class TestCancelRecord:
    @pytest.mark.asyncio
    async def test_save_and_list_cancel(self) -> None:
        store = DummyPaymentStore()
        record = _make_record()
        await store.save_payment(record)

        cancel = _make_cancel(record.id, "pay_001")
        returned = await store.save_cancel(cancel)

        assert returned is cancel
        cancels = await store.list_cancels("pay_001")
        assert len(cancels) == 1
        assert cancels[0].cancel_amount == 50000

    @pytest.mark.asyncio
    async def test_list_cancels_empty(self) -> None:
        store = DummyPaymentStore()
        assert await store.list_cancels("pay_001") == []

    @pytest.mark.asyncio
    async def test_multiple_cancels_for_same_payment(self) -> None:
        """부분 취소가 여러 번 발생한 경우"""
        store = DummyPaymentStore()
        record = _make_record()
        await store.save_payment(record)

        await store.save_cancel(_make_cancel(record.id, "pay_001", cancel_amount=10000))
        await store.save_cancel(_make_cancel(record.id, "pay_001", cancel_amount=15000))

        cancels = await store.list_cancels("pay_001")
        assert len(cancels) == 2
        total_canceled = sum(c.cancel_amount for c in cancels)
        assert total_canceled == 25000

    @pytest.mark.asyncio
    async def test_list_cancels_filters_by_payment_key(self) -> None:
        store = DummyPaymentStore()
        r1 = _make_record(payment_key="pay_001", order_id="order-001")
        r2 = _make_record(payment_key="pay_002", order_id="order-002")
        await store.save_payment(r1)
        await store.save_payment(r2)

        await store.save_cancel(_make_cancel(r1.id, "pay_001", cancel_amount=50000))
        await store.save_cancel(_make_cancel(r2.id, "pay_002", cancel_amount=30000))

        assert len(await store.list_cancels("pay_001")) == 1
        assert len(await store.list_cancels("pay_002")) == 1


# ── all_payments ──────────────────────────────────────────────────────────


class TestAllPayments:
    def test_empty_store(self) -> None:
        assert DummyPaymentStore().all_payments() == []

    @pytest.mark.asyncio
    async def test_returns_snapshot(self) -> None:
        store = DummyPaymentStore()
        await store.save_payment(_make_record(payment_key="pay_001", order_id="order-001"))
        await store.save_payment(_make_record(payment_key="pay_002", order_id="order-002"))

        all_p = store.all_payments()
        assert len(all_p) == 2
        keys = {p.payment_key for p in all_p}
        assert keys == {"pay_001", "pay_002"}
