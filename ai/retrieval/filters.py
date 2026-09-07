from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence, TypeVar


class FilterConfidence(str, Enum):
    EXACT = "EXACT"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class MetadataFilter:
    field: str
    value: str
    confidence: FilterConfidence


T = TypeVar("T")


def _metadata_value(
    item: object,
    field: str,
) -> str:
    metadata = getattr(
        item,
        "metadata",
        None,
    )

    if not isinstance(
        metadata,
        Mapping,
    ):
        return ""

    value = metadata.get(
        field
    )

    if value is None:
        return ""

    return str(value).strip()


def apply_metadata_filters(
    items: Sequence[T],
    *,
    filters: Sequence[MetadataFilter],
) -> list[T]:
    """
    확정 가능한 metadata만 scoring 전에 후보에서 제한한다.

    원칙:
    - EXACT만 실제 filter 적용
    - UNCERTAIN은 recall 보호를 위해 적용하지 않음
    - metadata 없는 문서를 무조건 제거하지 않음
    - exact filter 결과가 0건이면 원본 후보로 fallback
    """

    candidates = list(items)

    if not candidates:
        return []

    for metadata_filter in filters:
        if (
            metadata_filter.confidence
            != FilterConfidence.EXACT
        ):
            continue

        expected = (
            metadata_filter.value
            .strip()
            .casefold()
        )

        if not expected:
            continue

        matched: list[T] = []

        unknown_metadata: list[T] = []

        for item in candidates:
            actual = _metadata_value(
                item,
                metadata_filter.field,
            )

            if not actual:
                unknown_metadata.append(
                    item
                )
                continue

            if (
                actual.casefold()
                == expected
            ):
                matched.append(
                    item
                )

        # 실제 match가 있으면
        # known mismatch만 제거하고
        # metadata 미보유 source는 유지한다.
        if matched:
            matched_ids = {
                id(item)
                for item in matched
            }

            unknown_ids = {
                id(item)
                for item
                in unknown_metadata
            }

            candidates = [
                item
                for item in candidates
                if (
                    id(item) in matched_ids
                    or id(item)
                    in unknown_ids
                )
            ]

        # exact filter가 하나도 매치되지 않으면
        # 잘못된 entity/filter가 recall을 막지 않도록
        # 현재 candidates를 그대로 유지한다.

    return candidates