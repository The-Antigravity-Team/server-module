# payment

멀티 PG사를 단일 인터페이스로 추상화한 Python 결제 모듈입니다.  
TossPayments, NHN KCP, Stripe를 지원하며, 새로운 PG사 추가가 용이하도록 설계되었습니다.

## 목차

- [개요](#개요)
- [설치](#설치)
- [빠른 시작](#빠른-시작)
- [아키텍처](#아키텍처)
- [핵심 개념](#핵심-개념)
  - [PaymentService](#paymentservice)
  - [ProviderRegistry](#providerregistry)
  - [BasePaymentProvider](#basepaymentprovider)
- [데이터 모델](#데이터-모델)
  - [요청 모델](#요청-모델)
  - [결과 모델](#결과-모델)
  - [열거형](#열거형)
- [예외 계층](#예외-계층)
- [PG사 프로바이더](#pg사-프로바이더)
  - [TossPayments](#tosspayments)
  - [NHN KCP](#nhn-kcp)
  - [Stripe](#stripe)
- [개발/테스트용 저장소](#개발테스트용-저장소)
- [환경 변수 레퍼런스](#환경-변수-레퍼런스)
- [테스트](#테스트)
- [새 PG사 추가하기](#새-pg사-추가하기)

---

## 개요

이 모듈은 여러 PG사 API의 세부 구현을 숨기고, 애플리케이션 레이어에 **일관된 결제 인터페이스**를 제공합니다.

```
애플리케이션 코드
      │
      ▼
PaymentService          ← 외부 진입점
      │
ProviderRegistry        ← provider_name 으로 라우팅
      │
BasePaymentProvider     ← 추상 계약
 ├─ TossPaymentsProvider
 ├─ NHNKCPProvider
 └─ StripeProvider
```

**설계 원칙**

- 각 PG사 응답을 공통 `PaymentStatus` / `PaymentMethod`로 정규화
- `extra: dict` 필드로 PG사별 추가 파라미터를 처리 (인터페이스 오염 최소화)
- `DummyPaymentStore`로 개발·테스트 환경에서도 실제와 동일한 흐름 검증 가능
- `httpx` 기반 순수 async 구현 — FastAPI, Starlette 등과 자연스럽게 통합

---

## 설치

```bash
pip install -e python/payment
```

개발 의존성(테스트, 린터) 포함:

```bash
pip install -e "python/payment[dev]"
```

**요구 사항**: Python 3.11+

---

## 빠른 시작

```python
from payment import (
    PaymentService,
    ProviderRegistry,
    PaymentConfirmRequest,
    PaymentCancelRequest,
)
from payment.providers.toss import TossPaymentsProvider, TossPaymentsSettings

# 1. 레지스트리 구성
registry = ProviderRegistry()
registry.register(TossPaymentsProvider(TossPaymentsSettings()))  # 환경 변수에서 자동 로드

# 2. 서비스 생성
service = PaymentService(registry)

# 3. 결제 승인
result = await service.confirm_payment(
    "toss",
    PaymentConfirmRequest(
        payment_key="tviva20230410171218Ygm3r",
        order_id="order-abc-001",
        amount=50000,
    ),
)
print(result.status)   # PaymentStatus.DONE
print(result.method)   # PaymentMethod.CARD

# 4. 결제 취소 (전액)
cancel_result = await service.cancel_payment(
    "toss",
    PaymentCancelRequest(
        payment_key="tviva20230410171218Ygm3r",
        cancel_reason="고객 요청",
    ),
)

# 5. 결제 조회
query_result = await service.get_payment("toss", "tviva20230410171218Ygm3r")
```

### FastAPI 연동 예시

```python
from fastapi import APIRouter
from payment import PaymentService, ProviderRegistry, PaymentConfirmRequest
from payment.providers.toss import TossPaymentsProvider, TossPaymentsSettings

registry = ProviderRegistry()
registry.register(TossPaymentsProvider(TossPaymentsSettings()))
payment_service = PaymentService(registry)

router = APIRouter()

class ConfirmBody(BaseModel):
    payment_key: str
    order_id: str
    amount: int

@router.post("/payment/confirm")
async def confirm_payment(body: ConfirmBody):
    result = await payment_service.confirm_payment(
        "toss",
        PaymentConfirmRequest(
            payment_key=body.payment_key,
            order_id=body.order_id,
            amount=body.amount,
        ),
    )
    return result.model_dump()
```

---

## 아키텍처

```
src/payment/
├── __init__.py               # 공개 API 진입점
├── service.py                # PaymentService
├── registry.py               # ProviderRegistry
│
├── core/
│   ├── base.py               # BasePaymentProvider (ABC)
│   ├── models.py             # 공통 Request / Result 모델
│   ├── enums.py              # PaymentStatus, PaymentMethod
│   └── exceptions.py         # 예외 계층
│
├── providers/
│   ├── toss/
│   │   ├── provider.py       # TossPaymentsProvider
│   │   ├── client.py         # TossPaymentsClient (httpx)
│   │   ├── models.py         # TossPaymentResponse (Pydantic)
│   │   └── settings.py       # TossPaymentsSettings
│   ├── nhn_kcp/
│   │   ├── provider.py       # NHNKCPProvider
│   │   ├── client.py         # NHNKCPClient (httpx)
│   │   ├── models.py         # KCP 요청/응답 모델
│   │   └── settings.py       # NHNKCPSettings
│   └── stripe/
│       ├── provider.py       # StripeProvider
│       ├── client.py         # StripeClient (httpx)
│       ├── models.py         # StripePaymentIntentResponse 등
│       └── settings.py       # StripeSettings
│
└── dummy/
    └── store.py              # DummyPaymentStore (개발/테스트용 인메모리)
```

---

## 핵심 개념

### PaymentService

`payment.service.PaymentService`는 애플리케이션이 직접 사용하는 **유일한 진입점**입니다.

```python
class PaymentService:
    def __init__(
        self,
        registry: ProviderRegistry,
        store: DummyPaymentStore | None = None,
    ) -> None: ...
```

| 메서드 | 설명 |
|---|---|
| `confirm_payment(provider, request)` | 결제 승인 |
| `cancel_payment(provider, request)` | 결제 취소 (전액 또는 부분) |
| `get_payment(provider, payment_key)` | paymentKey로 결제 조회 |
| `get_payment_by_order_id(provider, order_id)` | orderId로 결제 조회 |

**`store` 파라미터**

- `None` (기본): 단순히 PG사 API를 호출하고 결과만 반환
- `DummyPaymentStore` 주입: 승인/취소 결과를 인메모리 저장소에 자동 저장 (개발·테스트용)
- 실제 서비스: `DummyPaymentStore` 대신 DB Repository를 동일한 인터페이스로 구현하여 주입

---

### ProviderRegistry

런타임에 PG사 프로바이더를 등록·조회하는 컨테이너입니다.

```python
registry = ProviderRegistry()
registry.register(TossPaymentsProvider(...))
registry.register(NHNKCPProvider(...))
registry.register(StripeProvider(...))

# 조회
provider = registry.get("toss")          # TossPaymentsProvider 반환
registry.registered()                    # ["toss", "nhn_kcp", "stripe"]
```

- 동일 `provider_name`으로 재등록하면 **덮어씁니다** (교체 가능)
- 미등록 이름 조회 시 `PaymentError` 발생 (메시지에 등록된 목록 포함)

---

### BasePaymentProvider

새 PG사를 추가할 때 구현해야 하는 추상 클래스입니다.

```python
class BasePaymentProvider(ABC):
    provider_name: str  # 반드시 클래스 속성으로 선언

    @abstractmethod
    async def confirm_payment(self, request: PaymentConfirmRequest) -> PaymentConfirmResult: ...

    @abstractmethod
    async def cancel_payment(self, request: PaymentCancelRequest) -> PaymentCancelResult: ...

    @abstractmethod
    async def get_payment(self, payment_key: str) -> PaymentQueryResult: ...

    @abstractmethod
    async def get_payment_by_order_id(self, order_id: str) -> PaymentQueryResult: ...
```

---

## 데이터 모델

### 요청 모델

#### `PaymentConfirmRequest`

```python
class PaymentConfirmRequest(BaseModel):
    payment_key: str          # PG사에서 발급한 결제 키
    order_id: str             # 가맹점 주문 ID
    amount: int               # 결제 금액 (원, 반드시 > 0)
    extra: dict = {}          # PG사별 추가 파라미터
```

| PG사 | `extra`에 필요한 키 |
|---|---|
| TossPayments | 없음 |
| NHN KCP | `enc_data`, `enc_info`, `pay_method`, `good_name` |
| Stripe (서버 확인) | `payment_method` (예: `"pm_xxx"`) |
| Stripe (클라이언트 확인) | 없음 |

#### `PaymentCancelRequest`

```python
class PaymentCancelRequest(BaseModel):
    payment_key: str           # 취소할 결제의 키
    cancel_reason: str         # 취소 사유
    cancel_amount: int | None  # None = 전액 취소, 정수 = 부분 취소 금액
    extra: dict = {}           # PG사별 추가 파라미터
```

| PG사 | `extra`에 필요한 키 |
|---|---|
| TossPayments | 없음 |
| NHN KCP | `total_amount` (잔여 금액 계산에 필요), `order_id` |
| Stripe | `total_amount` (잔여 금액 계산), `order_id` |

---

### 결과 모델

#### `PaymentConfirmResult`

```python
class PaymentConfirmResult(BaseModel):
    payment_key: str
    order_id: str
    order_name: str
    status: PaymentStatus
    method: PaymentMethod
    amount: int
    approved_at: datetime | None
    raw: dict                  # PG사 원본 응답 (디버깅용)
```

#### `PaymentCancelResult`

```python
class PaymentCancelResult(BaseModel):
    payment_key: str
    order_id: str
    cancel_amount: int         # 실제 취소된 금액
    remaining_amount: int      # 취소 후 잔여 금액
    status: PaymentStatus      # CANCELED 또는 PARTIAL_CANCELED
    canceled_at: datetime
    raw: dict
```

#### `PaymentQueryResult`

```python
class PaymentQueryResult(BaseModel):
    payment_key: str
    order_id: str
    order_name: str
    status: PaymentStatus
    method: PaymentMethod
    amount: int
    approved_at: datetime | None
    canceled_at: datetime | None
    raw: dict
```

---

### 열거형

#### `PaymentStatus`

| 값 | 설명 |
|---|---|
| `READY` | 결제 생성됨, 미완료 |
| `IN_PROGRESS` | 결제 진행 중 (가상계좌 입금 대기 포함) |
| `DONE` | 결제 완료 |
| `CANCELED` | 전액 취소 |
| `PARTIAL_CANCELED` | 부분 취소 |
| `ABORTED` | 결제 중단 |
| `EXPIRED` | 결제 만료 |

#### `PaymentMethod`

| 값 | 설명 |
|---|---|
| `CARD` | 신용/체크카드 |
| `VIRTUAL_ACCOUNT` | 가상계좌 |
| `EASY_PAY` | 간편결제 (카카오페이, 네이버페이, 토스 등) |
| `MOBILE_PHONE` | 휴대폰 결제 |
| `TRANSFER` | 계좌이체 |
| `CULTURE_GIFT_CERTIFICATE` | 문화상품권 |
| `BOOK_CULTURE_GIFT_CERTIFICATE` | 도서문화상품권 |
| `GAME_CULTURE_GIFT_CERTIFICATE` | 게임문화상품권 |
| `UNKNOWN` | 매핑 불가 |

---

## 예외 계층

```
PaymentError                        ← 결제 서비스 최상위 예외
├── PaymentConfirmError             ← 결제 승인 실패
├── PaymentCancelError              ← 결제 취소 실패
├── PaymentNotFoundError            ← 결제 정보 없음 (HTTP 404 포함)
├── PaymentAmountMismatchError      ← 금액 위변조 감지
│     .expected / .actual
└── ProviderAPIError                ← PG사 API 오류
      .status_code / .error_code / .message
```

**처리 예시**

```python
from payment import PaymentError
from payment.core.exceptions import PaymentAmountMismatchError, ProviderAPIError

try:
    result = await service.confirm_payment("toss", request)
except PaymentAmountMismatchError as e:
    # 금액 위변조: 클라이언트가 금액을 조작한 경우
    logger.critical(f"Amount tampered: expected={e.expected}, actual={e.actual}")
    raise
except ProviderAPIError as e:
    # PG사 API 오류
    logger.error(f"PG error [{e.error_code}] {e.message} (HTTP {e.status_code})")
    raise
except PaymentError:
    # 그 외 결제 오류
    raise
```

---

## PG사 프로바이더

### TossPayments

**provider_name**: `"toss"`

#### 설정

```python
from payment.providers.toss import TossPaymentsProvider, TossPaymentsSettings

settings = TossPaymentsSettings(
    secret_key="test_sk_...",    # 또는 환경 변수 TOSS_SECRET_KEY
    client_key="test_ck_...",    # 또는 환경 변수 TOSS_CLIENT_KEY
)
provider = TossPaymentsProvider(settings)
```

#### 결제 승인

클라이언트에서 TossPayments SDK로 결제 진행 완료 후 서버로 `paymentKey`, `orderId`, `amount`를 전달받아 서버 측에서 승인합니다.

```python
result = await service.confirm_payment(
    "toss",
    PaymentConfirmRequest(
        payment_key="tviva20230410171218Ygm3r",
        order_id="order-001",
        amount=50000,
    ),
)
```

> **금액 위변조 검증**: 승인 응답의 `totalAmount`가 요청 `amount`와 다르면 자동으로 `PaymentAmountMismatchError`를 발생시킵니다.

#### 결제 취소

```python
# 전액 취소
await service.cancel_payment(
    "toss",
    PaymentCancelRequest(payment_key="...", cancel_reason="고객 요청"),
)

# 부분 취소
await service.cancel_payment(
    "toss",
    PaymentCancelRequest(payment_key="...", cancel_reason="일부 환불", cancel_amount=20000),
)
```

#### API 엔드포인트

| 동작 | 메서드 | URL |
|---|---|---|
| 결제 승인 | POST | `/v1/payments/confirm` |
| 결제 취소 | POST | `/v1/payments/{paymentKey}/cancel` |
| paymentKey 조회 | GET | `/v1/payments/{paymentKey}` |
| orderId 조회 | GET | `/v1/payments/orders/{orderId}` |

#### 인증

`Authorization: Basic base64(secretKey:)`

---

### NHN KCP

**provider_name**: `"nhn_kcp"`

#### 설정

```python
from payment.providers.nhn_kcp import NHNKCPProvider, NHNKCPSettings

settings = NHNKCPSettings(
    site_cd="T0000",                              # KCP_SITE_CD
    site_key="test_site_key_...",                 # KCP_SITE_KEY
    base_url="https://stg-api.kcp.co.kr",         # 스테이징 (기본값: 운영)
)
provider = NHNKCPProvider(settings)
```

#### 결제 승인

KCP는 클라이언트에서 암호화한 결제 데이터(`enc_data`, `enc_info`)를 서버가 받아서 승인합니다.

```python
result = await service.confirm_payment(
    "nhn_kcp",
    PaymentConfirmRequest(
        payment_key="kcp-tno-xxx",   # KCP 거래 번호 (tno)
        order_id="order-001",
        amount=50000,
        extra={
            "enc_data": "...",       # 필수: KCP 암호화 결제 데이터
            "enc_info": "...",       # 필수: KCP 암호화 정보
            "pay_method": "CARD",   # 결제 수단 코드
            "good_name": "상품명",  # 상품명
        },
    ),
)
```

#### 결제 취소

```python
# 전액 취소
await service.cancel_payment(
    "nhn_kcp",
    PaymentCancelRequest(
        payment_key="kcp-tno-xxx",
        cancel_reason="고객 요청",
        extra={
            "total_amount": 50000,  # 원래 결제 금액 (잔여 계산에 필요)
            "order_id": "order-001",
        },
    ),
)

# 부분 취소
await service.cancel_payment(
    "nhn_kcp",
    PaymentCancelRequest(
        payment_key="kcp-tno-xxx",
        cancel_reason="일부 환불",
        cancel_amount=20000,
        extra={"total_amount": 50000, "order_id": "order-001"},
    ),
)
```

#### pay_method 코드표

| KCP 코드 | PaymentMethod |
|---|---|
| `CARD` | CARD |
| `VCNT` | VIRTUAL_ACCOUNT |
| `PCEL` | MOBILE_PHONE |
| `TRAN` | TRANSFER |
| `KWCP` | EASY_PAY (카카오페이) |
| `NPAY` | EASY_PAY (네이버페이) |
| `TCSH` | EASY_PAY (토스) |
| `GIFT` | CULTURE_GIFT_CERTIFICATE |

#### 주의 사항

- KCP는 **HTTP 200이어도 `res_cd` 필드로 오류를 반환**합니다. 클라이언트가 `res_cd != "0000"`일 때 `ProviderAPIError`를 발생시킵니다.
- 취소 응답의 `mod_mny` / `rem_mny` 누락 시 요청값을 fallback으로 사용합니다.
- 스테이징 URL: `https://stg-api.kcp.co.kr`

#### API 엔드포인트

| 동작 | 메서드 | URL |
|---|---|---|
| 결제 승인 | POST | `/v1/payment` |
| 결제 취소 | POST | `/v1/payment/cancel` |
| tno 조회 | GET | `/v1/payment/{tno}` |
| orderId 조회 | GET | `/v1/payment?ordr_idxx={orderId}` |

---

### Stripe

**provider_name**: `"stripe"`

#### 설정

```python
from payment.providers.stripe import StripeProvider, StripeSettings

settings = StripeSettings(
    secret_key="sk_test_...",    # STRIPE_SECRET_KEY
    currency="krw",              # STRIPE_CURRENCY (기본값)
    api_version="2024-06-20",    # STRIPE_API_VERSION
)
provider = StripeProvider(settings)
```

#### 결제 승인 — 두 가지 흐름

**흐름 A: 클라이언트 확인 (기본)**

클라이언트에서 `Stripe.js` 또는 모바일 SDK로 결제 완료 후, 서버는 PaymentIntent를 조회(retrieve)하여 `succeeded` 상태인지만 검증합니다.

```python
result = await service.confirm_payment(
    "stripe",
    PaymentConfirmRequest(
        payment_key="pi_3Nxxx...",   # Stripe PaymentIntent ID
        order_id="order-001",
        amount=50000,
        # extra 없음
    ),
)
```

**흐름 B: 서버 확인**

서버가 직접 Stripe `/confirm` 엔드포인트를 호출합니다. 모바일·서버사이드 결제에 사용합니다.

```python
result = await service.confirm_payment(
    "stripe",
    PaymentConfirmRequest(
        payment_key="pi_3Nxxx...",
        order_id="order-001",
        amount=50000,
        extra={"payment_method": "pm_card_visa"},  # 필수
    ),
)
```

#### 결제 취소 (환불)

Stripe에서는 취소가 **Refund 생성**으로 처리됩니다.

```python
# 전액 환불
await service.cancel_payment(
    "stripe",
    PaymentCancelRequest(
        payment_key="pi_3Nxxx...",
        cancel_reason="고객 요청",
        extra={"total_amount": 50000, "order_id": "order-001"},
    ),
)

# 부분 환불
await service.cancel_payment(
    "stripe",
    PaymentCancelRequest(
        payment_key="pi_3Nxxx...",
        cancel_reason="일부 환불",
        cancel_amount=20000,
        extra={"total_amount": 50000, "order_id": "order-001"},
    ),
)
```

> `cancel_reason`에 `"fraud"`, `"사기"`, `"duplicate"`, `"중복"` 포함 시 Stripe refund reason 코드로 자동 변환됩니다.

#### orderId 조회 방식

Stripe는 orderId를 **PaymentIntent `metadata`**에 저장한 경우에만 `get_payment_by_order_id`를 지원합니다. PaymentIntent 생성 시 아래를 포함해야 합니다:

```python
# Stripe PaymentIntent 생성 시 (클라이언트/서버 어딘가에서)
stripe.PaymentIntent.create(
    amount=50000,
    currency="krw",
    metadata={"order_id": "order-001", "order_name": "상품명"},
)
```

#### 주의 사항

- Stripe는 최소 화폐 단위를 사용합니다. KRW는 원(정수)이므로 그대로 사용합니다.
- 취소 시각(`canceled_at`)은 Stripe PaymentIntent에 직접 포함되지 않아 항상 `None`으로 반환됩니다.
- Stripe API 인증: `Authorization: Bearer {secret_key}`
- POST 요청은 `application/x-www-form-urlencoded` 형식입니다.

#### API 엔드포인트

| 동작 | 메서드 | URL |
|---|---|---|
| 결제 승인 (서버) | POST | `/v1/payment_intents/{id}/confirm` |
| 결제 조회 | GET | `/v1/payment_intents/{id}` |
| 환불 생성 | POST | `/v1/refunds` |
| orderId 조회 | GET | `/v1/payment_intents?metadata[order_id]={id}&limit=1` |

---

## 개발/테스트용 저장소

`DummyPaymentStore`는 실제 DB 없이도 승인·취소 흐름 전체를 테스트할 수 있는 **인메모리 저장소**입니다.

실제 서비스의 `payments` / `payment_cancels` 테이블 스키마를 그대로 반영하여, 나중에 ORM으로 교체하기 쉽도록 설계되었습니다.

```python
from payment.dummy.store import DummyPaymentStore

store = DummyPaymentStore()
service = PaymentService(registry, store=store)

# 승인 후 저장소 확인
await service.confirm_payment("toss", request)
records = store.all_payments()
record = await store.get_by_payment_key("tviva...")
```

### `PaymentRecord` — payments 테이블 스키마

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | str (UUID) | PK |
| `payment_key` | str | PG사 결제 키 (unique) |
| `order_id` | str | 주문 ID (unique) |
| `order_name` | str | 주문명 |
| `provider` | str | PG사 식별자 |
| `status` | PaymentStatus | 결제 상태 |
| `method` | PaymentMethod | 결제 수단 |
| `amount` | int | 결제 금액 |
| `approved_at` | datetime \| None | 승인 시각 |
| `created_at` | datetime | 레코드 생성 시각 |
| `updated_at` | datetime | 레코드 수정 시각 |
| `raw_response` | dict | PG사 원본 응답 |

### `CancelRecord` — payment_cancels 테이블 스키마

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | str (UUID) | PK |
| `payment_id` | str | payments.id FK |
| `payment_key` | str | PG사 결제 키 |
| `cancel_amount` | int | 취소 금액 |
| `cancel_reason` | str | 취소 사유 |
| `canceled_at` | datetime | 취소 시각 |
| `raw_response` | dict | PG사 원본 응답 |

---

## 환경 변수 레퍼런스

### TossPayments (`TOSS_` 접두사)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `TOSS_SECRET_KEY` | `""` | 시크릿 키 (`test_sk_...` / `live_sk_...`) |
| `TOSS_CLIENT_KEY` | `""` | 클라이언트 키 (`test_ck_...` / `live_ck_...`) |
| `TOSS_BASE_URL` | `https://api.tosspayments.com` | API 기본 URL |
| `TOSS_API_VERSION` | `v1` | API 버전 |
| `TOSS_TIMEOUT_SECONDS` | `30` | HTTP 타임아웃 (초) |

### NHN KCP (`KCP_` 접두사)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `KCP_SITE_CD` | `""` | 사이트 코드 |
| `KCP_SITE_KEY` | `""` | 사이트 키 |
| `KCP_BASE_URL` | `https://api.kcp.co.kr` | API 기본 URL (스테이징: `https://stg-api.kcp.co.kr`) |
| `KCP_API_VERSION` | `v1` | API 버전 |
| `KCP_TIMEOUT_SECONDS` | `30` | HTTP 타임아웃 (초) |

### Stripe (`STRIPE_` 접두사)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `STRIPE_SECRET_KEY` | `""` | 시크릿 키 (`sk_test_...` / `sk_live_...`) |
| `STRIPE_API_VERSION` | `2024-06-20` | Stripe API 버전 |
| `STRIPE_CURRENCY` | `krw` | 기본 통화 |
| `STRIPE_TIMEOUT_SECONDS` | `30` | HTTP 타임아웃 (초) |

`.env` 파일 예시:

```env
TOSS_SECRET_KEY=test_sk_xxxxxxxxxx
TOSS_CLIENT_KEY=test_ck_xxxxxxxxxx

KCP_SITE_CD=T0000
KCP_SITE_KEY=test_site_key_xxxxxxxxxx
KCP_BASE_URL=https://stg-api.kcp.co.kr

STRIPE_SECRET_KEY=sk_test_xxxxxxxxxx
```

---

## 테스트

```bash
cd python/payment
pip install -e ".[dev]"
pytest
```

**테스트 구조**

```
tests/
├── conftest.py                         # 공유 픽스처 (provider, registry, service, store)
└── unit/
    ├── core/
    │   ├── test_exceptions.py
    │   └── test_models.py
    ├── providers/
    │   ├── toss/test_provider.py       # respx로 HTTP 목킹
    │   ├── nhn_kcp/test_provider.py
    │   └── stripe/test_provider.py
    ├── test_registry.py
    └── test_dummy_store.py
```

**HTTP 목킹**: `respx` 라이브러리로 실제 HTTP 요청 없이 PG사 응답을 시뮬레이션합니다.

```python
import respx, httpx

with respx.mock:
    respx.post("https://api.tosspayments.com/v1/payments/confirm").mock(
        return_value=httpx.Response(200, json={"paymentKey": "...", ...})
    )
    result = await provider.confirm_payment(request)
```

**픽스처 (conftest.py)**

| 픽스처 | 타입 | 설명 |
|---|---|---|
| `toss_settings` | `TossPaymentsSettings` | 테스트용 설정 |
| `toss_provider` | `TossPaymentsProvider` | 테스트용 프로바이더 |
| `kcp_settings` | `NHNKCPSettings` | 테스트용 설정 |
| `kcp_provider` | `NHNKCPProvider` | 테스트용 프로바이더 |
| `stripe_settings` | `StripeSettings` | 테스트용 설정 |
| `stripe_provider` | `StripeProvider` | 테스트용 프로바이더 |
| `store` | `DummyPaymentStore` | 인메모리 저장소 |
| `registry` | `ProviderRegistry` | 3개 PG사 등록된 레지스트리 |
| `service` | `PaymentService` | registry + store 주입된 서비스 |

---

## 새 PG사 추가하기

1. **디렉토리 생성**

```
src/payment/providers/kakao/
├── __init__.py
├── settings.py
├── models.py
├── client.py
└── provider.py
```

2. **Settings 정의** (`settings.py`)

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class KakaoPaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KAKAO_", env_file=".env")

    secret_key: str = ""
    base_url: str = "https://open-api.kakaopay.com"
    timeout_seconds: int = 30
```

3. **Provider 구현** (`provider.py`)

```python
from payment.core.base import BasePaymentProvider
from payment.core.enums import PaymentMethod, PaymentStatus
from payment.core.models import (
    PaymentCancelRequest, PaymentCancelResult,
    PaymentConfirmRequest, PaymentConfirmResult, PaymentQueryResult,
)
from .client import KakaoPayClient
from .settings import KakaoPaySettings

class KakaoPayProvider(BasePaymentProvider):
    provider_name = "kakao"  # registry 등록 키

    def __init__(self, settings: KakaoPaySettings | None = None) -> None:
        self._client = KakaoPayClient(settings or KakaoPaySettings())

    async def confirm_payment(self, request: PaymentConfirmRequest) -> PaymentConfirmResult:
        raw = await self._client.approve(...)
        # KakaoPay 응답 → 공통 모델로 변환
        return PaymentConfirmResult(
            payment_key=...,
            status=PaymentStatus.DONE,
            method=PaymentMethod.EASY_PAY,
            ...
            raw=raw,
        )

    async def cancel_payment(self, request: PaymentCancelRequest) -> PaymentCancelResult: ...
    async def get_payment(self, payment_key: str) -> PaymentQueryResult: ...
    async def get_payment_by_order_id(self, order_id: str) -> PaymentQueryResult: ...
```

4. **`__init__.py` 작성**

```python
from .provider import KakaoPayProvider
from .settings import KakaoPaySettings

__all__ = ["KakaoPayProvider", "KakaoPaySettings"]
```

5. **등록 및 사용**

```python
from payment.providers.kakao import KakaoPayProvider, KakaoPaySettings

registry.register(KakaoPayProvider(KakaoPaySettings()))
result = await service.confirm_payment("kakao", request)
```

**체크리스트**

- [ ] `provider_name` 클래스 속성 선언
- [ ] 4개 추상 메서드 모두 구현
- [ ] PG사 고유 status/method 코드 → 공통 Enum 매핑
- [ ] `PaymentAmountMismatchError` 금액 검증
- [ ] `PaymentNotFoundError` / `ProviderAPIError` 예외 변환
- [ ] `raw=raw` 원본 응답 보존
- [ ] 단위 테스트 작성 (`respx`로 HTTP 목킹)
