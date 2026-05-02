"""NHN KCP REST API 요청/응답 Pydantic 모델"""
from __future__ import annotations

from pydantic import BaseModel, Field


# ── 결제 승인 ────────────────────────────────────────────────────────────


class KCPConfirmRequest(BaseModel):
    """POST /v1/payment"""

    site_cd: str
    tno: str            # 클라이언트에서 받은 KCP 거래 번호
    enc_data: str       # KCP 암호화 결제 데이터
    enc_info: str       # KCP 암호화 정보
    pay_method: str     # "CARD" | "VCNT" | "PCEL" | "TRAN" | "KWCP" | "NPAY"
    ordr_idxx: str      # 주문 번호 (최대 40자)
    good_name: str      # 상품명 (최대 100자)
    good_mny: int       # 결제 금액


class KCPConfirmResponse(BaseModel):
    """결제 승인 응답"""

    res_cd: str                     # "0000" = 정상
    res_msg: str
    tno: str
    amount: int
    pay_method: str | None = None
    ordr_idxx: str | None = None
    good_name: str | None = None
    approve_no: str | None = None   # 승인 번호
    card_no: str | None = None      # 마스킹된 카드 번호
    noinf: str | None = None        # 무이자 여부 ("0": 일반, "1": 무이자)
    quota: str | None = None        # 할부 개월수 ("00": 일시불)
    van_appro_date: str | None = None   # 승인 일자 YYYYMMDD
    van_appro_time: str | None = None   # 승인 시각 HHMMSS


# ── 결제 취소 ────────────────────────────────────────────────────────────


class KCPCancelRequest(BaseModel):
    """POST /v1/payment/cancel"""

    site_cd: str
    tno: str
    mod_type: str       # "STAX" = 전체 취소, "PART" = 부분 취소
    mod_mny: int        # 취소 금액
    rem_mny: int        # 취소 후 잔여 금액
    cancel_reason: str = Field(alias="canc_memo")

    model_config = {"populate_by_name": True}


class KCPCancelResponse(BaseModel):
    """결제 취소 응답"""

    res_cd: str
    res_msg: str
    tno: str | None = None
    mod_mny: int | None = None      # 취소 금액
    rem_mny: int | None = None      # 잔여 금액
    mod_date: str | None = None     # 취소 일자 YYYYMMDD
    mod_time: str | None = None     # 취소 시각 HHMMSS


# ── 결제 조회 ────────────────────────────────────────────────────────────


class KCPQueryResponse(BaseModel):
    """GET /v1/payment/{tno}  또는  GET /v1/payment?ordr_idxx={orderId} 응답"""

    res_cd: str
    res_msg: str
    tno: str | None = None
    amount: int | None = None
    pay_method: str | None = None
    ordr_idxx: str | None = None
    good_name: str | None = None
    cancel_yn: str | None = None        # "Y" = 취소됨, "N" = 정상
    part_cancel_yn: str | None = None   # "Y" = 부분 취소 있음
    van_appro_date: str | None = None   # 승인 일자 YYYYMMDD
    van_appro_time: str | None = None   # 승인 시각 HHMMSS
    mod_date: str | None = None         # 최종 취소 일자
    mod_time: str | None = None         # 최종 취소 시각
