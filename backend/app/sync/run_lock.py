"""In-process sync run lock."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class SyncRunLock:
    _active: set[tuple[str, str, str]] = field(default_factory=set)
    _mutex: object = field(default_factory=Lock, repr=False)

    @staticmethod
    def _key(
        *,
        tenant_id: str,
        provider: str,
        resource: str,
    ) -> tuple[str, str, str]:
        return tenant_id, provider, resource

    def acquire(
        self,
        *,
        tenant_id: str,
        provider: str,
        resource: str,
    ) -> bool:
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not provider:
            raise ValueError("provider is required")
        if not resource:
            raise ValueError("resource is required")

        key = self._key(
            tenant_id=tenant_id,
            provider=provider,
            resource=resource,
        )

        with self._mutex:
            if key in self._active:
                return False
            self._active.add(key)
            return True

    def release(
        self,
        *,
        tenant_id: str,
        provider: str,
        resource: str,
    ) -> None:
        key = self._key(
            tenant_id=tenant_id,
            provider=provider,
            resource=resource,
        )

        with self._mutex:
            self._active.discard(key)

    def is_locked(
        self,
        *,
        tenant_id: str,
        provider: str,
        resource: str,
    ) -> bool:
        key = self._key(
            tenant_id=tenant_id,
            provider=provider,
            resource=resource,
        )

        with self._mutex:
            return key in self._active
