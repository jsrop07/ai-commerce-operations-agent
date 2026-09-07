"""Read-only provider protocol for C1."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from contracts.providers import CapabilityMatrix, ProviderReadPage


class UnsupportedCapability(RuntimeError):
    code = "UNSUPPORTED_CAPABILITY"


class ProviderTransientError(RuntimeError):
    retryable = True


class ProviderNonRetryableError(RuntimeError):
    retryable = False


class ProviderHttpError(RuntimeError):
    """Safe HTTP read failure metadata for retry decisions."""

    def __init__(
        self,
        status_code: int,
        *,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(f"provider HTTP {status_code}")
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


class CommerceProvider(ABC):
    @abstractmethod
    def capabilities(self) -> CapabilityMatrix: ...

    @abstractmethod
    def verify_health(self) -> dict[str, str]: ...

    @abstractmethod
    def read_products(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]: ...

    @abstractmethod
    def read_orders(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]: ...

    @abstractmethod
    def read_inventory(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]: ...

    @abstractmethod
    def read_inquiries(self, cursor: str | None = None) -> ProviderReadPage[dict[str, Any]]: ...

    @abstractmethod
    def read_incoming_stock(
        self, cursor: str | None = None
    ) -> ProviderReadPage[dict[str, Any]]: ...


class WriteDisabledMixin:
    def execute_write(self, *_: object, **__: object) -> None:
        raise UnsupportedCapability("UNSUPPORTED_CAPABILITY: writes are disabled in C1")
