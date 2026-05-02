"""payment.registry.ProviderRegistry 테스트"""
from unittest.mock import MagicMock

import pytest

from payment.core.base import BasePaymentProvider
from payment.core.exceptions import PaymentError
from payment.registry import ProviderRegistry


def _make_provider(name: str) -> MagicMock:
    p = MagicMock(spec=BasePaymentProvider)
    p.provider_name = name
    return p


class TestProviderRegistry:
    def test_register_and_get(self) -> None:
        registry = ProviderRegistry()
        provider = _make_provider("toss")
        registry.register(provider)

        assert registry.get("toss") is provider

    def test_get_nonexistent_raises_payment_error(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(PaymentError):
            registry.get("nonexistent")

    def test_error_message_names_the_provider(self) -> None:
        registry = ProviderRegistry()
        with pytest.raises(PaymentError) as exc:
            registry.get("kakao")
        assert "kakao" in str(exc.value)

    def test_error_message_lists_available_providers(self) -> None:
        registry = ProviderRegistry()
        registry.register(_make_provider("toss"))
        registry.register(_make_provider("stripe"))

        with pytest.raises(PaymentError) as exc:
            registry.get("kakao")

        msg = str(exc.value)
        assert "toss" in msg or "stripe" in msg

    def test_registered_returns_all_names(self) -> None:
        registry = ProviderRegistry()
        registry.register(_make_provider("toss"))
        registry.register(_make_provider("stripe"))
        registry.register(_make_provider("nhn_kcp"))

        assert set(registry.registered()) == {"toss", "stripe", "nhn_kcp"}

    def test_registered_empty_registry(self) -> None:
        assert ProviderRegistry().registered() == []

    def test_register_overwrites_same_name(self) -> None:
        registry = ProviderRegistry()
        old = _make_provider("toss")
        new = _make_provider("toss")

        registry.register(old)
        registry.register(new)

        assert registry.get("toss") is new
        assert len(registry.registered()) == 1

    def test_multiple_providers_independent(self) -> None:
        registry = ProviderRegistry()
        toss = _make_provider("toss")
        stripe = _make_provider("stripe")

        registry.register(toss)
        registry.register(stripe)

        assert registry.get("toss") is toss
        assert registry.get("stripe") is stripe
