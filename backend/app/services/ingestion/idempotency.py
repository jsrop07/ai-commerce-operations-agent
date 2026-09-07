"""Processed-effect registry, deliberately separate from inbox acceptance."""

from dataclasses import dataclass, field


@dataclass
class EffectRegistry:
    processed: set[tuple[str, str, str]] = field(default_factory=set)
    business_effect_count: int = 0

    @staticmethod
    def _identity(tenant_id: str, consumer: str, idempotency_key: str) -> tuple[str, str, str]:
        return tenant_id, consumer, idempotency_key

    def was_applied(self, tenant_id: str, consumer: str, idempotency_key: str) -> bool:
        return self._identity(tenant_id, consumer, idempotency_key) in self.processed

    def apply_once(self, tenant_id: str, consumer: str, idempotency_key: str) -> bool:
        identity = self._identity(tenant_id, consumer, idempotency_key)
        if identity in self.processed:
            return False
        self.processed.add(identity)
        self.business_effect_count += 1
        return True

    def was_business_effect_applied(
        self,
        tenant_id: str,
        consumer: str,
        business_key: str,
    ) -> bool:
        return self.was_applied(
            tenant_id,
            consumer,
            f"business:{business_key}",
        )

    def apply_business_effect_once(
        self,
        tenant_id: str,
        consumer: str,
        business_key: str,
    ) -> bool:
        return self.apply_once(
            tenant_id,
            consumer,
            f"business:{business_key}",
        )
