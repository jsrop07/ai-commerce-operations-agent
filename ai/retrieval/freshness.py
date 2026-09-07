from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Mapping, Sequence

import yaml


class FreshnessState(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    MISSING = "MISSING"
    POLICY_UNDEFINED = "POLICY_UNDEFINED"


@dataclass(frozen=True)
class FreshnessResult:
    state: FreshnessState
    source_type: str
    source_id: str
    version: str
    reason: str
    definitive_answer_allowed: bool


_VERSION_PATTERN = re.compile(
    r"^v(\d+)$",
    flags=re.IGNORECASE,
)


def load_freshness_policy(
    path: str = "ai/retrieval/freshness.yaml",
) -> dict[str, Any]:
    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        return yaml.safe_load(file)


def _parse_datetime(
    value: Any,
) -> datetime | None:
    if not isinstance(value, str):
        return None

    text = value.strip()

    if not text:
        return None

    if text.endswith("Z"):
        text = (
            text[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            text
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _version_number(
    version: str,
) -> int | None:
    match = _VERSION_PATTERN.fullmatch(
        version.strip()
    )

    if match is None:
        return None

    return int(
        match.group(1)
    )


def _latest_version(
    *,
    source_id: str,
    versions: Mapping[str, Sequence[str]],
) -> str | None:
    source_versions = list(
        versions.get(
            source_id,
            [],
        )
    )

    if not source_versions:
        return None

    parsed: list[
        tuple[int, str]
    ] = []

    for version in source_versions:
        number = _version_number(
            version
        )

        if number is None:
            # 버전 규칙을 추측하지 않는다.
            return None

        parsed.append(
            (
                number,
                version,
            )
        )

    parsed.sort(
        key=lambda item: item[0]
    )

    return parsed[-1][1]


def build_version_catalog(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, list[str]]:
    catalog: dict[
        str,
        list[str],
    ] = {}

    for row in rows:
        source_id = str(
            row.get(
                "source_id",
                "",
            )
        )

        version = str(
            row.get(
                "version",
                "",
            )
        )

        if not source_id or not version:
            continue

        bucket = catalog.setdefault(
            source_id,
            [],
        )

        if version not in bucket:
            bucket.append(
                version
            )

    return catalog


def evaluate_freshness(
    *,
    source_type: str,
    source_id: str,
    version: str,
    metadata: Mapping[str, Any],
    policy: Mapping[str, Any],
    version_catalog: Mapping[
        str,
        Sequence[str],
    ],
    now: datetime | None = None,
) -> FreshnessResult:
    """
    freshness.yaml을 실제 runtime 판정으로 변환한다.

    추측 금지 원칙:
    - 정책에 없는 source_type은 POLICY_UNDEFINED
    - VERSIONED인데 버전 비교가 불가능하면 MISSING
    - TTL인데 as_of가 없거나 파싱 불가하면 STALE
    """

    source_policy = (
        policy.get(
            "sources",
            {},
        ).get(
            source_type
        )
    )

    if not isinstance(
        source_policy,
        Mapping,
    ):
        return FreshnessResult(
            state=(
                FreshnessState
                .POLICY_UNDEFINED
            ),
            source_type=source_type,
            source_id=source_id,
            version=version,
            reason=(
                "freshness_policy_undefined"
            ),
            definitive_answer_allowed=False,
        )

    mode = source_policy.get(
        "freshness_mode"
    )

    if mode == "VERSIONED":
        latest = _latest_version(
            source_id=source_id,
            versions=version_catalog,
        )

        if latest is None:
            return FreshnessResult(
                state=(
                    FreshnessState.MISSING
                ),
                source_type=source_type,
                source_id=source_id,
                version=version,
                reason=(
                    "version_comparison_unavailable"
                ),
                definitive_answer_allowed=False,
            )

        if version != latest:
            return FreshnessResult(
                state=(
                    FreshnessState.STALE
                ),
                source_type=source_type,
                source_id=source_id,
                version=version,
                reason=(
                    f"version_superseded_by_"
                    f"{latest}"
                ),
                definitive_answer_allowed=(
                    bool(
                        source_policy.get(
                            "definitive_answer_"
                            "allowed_when_stale",
                            False,
                        )
                    )
                ),
            )

        return FreshnessResult(
            state=FreshnessState.FRESH,
            source_type=source_type,
            source_id=source_id,
            version=version,
            reason="latest_valid_version",
            definitive_answer_allowed=True,
        )

    if mode == "TTL":
        ttl_seconds = source_policy.get(
            "ttl_seconds"
        )

        required_field = (
            source_policy.get(
                "required_time_field"
            )
        )

        if (
            not isinstance(
                ttl_seconds,
                int,
            )
            or ttl_seconds <= 0
            or not isinstance(
                required_field,
                str,
            )
        ):
            return FreshnessResult(
                state=FreshnessState.MISSING,
                source_type=source_type,
                source_id=source_id,
                version=version,
                reason=(
                    "invalid_ttl_policy"
                ),
                definitive_answer_allowed=False,
            )

        as_of = _parse_datetime(
            metadata.get(
                required_field
            )
        )

        if as_of is None:
            return FreshnessResult(
                state=FreshnessState.STALE,
                source_type=source_type,
                source_id=source_id,
                version=version,
                reason=(
                    f"{required_field}_missing"
                ),
                definitive_answer_allowed=False,
            )

        current_time = (
            now.astimezone(
                timezone.utc
            )
            if now is not None
            else datetime.now(
                timezone.utc
            )
        )

        age_seconds = (
            current_time
            - as_of
        ).total_seconds()

        if age_seconds < 0:
            return FreshnessResult(
                state=FreshnessState.MISSING,
                source_type=source_type,
                source_id=source_id,
                version=version,
                reason=(
                    "future_as_of_invalid"
                ),
                definitive_answer_allowed=False,
            )

        if age_seconds > ttl_seconds:
            return FreshnessResult(
                state=FreshnessState.STALE,
                source_type=source_type,
                source_id=source_id,
                version=version,
                reason="age_exceeds_ttl",
                definitive_answer_allowed=False,
            )

        return FreshnessResult(
            state=FreshnessState.FRESH,
            source_type=source_type,
            source_id=source_id,
            version=version,
            reason="within_ttl",
            definitive_answer_allowed=True,
        )

    return FreshnessResult(
        state=FreshnessState.MISSING,
        source_type=source_type,
        source_id=source_id,
        version=version,
        reason=(
            "unsupported_freshness_mode"
        ),
        definitive_answer_allowed=False,
    )