from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
import re
from typing import Callable, Iterable, Sequence

from ai.retrieval.hybrid import (
    HybridSearchResult,
)
from ai.retrieval.query_preprocess import (
    normalize_query,
)


ELIGIBLE_SLICES = frozenset(
    {
        "compatibility",
        "policy",
    }
)

_MAX_QUERY_COUNT = 3
_MULTI_QUERY_RRF_K = 60

_TRAILING_PUNCTUATION = re.compile(
    r"[?!？！。.,]+$"
)

_REQUEST_SUFFIX_PATTERNS = (
    re.compile(
        r"\s*(알려줘|알려주세요|"
        r"확인해줘|확인해주세요|"
        r"보여줘|보여주세요|"
        r"찾아줘|찾아주세요)\s*$"
    ),
    re.compile(
        r"\s*(어떻게\s*돼|어떻게\s*돼요|"
        r"어떻게\s*되나요)\s*$"
    ),
)


@dataclass(frozen=True)
class MultiQueryCandidate:
    index: int
    query: str
    source: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "query": self.query,
            "source": self.source,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class MultiQueryMergedResult:
    rank: int
    source_id: str
    source_type: str
    version: str
    chunk_id: str
    score: float

    matched_query_indexes: tuple[int, ...]
    matched_queries: tuple[str, ...]
    combine_reason: str

    representative: HybridSearchResult

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "version": self.version,
            "chunk_id": self.chunk_id,
            "score": self.score,
            "matched_query_indexes": list(
                self.matched_query_indexes
            ),
            "matched_queries": list(
                self.matched_queries
            ),
            "combine_reason":
                self.combine_reason,
            "representative": {
                "rank":
                    self.representative.rank,
                "source_id":
                    self.representative.source_id,
                "source_type":
                    self.representative.source_type,
                "version":
                    self.representative.version,
                "chunk_id":
                    self.representative.chunk_id,
                "score":
                    self.representative.score,
                "fusion_method":
                    self.representative.fusion_method,
            },
        }


@dataclass(frozen=True)
class MultiQueryTrace:
    slice_name: str
    query_count: int
    retrieval_count: int
    unique_result_count: int
    dedupe_count: int

    single_query_recall: float | None
    multi_query_recall: float | None
    recall_change: float | None

    latency_ms: float
    api_cost_usd: float

    skipped: bool
    skip_reason: str | None

    def to_dict(self) -> dict[str, object]:
        return {
            "slice": self.slice_name,
            "query_count":
                self.query_count,
            "retrieval_count":
                self.retrieval_count,
            "unique_result_count":
                self.unique_result_count,
            "dedupe_count":
                self.dedupe_count,
            "single_query_recall":
                self.single_query_recall,
            "multi_query_recall":
                self.multi_query_recall,
            "recall_change":
                self.recall_change,
            "latency_ms":
                self.latency_ms,
            "api_cost_usd":
                self.api_cost_usd,
            "skipped":
                self.skipped,
            "skip_reason":
                self.skip_reason,
        }


@dataclass(frozen=True)
class MultiQueryRunResult:
    candidates: tuple[
        MultiQueryCandidate,
        ...
    ]
    results: tuple[
        MultiQueryMergedResult,
        ...
    ]
    trace: MultiQueryTrace

    def to_dict(self) -> dict[str, object]:
        return {
            "candidates": [
                item.to_dict()
                for item in self.candidates
            ],
            "results": [
                item.to_dict()
                for item in self.results
            ],
            "trace":
                self.trace.to_dict(),
        }


def _unique_preserve_order(
    values: Iterable[
        tuple[str, str, str]
    ],
) -> list[
    tuple[str, str, str]
]:
    output: list[
        tuple[str, str, str]
    ] = []

    seen: set[str] = set()

    for query, source, reason in values:
        cleaned = query.strip()

        if not cleaned:
            continue

        key = cleaned.casefold()

        if key in seen:
            continue

        seen.add(key)

        output.append(
            (
                cleaned,
                source,
                reason,
            )
        )

    return output


def _without_trailing_punctuation(
    query: str,
) -> str:
    return _TRAILING_PUNCTUATION.sub(
        "",
        query,
    ).strip()


def _without_request_suffix(
    query: str,
) -> str:
    output = query

    for pattern in _REQUEST_SUFFIX_PATTERNS:
        changed = pattern.sub(
            "",
            output,
        ).strip()

        if changed != output:
            return changed

    return output


def generate_multi_queries(
    query: str,
    *,
    slice_name: str,
    max_queries: int = _MAX_QUERY_COUNT,
) -> tuple[
    MultiQueryCandidate,
    ...
]:
    """
    D10-AI-02 Multi-query 후보 생성.

    안전 원칙:
    - compatibility / policy에만 기본 적용
    - 최대 3개
    - 새로운 alias / edition / language를 만들지 않음
    - 기존 query 표면형에서 제거 가능한
      문장부호/요청형 표현만 정리
    - exact product lookup에는 적용하지 않음
    """

    if max_queries <= 0:
        raise ValueError(
            "max_queries must be greater than 0"
        )

    max_queries = min(
        max_queries,
        _MAX_QUERY_COUNT,
    )

    normalized = normalize_query(
        query
    )

    if slice_name not in ELIGIBLE_SLICES:
        return (
            MultiQueryCandidate(
                index=0,
                query=normalized,
                source="ORIGINAL_QUERY",
                reason=(
                    "MULTI_QUERY_NOT_REQUIRED"
                ),
            ),
        )

    no_punctuation = (
        _without_trailing_punctuation(
            normalized
        )
    )

    no_request_suffix = (
        _without_request_suffix(
            no_punctuation
        )
    )

    candidates = (
        _unique_preserve_order(
            [
                (
                    normalized,
                    "ORIGINAL_QUERY",
                    "ORIGINAL_SURFACE",
                ),
                (
                    no_punctuation,
                    "ORIGINAL_QUERY",
                    (
                        "TRAILING_PUNCTUATION_"
                        "REMOVED"
                    ),
                ),
                (
                    no_request_suffix,
                    "ORIGINAL_QUERY",
                    (
                        "REQUEST_SUFFIX_"
                        "REMOVED"
                    ),
                ),
            ]
        )
    )

    return tuple(
        MultiQueryCandidate(
            index=index,
            query=value,
            source=source,
            reason=reason,
        )
        for index, (
            value,
            source,
            reason,
        )
        in enumerate(
            candidates[:max_queries]
        )
    )


def _recall(
    retrieved_source_ids: Sequence[str],
    relevant_source_ids: set[str],
) -> float:
    if not relevant_source_ids:
        return 0.0

    retrieved = set(
        retrieved_source_ids
    )

    return (
        len(
            retrieved
            & relevant_source_ids
        )
        / len(relevant_source_ids)
    )


def merge_multi_query_results(
    candidates: Sequence[
        MultiQueryCandidate
    ],
    batches: Sequence[
        Sequence[HybridSearchResult]
    ],
) -> tuple[
    MultiQueryMergedResult,
    ...
]:
    if len(candidates) != len(batches):
        raise ValueError(
            "candidate/batch count mismatch"
        )

    by_source: dict[
        str,
        dict[str, object],
    ] = {}

    for candidate, results in zip(
        candidates,
        batches,
        strict=True,
    ):
        seen_in_query: set[str] = set()

        for result in results:
            source_id = str(
                result.source_id
            )

            # 같은 query에서 동일 source의
            # 중복 chunk는 한 번만 반영한다.
            if source_id in seen_in_query:
                continue

            seen_in_query.add(
                source_id
            )

            row = by_source.get(
                source_id
            )

            component_score = (
                1.0
                / (
                    _MULTI_QUERY_RRF_K
                    + result.rank
                )
            )

            if row is None:
                by_source[source_id] = {
                    "source_id":
                        source_id,
                    "score":
                        component_score,
                    "best_result":
                        result,
                    "best_rank":
                        result.rank,
                    "query_indexes": [
                        candidate.index
                    ],
                    "queries": [
                        candidate.query
                    ],
                }
                continue

            row["score"] = (
                float(row["score"])
                + component_score
            )

            query_indexes = row[
                "query_indexes"
            ]

            queries = row["queries"]

            assert isinstance(
                query_indexes,
                list,
            )
            assert isinstance(
                queries,
                list,
            )

            query_indexes.append(
                candidate.index
            )
            queries.append(
                candidate.query
            )

            best_rank = int(
                row["best_rank"]
            )

            best_result = row[
                "best_result"
            ]

            if (
                result.rank < best_rank
                or (
                    result.rank
                    == best_rank
                    and result.source_id
                    < best_result.source_id
                )
            ):
                row["best_rank"] = (
                    result.rank
                )
                row["best_result"] = (
                    result
                )

    ordered = sorted(
        by_source.values(),
        key=lambda row: (
            -float(row["score"]),
            int(row["best_rank"]),
            str(row["source_id"]),
        ),
    )

    merged: list[
        MultiQueryMergedResult
    ] = []

    for rank, row in enumerate(
        ordered,
        start=1,
    ):
        representative = row[
            "best_result"
        ]

        query_indexes = tuple(
            int(value)
            for value
            in row["query_indexes"]
        )

        queries = tuple(
            str(value)
            for value
            in row["queries"]
        )

        combine_reason = (
            "MATCHED_MULTIPLE_QUERIES"
            if len(query_indexes) > 1
            else "MATCHED_SINGLE_QUERY"
        )

        merged.append(
            MultiQueryMergedResult(
                rank=rank,
                source_id=(
                    representative.source_id
                ),
                source_type=(
                    representative.source_type
                ),
                version=(
                    representative.version
                ),
                chunk_id=(
                    representative.chunk_id
                ),
                score=float(
                    row["score"]
                ),
                matched_query_indexes=(
                    query_indexes
                ),
                matched_queries=queries,
                combine_reason=(
                    combine_reason
                ),
                representative=(
                    representative
                ),
            )
        )

    return tuple(merged)


def run_multi_query(
    query: str,
    *,
    slice_name: str,
    search_fn: Callable[
        [str],
        Sequence[HybridSearchResult],
    ],
    relevant_source_ids: Iterable[
        str
    ]
    | None = None,
    max_queries: int = _MAX_QUERY_COUNT,
    api_cost_usd: float = 0.0,
) -> MultiQueryRunResult:
    """
    후보 생성 → 검색 → source_id 중복합치기 →
    recall/latency/cost 기록.

    search_fn은 기존 Hybrid 검색 계층을
    주입받는다. 이 모듈은 외부 API를 직접
    호출하지 않는다.
    """

    if api_cost_usd < 0:
        raise ValueError(
            "api_cost_usd must not be negative"
        )

    candidates = generate_multi_queries(
        query,
        slice_name=slice_name,
        max_queries=max_queries,
    )

    started = perf_counter()

    batches = [
        tuple(
            search_fn(
                candidate.query
            )
        )
        for candidate in candidates
    ]

    latency_ms = (
        perf_counter()
        - started
    ) * 1000.0

    merged = merge_multi_query_results(
        candidates,
        batches,
    )

    retrieval_count = sum(
        len(batch)
        for batch in batches
    )

    unique_result_count = len(
        merged
    )

    dedupe_count = (
        retrieval_count
        - unique_result_count
    )

    relevant = (
        {
            str(value)
            for value
            in relevant_source_ids
        }
        if relevant_source_ids
        is not None
        else None
    )

    single_query_recall: (
        float | None
    ) = None

    multi_query_recall: (
        float | None
    ) = None

    recall_change: (
        float | None
    ) = None

    if relevant is not None:
        first_batch_ids = [
            str(result.source_id)
            for result
            in batches[0]
        ]

        merged_ids = [
            result.source_id
            for result
            in merged
        ]

        single_query_recall = _recall(
            first_batch_ids,
            relevant,
        )

        multi_query_recall = _recall(
            merged_ids,
            relevant,
        )

        recall_change = (
            multi_query_recall
            - single_query_recall
        )

    skipped = (
        slice_name
        not in ELIGIBLE_SLICES
    )

    trace = MultiQueryTrace(
        slice_name=slice_name,
        query_count=len(
            candidates
        ),
        retrieval_count=(
            retrieval_count
        ),
        unique_result_count=(
            unique_result_count
        ),
        dedupe_count=(
            dedupe_count
        ),
        single_query_recall=(
            single_query_recall
        ),
        multi_query_recall=(
            multi_query_recall
        ),
        recall_change=(
            recall_change
        ),
        latency_ms=latency_ms,
        api_cost_usd=api_cost_usd,
        skipped=skipped,
        skip_reason=(
            "SLICE_NOT_MULTI_QUERY_ELIGIBLE"
            if skipped
            else None
        ),
    )

    return MultiQueryRunResult(
        candidates=candidates,
        results=merged,
        trace=trace,
    )