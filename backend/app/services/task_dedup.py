"""D11-BE-02 공통 Task 원인 기반 dedupe.

현재 구현은 프로세스 메모리 수준이다.
PostgreSQL 영속성/동시요청 안전성은 별도 검증 전까지 주장하지 않는다.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class TaskCauseIdentity:
    tenant_id: str
    sku_id: str
    risk_type: str
    cause_id: str
    period_bucket: int

    def raw_key(self) -> str:
        return (
            f"{self.tenant_id}|"
            f"{self.sku_id}|"
            f"{self.risk_type}|"
            f"{self.cause_id}|"
            f"{self.period_bucket}"
        )

    def dedupe_key(self) -> str:
        digest = hashlib.sha256(
            self.raw_key().encode("utf-8")
        ).hexdigest()[:24]

        return f"taskcause_{digest}"


@dataclass(frozen=True)
class DedupedTaskProposal:
    dedupe_key: str
    identity: TaskCauseIdentity

    first_seen_at: datetime
    last_seen_at: datetime

    evidence_ids: tuple[str, ...]

    replay_count: int


@dataclass
class TaskDedupService:
    """프로세스 메모리 수준 Task dedupe."""

    proposals: dict[
        str,
        DedupedTaskProposal,
    ] = field(default_factory=dict)

    def register(
        self,
        *,
        tenant_id: str,
        sku_id: str,
        risk_type: str,
        cause_id: str,
        occurred_at: datetime,
        evidence_ids: tuple[str, ...],
        dedupe_window_hours: int,
    ) -> DedupedTaskProposal:
        if not tenant_id:
            raise ValueError(
                "tenant_id is required"
            )
        if not cause_id:
            raise ValueError(
                "cause_id is required"
            )
        if not sku_id:
            raise ValueError(
                "sku_id is required"
            )

        if not risk_type:
            raise ValueError(
                "risk_type is required"
            )

        if dedupe_window_hours <= 0:
            raise ValueError(
                "dedupe_window_hours must be > 0"
            )

        if (
            occurred_at.tzinfo is None
            or occurred_at.utcoffset() is None
        ):
            raise ValueError(
                "occurred_at must be timezone-aware"
            )

        bucket = int(
            occurred_at.timestamp()
            // (dedupe_window_hours * 3600)
        )

        identity = TaskCauseIdentity(
            tenant_id=tenant_id,
            sku_id=sku_id,
            risk_type=risk_type,
            cause_id=cause_id,
            period_bucket=bucket,
        )

        dedupe_key = identity.dedupe_key()

        existing = self.proposals.get(
            dedupe_key
        )

        merged_evidence = tuple(
            dict.fromkeys(
                (
                    existing.evidence_ids
                    if existing is not None
                    else ()
                )
                + evidence_ids
            )
        )

        if existing is not None:
            updated = DedupedTaskProposal(
                dedupe_key=dedupe_key,
                identity=identity,
                first_seen_at=(
                    existing.first_seen_at
                ),
                last_seen_at=occurred_at,
                evidence_ids=merged_evidence,
                replay_count=(
                    existing.replay_count + 1
                ),
            )

            self.proposals[
                dedupe_key
            ] = updated

            return updated

        proposal = DedupedTaskProposal(
            dedupe_key=dedupe_key,
            identity=identity,
            first_seen_at=occurred_at,
            last_seen_at=occurred_at,
            evidence_ids=merged_evidence,
            replay_count=0,
        )

        self.proposals[
            dedupe_key
        ] = proposal

        return proposal