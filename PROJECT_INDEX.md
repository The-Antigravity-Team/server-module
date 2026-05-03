# Project Index: server_module / payment

Generated: 2026-05-03

## 📁 Project Structure

```
server_module/
└── python/
    └── payment/
        ├── pyproject.toml
        ├── src/
        │   └── payment/
        │       ├── __init__.py          ← public API surface
        │       ├── service.py           ← PaymentService (main entry point)
        │       ├── registry.py          ← ProviderRegistry
        │       ├── core/
        │       │   ├── base.py          ← BasePaymentProvider (ABC)
        │       │   ├── models.py        ← Request/Result Pydantic models
        │       │   ├── enums.py         ← PaymentStatus, PaymentMethod
        │       │   └── exceptions.py    ← Exception hierarchy
        │       ├── providers/
        │       │   ├── toss/            ← TossPayments provider
        │       │   ├── nhn_kcp/         ← NHN KCP provider
        │       │   └── stripe/          ← Stripe provider
        │       └── dummy/
        │           └── store.py         ← In-memory store (dev/test)
        └── tests/
            ├── conftest.py              ← shared fixtures
            └── unit/
                ├── core/                ← exceptions, models tests
                ├── providers/
                │   ├── toss/
                │   ├── nhn_kcp/
                │   └── stripe/
                ├── test_registry.py
                └── test_dummy_store.py
```

## 🚀 Entry Points

- **Package root**: `python/payment/src/payment/__init__.py` — exports public API
- **Service**: `python/payment/src/payment/service.py` — `PaymentService` class (use in FastAPI/Django routers)
- **Tests**: `python/payment/tests/` — `pytest` with `asyncio_mode = "auto"`

## 📦 Core Modules

### `payment` (public API)
- Path: `src/payment/__init__.py`
- Exports: `PaymentService`, `ProviderRegistry`, `PaymentConfirmRequest`, `PaymentCancelRequest`, `PaymentStatus`, `PaymentMethod`, `PaymentError`

### `payment.service` — PaymentService
- Path: `src/payment/service.py`
- Methods: `confirm_payment(provider, request)`, `cancel_payment(provider, request)`, `get_payment(provider, payment_key)`, `get_payment_by_order_id(provider, order_id)`
- Constructor: `PaymentService(registry, store=None)` — inject `DummyPaymentStore` for dev, real DB repo for prod

### `payment.registry` — ProviderRegistry
- Path: `src/payment/registry.py`
- Methods: `register(provider)`, `get(name)`, `registered()` → list of names
- Raises `PaymentError` if unknown provider requested

### `payment.core.base` — BasePaymentProvider
- Path: `src/payment/core/base.py`
- Abstract methods: `confirm_payment`, `cancel_payment`, `get_payment`, `get_payment_by_order_id`
- Required class attribute: `provider_name: str`

### `payment.core.models` — Data Models
- Path: `src/payment/core/models.py`
- Request: `PaymentConfirmRequest(payment_key, order_id, amount, extra={})`, `PaymentCancelRequest(payment_key, cancel_reason, cancel_amount=None, extra={})`
- Result: `PaymentConfirmResult`, `PaymentCancelResult`, `PaymentQueryResult`
- `extra: dict` carries PG-specific params (e.g., KCP `enc_data`, Stripe `payment_method`)

### `payment.core.enums`
- Path: `src/payment/core/enums.py`
- `PaymentStatus`: READY | IN_PROGRESS | DONE | CANCELED | PARTIAL_CANCELED | ABORTED | EXPIRED
- `PaymentMethod`: CARD | VIRTUAL_ACCOUNT | EASY_PAY | MOBILE_PHONE | TRANSFER | CULTURE_GIFT_CERTIFICATE | BOOK_CULTURE_GIFT_CERTIFICATE | GAME_CULTURE_GIFT_CERTIFICATE | UNKNOWN

### `payment.core.exceptions`
- Path: `src/payment/core/exceptions.py`
- Hierarchy: `PaymentError` → `PaymentConfirmError`, `PaymentCancelError`, `PaymentNotFoundError`, `PaymentAmountMismatchError`, `ProviderAPIError`

### `payment.dummy.store` — DummyPaymentStore
- Path: `src/payment/dummy/store.py`
- In-memory async store; mirrors real DB schema (`PaymentRecord`, `CancelRecord`)
- Methods: `save_payment`, `get_by_payment_key`, `get_by_order_id`, `update_status`, `save_cancel`, `list_cancels`, `all_payments`

## 🔌 Providers

| Provider | `provider_name` | Class | Settings env prefix |
|---|---|---|---|
| TossPayments | `"toss"` | `TossPaymentsProvider` | `TOSS_` |
| NHN KCP | `"nhn_kcp"` | `NHNKCPProvider` | `KCP_` |
| Stripe | `"stripe"` | `StripeProvider` | `STRIPE_` |

Each provider lives in `src/payment/providers/<name>/` with: `provider.py`, `client.py`, `models.py`, `settings.py`, `__init__.py`

### TossPayments env vars
`TOSS_SECRET_KEY`, `TOSS_CLIENT_KEY`, `TOSS_BASE_URL` (default: `https://api.tosspayments.com`), `TOSS_API_VERSION` (default: `v1`), `TOSS_TIMEOUT_SECONDS` (default: 30)

### Stripe notes
Two confirm flows: (A) client-side Stripe.js → server retrieves PI; (B) server-confirm via `extra={"payment_method": "pm_xxx"}`. Cancel creates a Stripe Refund. Pass `extra={"total_amount": N}` for accurate remaining-amount calculation.

### NHN KCP notes
`confirm` requires `extra={"enc_data": ..., "enc_info": ..., "pay_method": ..., "good_name": ...}`. `cancel` benefits from `extra={"total_amount": N}` for partial cancel detection.

## 🔧 Configuration

- `python/payment/pyproject.toml` — project metadata, deps, pytest config (`asyncio_mode=auto`), ruff linting
- Settings loaded via `pydantic-settings` from env vars or `.env` file

## 🧪 Test Coverage

- Unit test files: 8 files across core + 3 providers + registry + dummy store
- Framework: `pytest` + `pytest-asyncio` (auto mode) + `pytest-mock` + `respx` (HTTP mocking)
- Shared fixtures in `tests/conftest.py`: provider instances, registry, service, store

## 🔗 Key Dependencies

| Package | Version | Purpose |
|---|---|---|
| `httpx` | >=0.27 | Async HTTP client for all provider API calls |
| `pydantic` | >=2.7 | Request/response model validation |
| `pydantic-settings` | >=2.3 | Env-based settings per provider |
| `pytest-asyncio` | >=0.23 | `async def` test support |
| `respx` | >=0.21 | Mock `httpx` calls in tests |
| `ruff` | >=0.4 | Linting (E, F, I, UP rules, line-length=100) |

## 📝 Quick Start

```python
# 1. Install
# pip install -e python/payment

# 2. Wire up providers
from payment import PaymentService, ProviderRegistry, PaymentConfirmRequest
from payment.providers.toss import TossPaymentsProvider, TossPaymentsSettings

registry = ProviderRegistry()
registry.register(TossPaymentsProvider(TossPaymentsSettings()))  # reads TOSS_* env vars

service = PaymentService(registry)

# 3. Confirm a payment (e.g., in FastAPI)
result = await service.confirm_payment(
    "toss",
    PaymentConfirmRequest(payment_key=..., order_id=..., amount=10000)
)
```

```bash
# Run tests
cd python/payment
pip install -e ".[dev]"
pytest
```

## ➕ Adding a New Provider

1. Create `src/payment/providers/<name>/` with `settings.py`, `client.py`, `models.py`, `provider.py`, `__init__.py`
2. Subclass `BasePaymentProvider`, set `provider_name`, implement 4 abstract methods
3. Map provider-specific status/method codes to `PaymentStatus` / `PaymentMethod` enums
4. Register: `registry.register(MyProvider(MySettings()))`
