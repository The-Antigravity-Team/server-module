from payment.core.base import BasePaymentProvider
from payment.core.exceptions import PaymentError


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BasePaymentProvider] = {}

    def register(self, provider: BasePaymentProvider) -> None:
        self._providers[provider.provider_name] = provider

    def get(self, name: str) -> BasePaymentProvider:
        try:
            return self._providers[name]
        except KeyError:
            available = ", ".join(self._providers) or "(none)"
            raise PaymentError(
                f"Provider '{name}' not registered. Available: {available}"
            ) from None

    def registered(self) -> list[str]:
        return list(self._providers)
