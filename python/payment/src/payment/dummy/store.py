"""
개발/테스트용 인메모리 저장소.

PaymentRecord, CancelRecord 는 실제 DB 테이블 스키마의 참고 형태이다.
실제 프로젝트에서는 이 모델을 SQLAlchemy / SQLModel / Tortoise ORM 등으로 매핑한다.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from payment.core.enums import PaymentMethod, PaymentStatus


# ── DB 레코드 모델 (스키마 참고용) ─────────────────────────────────────────


class PaymentRecord(BaseModel):
    """payments 테이블

    Columns
    -------
    id              PK, UUID
    payment_key     PG사 결제 키 (unique)
    order_id        주문 ID (unique)
    order_name      주문명
    provider        PG사 식별자 ("toss" | "kakao" | ...)
    status          결제 상태
    method          결제 수단
    amount          결제 금액 (원)
    approved_at     승인 시각
    created_at      레코드 생성 시각
    updated_at      레코드 수정 시각
    raw_response    PG사 원본 응답 (JSON)
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payment_key: str
    order_id: str
    order_name: str
    provider: str
    status: PaymentStatus
    method: PaymentMethod
    amount: int
    approved_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_response: dict = Field(default_factory=dict)


class CancelRecord(BaseModel):
    """payment_cancels 테이블

    Columns
    -------
    id              PK, UUID
    payment_id      payments.id FK
    payment_key     PG사 결제 키
    cancel_amount   취소 금액
    cancel_reason   취소 사유
    canceled_at     취소 시각
    raw_response    PG사 원본 응답 (JSON)
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payment_id: str
    payment_key: str
    cancel_amount: int
    cancel_reason: str
    canceled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_response: dict = Field(default_factory=dict)


# ── 인메모리 저장소 ────────────────────────────────────────────────────────


class DummyPaymentStore:
    """개발·테스트용 인메모리 저장소 — 실제 DB Repository 인터페이스 참고용"""

    def __init__(self) -> None:
        self._payments: dict[str, PaymentRecord] = {}  # payment_key → record
        self._cancels: list[CancelRecord] = []

    async def save_payment(self, record: PaymentRecord) -> PaymentRecord:
        self._payments[record.payment_key] = record
        return record

    async def get_by_payment_key(self, payment_key: str) -> PaymentRecord | None:
        return self._payments.get(payment_key)

    async def get_by_order_id(self, order_id: str) -> PaymentRecord | None:
        return next(
            (r for r in self._payments.values() if r.order_id == order_id),
            None,
        )

    async def update_status(
        self, payment_key: str, status: PaymentStatus
    ) -> PaymentRecord | None:
        record = self._payments.get(payment_key)
        if record is None:
            return None
        updated = record.model_copy(
            update={"status": status, "updated_at": datetime.now(UTC)}
        )
        self._payments[payment_key] = updated
        return updated

    async def save_cancel(self, record: CancelRecord) -> CancelRecord:
        self._cancels.append(record)
        return record

    async def list_cancels(self, payment_key: str) -> list[CancelRecord]:
        return [c for c in self._cancels if c.payment_key == payment_key]

    def all_payments(self) -> list[PaymentRecord]:
        return list(self._payments.values())
