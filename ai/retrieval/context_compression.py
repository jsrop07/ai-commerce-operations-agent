from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ai.retrieval.citation import (
    LIVE_SOURCE_TYPES,
    citation_or_abstain,
)


REQUIRED_EVIDENCE_FIELDS = frozenset(
    {
        "source_id",
        "title",
        "record_id",
        "source_type",
        "field_or_path",
        "excerpt",
    }
)

PRESERVED_OPTIONAL_FIELDS = frozenset(
    {
        "as_of",
        "evidence_id",
        "evidence_ids",
        "policy_exception",
        "policy_exceptions",
        "version",
    }
)

DROP_FIELDS = frozenset(
    {
        "rank",
        "score",
        "bm25_rank",
        "vector_rank",
        "bm25_score",
        "vector_score",
        "bm25_normalized",
        "vector_normalized",
        "fusion_method",
        "rerank_score",
        "matched_query_indexes",
        "matched_queries",
        "combine_reason",
        "debug",
        "ui_state",
    }
)


@dataclass(frozen=True)
class CompressionItem:
    source_id: str
    compressed: dict[str, Any]
    original: dict[str, Any]
    fallback: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id":
                self.source_id,
            "compressed":
                self.compressed,
            "original":
                self.original,
            "fallback":
                self.fallback,
            "reason":
                self.reason,
        }


@dataclass(frozen=True)
class CompressionTrace:
    input_count: int
    output_count: int
    duplicate_count: int

    before_char_count: int
    after_char_count: int
    reduction_ratio: float

    evidence_loss_count: int
    fallback_count: int

    citation_answerable_before: int
    citation_answerable_after: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_count":
                self.input_count,
            "output_count":
                self.output_count,
            "duplicate_count":
                self.duplicate_count,
            "before_char_count":
                self.before_char_count,
            "after_char_count":
                self.after_char_count,
            "reduction_ratio":
                self.reduction_ratio,
            "evidence_loss_count":
                self.evidence_loss_count,
            "fallback_count":
                self.fallback_count,
            "citation_answerable_before":
                self.citation_answerable_before,
            "citation_answerable_after":
                self.citation_answerable_after,
        }


@dataclass(frozen=True)
class CompressionResult:
    items: tuple[CompressionItem, ...]
    trace: CompressionTrace

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": [
                item.to_dict()
                for item in self.items
            ],
            "trace":
                self.trace.to_dict(),
        }


def _string_size(
    value: Any,
) -> int:
    if value is None:
        return 0

    if isinstance(
        value,
        dict,
    ):
        return sum(
            len(str(key))
            + _string_size(item)
            for key, item
            in value.items()
        )

    if isinstance(
        value,
        (list, tuple, set),
    ):
        return sum(
            _string_size(item)
            for item in value
        )

    return len(
        str(value)
    )


def _has_required_evidence(
    item: dict[str, Any],
) -> bool:
    return all(
        item.get(field)
        for field
        in REQUIRED_EVIDENCE_FIELDS
    )


def _has_valid_live_as_of(
    item: dict[str, Any],
) -> bool:
    source_type = item.get(
        "source_type"
    )

    if (
        source_type
        not in LIVE_SOURCE_TYPES
    ):
        return True

    return bool(
        item.get(
            "as_of"
        )
    )


def _citation_answerable(
    item: dict[str, Any],
) -> bool:
    decision = citation_or_abstain(
        [item]
    )

    return (
        decision.decision
        == "ANSWER"
    )


def _compress_one(
    item: dict[str, Any],
) -> dict[str, Any]:
    output: dict[
        str,
        Any,
    ] = {}

    for key, value in item.items():
        if key in DROP_FIELDS:
            continue

        if (
            key
            in REQUIRED_EVIDENCE_FIELDS
            or key
            in PRESERVED_OPTIONAL_FIELDS
        ):
            output[key] = value
            continue

        # 사용자 답변에 직접 필요한
        # 작은 도메인 필드만 유지한다.
        if key in {
            "product_name",
            "product_code",
            "custom_product_code",
            "category_nos",
            "selling",
            "sold_out",
            "operational",
        }:
            output[key] = value

    return output


def _identity_key(
    item: dict[str, Any],
) -> tuple[str, str, str]:
    return (
        str(
            item.get(
                "source_id",
                "",
            )
        ),
        str(
            item.get(
                "record_id",
                "",
            )
        ),
        str(
            item.get(
                "field_or_path",
                "",
            )
        ),
    )


def compress_context(
    items: Iterable[
        dict[str, Any]
    ],
) -> CompressionResult:
    original_items = [
        dict(item)
        for item in items
    ]

    before_char_count = sum(
        _string_size(item)
        for item
        in original_items
    )

    before_answerable = sum(
        _citation_answerable(item)
        for item
        in original_items
    )

    seen: set[
        tuple[str, str, str]
    ] = set()

    output: list[
        CompressionItem
    ] = []

    duplicate_count = 0
    evidence_loss_count = 0
    fallback_count = 0

    for original in original_items:
        identity = _identity_key(
            original
        )

        if identity in seen:
            duplicate_count += 1
            continue

        seen.add(
            identity
        )

        compressed = (
            _compress_one(
                original
            )
        )

        required_ok = (
            _has_required_evidence(
                compressed
            )
        )

        live_as_of_ok = (
            _has_valid_live_as_of(
                compressed
            )
        )

        citation_ok = (
            _citation_answerable(
                compressed
            )
        )

        if (
            not required_ok
            or not live_as_of_ok
            or not citation_ok
        ):
            evidence_loss_count += 1
            fallback_count += 1

            output.append(
                CompressionItem(
                    source_id=str(
                        original.get(
                            "source_id",
                            "",
                        )
                    ),
                    compressed=original,
                    original=original,
                    fallback=True,
                    reason=(
                        "EVIDENCE_PRESERVATION_FAILED"
                    ),
                )
            )

            continue

        output.append(
            CompressionItem(
                source_id=str(
                    compressed[
                        "source_id"
                    ]
                ),
                compressed=compressed,
                original=original,
                fallback=False,
                reason="COMPRESSED",
            )
        )

    final_payloads = [
        item.compressed
        for item in output
    ]

    after_char_count = sum(
        _string_size(item)
        for item
        in final_payloads
    )

    after_answerable = sum(
        _citation_answerable(item)
        for item
        in final_payloads
    )

    if before_char_count <= 0:
        reduction_ratio = 0.0
    else:
        reduction_ratio = (
            1.0
            - (
                after_char_count
                / before_char_count
            )
        )

    return CompressionResult(
        items=tuple(
            output
        ),
        trace=CompressionTrace(
            input_count=len(
                original_items
            ),
            output_count=len(
                output
            ),
            duplicate_count=(
                duplicate_count
            ),
            before_char_count=(
                before_char_count
            ),
            after_char_count=(
                after_char_count
            ),
            reduction_ratio=(
                reduction_ratio
            ),
            evidence_loss_count=(
                evidence_loss_count
            ),
            fallback_count=(
                fallback_count
            ),
            citation_answerable_before=(
                before_answerable
            ),
            citation_answerable_after=(
                after_answerable
            ),
        ),
    )