"""Stripe API 응답 Pydantic 모델 — Stripe API 2024-06-20 기준"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StripeMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")  # 사용자 정의 메타데이터 필드 허용

    order_id: str | None = None
    order_name: str | None = None


class StripePaymentIntentResponse(BaseModel):
    """GET /v1/payment_intents/{id}  또는  POST .../confirm 응답"""

    model_config = ConfigDict(populate_by_name=True)

    id: str                                         # "pi_3Nxxx..."
    object: str = "payment_intent"
    amount: int                                     # 최소 화폐 단위 (KRW = 원)
    amount_received: int = 0
    currency: str
    status: str                                     # "succeeded" | "canceled" | "processing" | ...
    payment_method_types: list[str] = Field(default_factory=list)   # ["card", "alipay", ...]
    metadata: StripeMetadata = Field(default_factory=StripeMetadata)
    created: int                                    # Unix timestamp
    description: str | None = None
    client_secret: str | None = None


class StripeRefundResponse(BaseModel):
    """POST /v1/refunds 응답"""

    model_config = ConfigDict(populate_by_name=True)

    id: str                             # "re_3Nxxx..."
    object: str = "refund"
    amount: int
    payment_intent: str
    status: str                         # "succeeded" | "pending" | "failed"
    created: int
    reason: str | None = None
    currency: str


class StripeListResponse(BaseModel):
    """GET /v1/payment_intents (목록 조회) 응답"""

    object: str = "list"
    data: list[StripePaymentIntentResponse] = Field(default_factory=list)
    has_more: bool = False
