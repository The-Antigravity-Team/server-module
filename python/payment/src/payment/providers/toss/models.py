"""TossPayments API 응답 Pydantic 모델 — 공식 API 스펙 기준"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TossCardInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    amount: int
    issuer_code: str = Field(alias="issuerCode")
    acquirer_code: str | None = Field(None, alias="acquirerCode")
    number: str
    installment_plan_months: int = Field(alias="installmentPlanMonths")
    approve_no: str = Field(alias="approveNo")
    use_card_point: bool = Field(alias="useCardPoint")
    card_type: str = Field(alias="cardType")       # "신용" | "체크" | "기프트" | "미확인"
    owner_type: str = Field(alias="ownerType")     # "개인" | "법인" | "미확인"
    acquire_status: str = Field(alias="acquireStatus")
    is_interest_free: bool = Field(alias="isInterestFree")
    interest_payer: str | None = Field(None, alias="interestPayer")


class TossEasyPayInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider: str
    amount: int
    discount_amount: int = Field(alias="discountAmount")


class TossVirtualAccountInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    account_type: str = Field(alias="accountType")
    account_number: str = Field(alias="accountNumber")
    bank_code: str = Field(alias="bankCode")
    customer_name: str = Field(alias="customerName")
    due_date: datetime = Field(alias="dueDate")
    refund_status: str = Field(alias="refundStatus")
    expired: bool
    settlement_status: str = Field(alias="settlementStatus")


class TossMobilePhoneInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    customer_mobile_phone: str = Field(alias="customerMobilePhone")
    settlement_status: str = Field(alias="settlementStatus")
    receipt_url: str = Field(alias="receiptUrl")


class TossCancelInfo(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cancel_amount: int = Field(alias="cancelAmount")
    cancel_reason: str = Field(alias="cancelReason")
    tax_free_amount: int = Field(alias="taxFreeAmount")
    refundable_amount: int = Field(alias="refundableAmount")
    canceled_at: datetime = Field(alias="canceledAt")
    transaction_key: str = Field(alias="transactionKey")


class TossPaymentResponse(BaseModel):
    """TossPayments /v1/payments 공통 응답 모델"""

    model_config = ConfigDict(populate_by_name=True)

    payment_key: str = Field(alias="paymentKey")
    order_id: str = Field(alias="orderId")
    order_name: str = Field(alias="orderName")
    status: str
    method: str | None = None
    total_amount: int = Field(alias="totalAmount")
    balance_amount: int = Field(alias="balanceAmount")
    requested_at: datetime = Field(alias="requestedAt")
    approved_at: datetime | None = Field(None, alias="approvedAt")
    card: TossCardInfo | None = None
    easy_pay: TossEasyPayInfo | None = Field(None, alias="easyPay")
    virtual_account: TossVirtualAccountInfo | None = Field(None, alias="virtualAccount")
    mobile_phone: TossMobilePhoneInfo | None = Field(None, alias="mobilePhone")
    cancels: list[TossCancelInfo] | None = None
