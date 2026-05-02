import pytest

from payment.dummy.store import DummyPaymentStore
from payment.providers.nhn_kcp import NHNKCPProvider, NHNKCPSettings
from payment.providers.stripe import StripeProvider, StripeSettings
from payment.providers.toss import TossPaymentsProvider, TossPaymentsSettings
from payment.registry import ProviderRegistry
from payment.service import PaymentService

_TOSS_SETTINGS = TossPaymentsSettings(
    secret_key="test_sk_xxxxxxxxxxxxxxxxxxxx",
    client_key="test_ck_xxxxxxxxxxxxxxxxxxxx",
)

_KCP_SETTINGS = NHNKCPSettings(
    site_cd="T0000",
    site_key="test_site_key_xxxxxxxxxxxx",
)

_STRIPE_SETTINGS = StripeSettings(
    secret_key="sk_test_xxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    currency="krw",
)


@pytest.fixture
def toss_settings() -> TossPaymentsSettings:
    return _TOSS_SETTINGS


@pytest.fixture
def toss_provider(toss_settings: TossPaymentsSettings) -> TossPaymentsProvider:
    return TossPaymentsProvider(toss_settings)


@pytest.fixture
def kcp_settings() -> NHNKCPSettings:
    return _KCP_SETTINGS


@pytest.fixture
def kcp_provider(kcp_settings: NHNKCPSettings) -> NHNKCPProvider:
    return NHNKCPProvider(kcp_settings)


@pytest.fixture
def stripe_settings() -> StripeSettings:
    return _STRIPE_SETTINGS


@pytest.fixture
def stripe_provider(stripe_settings: StripeSettings) -> StripeProvider:
    return StripeProvider(stripe_settings)


@pytest.fixture
def store() -> DummyPaymentStore:
    return DummyPaymentStore()


@pytest.fixture
def registry(
    toss_provider: TossPaymentsProvider,
    kcp_provider: NHNKCPProvider,
    stripe_provider: StripeProvider,
) -> ProviderRegistry:
    r = ProviderRegistry()
    r.register(toss_provider)
    r.register(kcp_provider)
    r.register(stripe_provider)
    return r


@pytest.fixture
def service(registry: ProviderRegistry, store: DummyPaymentStore) -> PaymentService:
    return PaymentService(registry, store=store)
