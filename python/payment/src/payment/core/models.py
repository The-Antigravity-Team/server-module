from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .enums import PaymentMethod, PaymentStatus


class PaymentConfirmRequest(BaseModel):
    payment_key: str
    order_id: str
    amount: int = Field(gt=0)
    extra: dict = Field(default_factory=dict)  # PG사별 추가 파라미터 (예: KCP enc_data)


class PaymentCancelRequest(BaseModel):
    payment_key: str
    cancel_reason: str
    cancel_amount: int | None = Field(default=None, gt=0)  # None = 전액 취소
    extra: dict = Field(default_factory=dict)  # PG사별 추가 파라미터 (예: KCP total_amount)


class PaymentConfirmResult(BaseModel):
    payment_key: str
    order_id: str
    order_name: str
    status: PaymentStatus
    method: PaymentMethod
    amount: int
    approved_at: datetime | None = None
    raw: dict = Field(default_factory=dict)


class PaymentCancelResult(BaseModel):
    payment_key: str
    order_id: str
    cancel_amount: int
    remaining_amount: int
    status: PaymentStatus
    canceled_at: datetime
    raw: dict = Field(default_factory=dict)


class PaymentQueryResult(BaseModel):
    payment_key: str
    order_id: str
    order_name: str
    status: PaymentStatus
    method: PaymentMethod
    amount: int
    approved_at: datetime | None = None
    canceled_at: datetime | None = None
    raw: dict = Field(default_factory=dict)
