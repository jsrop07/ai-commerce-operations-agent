from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class HybridSearchResult:
    """
    BM25 + Vector 결합 결과.

    source_id를 공통 identity로 사용한다.
    """

    rank: int
    source_id: str
    source_type: str
    version: str
    chunk_id: str
    score: float
    metadata: Mapping[str, str]

    bm25_rank: int | None
    vector_rank: int | None

    bm25_score: float | None
    vector_score: float | None

    bm25_normalized: float
    vector_normalized: float

    fusion_method: str


def _collapse_by_source(
    results: Sequence[Any],
) -> list[Any]:
    """
    동일 source_id가 여러 chunk로 존재할 경우
    가장 높은 순위의 결과 하나만 유지한다.
    """

    collapsed: list[Any] = []
    seen: set[str] = set()

    for result in sorted(
        results,
        key=lambda item: item.rank,
    ):
        source_id = str(
            result.source_id
        )

        if source_id in seen:
            continue

        seen.add(source_id)
        collapsed.append(result)

    return collapsed


def _prepare_candidates(
    results: Sequence[Any],
    *,
    candidate_top_k: int,
) -> list[Any]:
    if candidate_top_k <= 0:
        raise ValueError(
            "candidate_top_k must be greater than 0"
        )

    collapsed = _collapse_by_source(
        results
    )

    return collapsed[
        :candidate_top_k
    ]


def _min_max_normalize(
    results: Sequence[Any],
) -> dict[str, float]:
    """
    retriever별 score scale을 0~1로 맞춘다.

    후보가 1개이거나 모든 score가 동일하면
    해당 retriever 안에서 모두 1.0으로 처리한다.
    """

    if not results:
        return {}

    scores = [
        float(result.score)
        for result in results
    ]

    minimum = min(scores)
    maximum = max(scores)

    if maximum == minimum:
        return {
            str(result.source_id): 1.0
            for result in results
        }

    scale = maximum - minimum

    return {
        str(result.source_id): (
            float(result.score)
            - minimum
        )
        / scale
        for result in results
    }


def _result_map(
    results: Sequence[Any],
) -> dict[str, Any]:
    return {
        str(result.source_id): result
        for result in results
    }


def _representative(
    *,
    source_id: str,
    bm25_map: Mapping[str, Any],
    vector_map: Mapping[str, Any],
) -> Any:
    bm25 = bm25_map.get(
        source_id
    )

    vector = vector_map.get(
        source_id
    )

    if bm25 is None:
        return vector

    if vector is None:
        return bm25

    if bm25.rank <= vector.rank:
        return bm25

    return vector


def _sort_and_rank(
    rows: list[
        dict[str, Any]
    ],
    *,
    fusion_method: str,
) -> list[HybridSearchResult]:
    """
    score 동률 시:
    1. 더 좋은 component rank
    2. source_id
    순으로 deterministic하게 정렬한다.
    """

    def best_component_rank(
        row: dict[str, Any],
    ) -> int:
        ranks = [
            value
            for value in (
                row["bm25_rank"],
                row["vector_rank"],
            )
            if value is not None
        ]

        if not ranks:
            return 10**9

        return min(ranks)

    ordered = sorted(
        rows,
        key=lambda row: (
            -float(row["score"]),
            best_component_rank(row),
            str(row["source_id"]),
        ),
    )

    return [
        HybridSearchResult(
            rank=rank,
            source_id=row["source_id"],
            source_type=row["source_type"],
            version=row["version"],
            chunk_id=row["chunk_id"],
            score=float(
                row["score"]
            ),
            metadata=row["metadata"],
            bm25_rank=row["bm25_rank"],
            vector_rank=row["vector_rank"],
            bm25_score=row["bm25_score"],
            vector_score=row[
                "vector_score"
            ],
            bm25_normalized=float(
                row["bm25_normalized"]
            ),
            vector_normalized=float(
                row["vector_normalized"]
            ),
            fusion_method=(
                fusion_method
            ),
        )
        for rank, row
        in enumerate(
            ordered,
            start=1,
        )
    ]


def reciprocal_rank_fusion(
    bm25_results: Sequence[Any],
    vector_results: Sequence[Any],
    *,
    candidate_top_k: int = 20,
    rrf_k: int = 60,
) -> list[HybridSearchResult]:
    """
    Reciprocal Rank Fusion.

    raw BM25/Vector score 크기는 사용하지 않고
    각 retriever의 순위만 결합한다.
    """

    if rrf_k <= 0:
        raise ValueError(
            "rrf_k must be greater than 0"
        )

    bm25 = _prepare_candidates(
        bm25_results,
        candidate_top_k=(
            candidate_top_k
        ),
    )

    vector = _prepare_candidates(
        vector_results,
        candidate_top_k=(
            candidate_top_k
        ),
    )

    bm25_map = _result_map(
        bm25
    )

    vector_map = _result_map(
        vector
    )

    source_ids = (
        set(bm25_map)
        | set(vector_map)
    )

    rows: list[
        dict[str, Any]
    ] = []

    for source_id in source_ids:
        bm25_result = bm25_map.get(
            source_id
        )

        vector_result = (
            vector_map.get(
                source_id
            )
        )

        score = 0.0

        if bm25_result is not None:
            score += (
                1.0
                / (
                    rrf_k
                    + bm25_result.rank
                )
            )

        if vector_result is not None:
            score += (
                1.0
                / (
                    rrf_k
                    + vector_result.rank
                )
            )

        representative = (
            _representative(
                source_id=source_id,
                bm25_map=bm25_map,
                vector_map=vector_map,
            )
        )

        rows.append(
            {
                "source_id": source_id,
                "source_type": (
                    representative
                    .source_type
                ),
                "version": (
                    representative.version
                ),
                "chunk_id": (
                    representative.chunk_id
                ),
                "metadata": dict(
                    representative.metadata
                ),
                "score": score,
                "bm25_rank": (
                    bm25_result.rank
                    if bm25_result
                    is not None
                    else None
                ),
                "vector_rank": (
                    vector_result.rank
                    if vector_result
                    is not None
                    else None
                ),
                "bm25_score": (
                    float(
                        bm25_result.score
                    )
                    if bm25_result
                    is not None
                    else None
                ),
                "vector_score": (
                    float(
                        vector_result.score
                    )
                    if vector_result
                    is not None
                    else None
                ),
                "bm25_normalized": 0.0,
                "vector_normalized": 0.0,
            }
        )

    return _sort_and_rank(
        rows,
        fusion_method="RRF",
    )


def weighted_hybrid(
    bm25_results: Sequence[Any],
    vector_results: Sequence[Any],
    *,
    candidate_top_k: int = 20,
    bm25_weight: float = 0.5,
    vector_weight: float = 0.5,
) -> list[HybridSearchResult]:
    """
    Min-Max normalized weighted Hybrid.

    각 retriever score를 먼저 0~1로
    정규화한 뒤 가중합한다.
    """

    if (
        bm25_weight < 0
        or vector_weight < 0
    ):
        raise ValueError(
            "weights must not be negative"
        )

    total_weight = (
        bm25_weight
        + vector_weight
    )

    if total_weight <= 0:
        raise ValueError(
            "weight sum must be greater than 0"
        )

    normalized_bm25_weight = (
        bm25_weight
        / total_weight
    )

    normalized_vector_weight = (
        vector_weight
        / total_weight
    )

    bm25 = _prepare_candidates(
        bm25_results,
        candidate_top_k=(
            candidate_top_k
        ),
    )

    vector = _prepare_candidates(
        vector_results,
        candidate_top_k=(
            candidate_top_k
        ),
    )

    bm25_map = _result_map(
        bm25
    )

    vector_map = _result_map(
        vector
    )

    bm25_normalized = (
        _min_max_normalize(
            bm25
        )
    )

    vector_normalized = (
        _min_max_normalize(
            vector
        )
    )

    source_ids = (
        set(bm25_map)
        | set(vector_map)
    )

    rows: list[
        dict[str, Any]
    ] = []

    for source_id in source_ids:
        bm25_result = bm25_map.get(
            source_id
        )

        vector_result = (
            vector_map.get(
                source_id
            )
        )

        bm25_value = (
            bm25_normalized.get(
                source_id,
                0.0,
            )
        )

        vector_value = (
            vector_normalized.get(
                source_id,
                0.0,
            )
        )

        score = (
            normalized_bm25_weight
            * bm25_value
            + normalized_vector_weight
            * vector_value
        )

        representative = (
            _representative(
                source_id=source_id,
                bm25_map=bm25_map,
                vector_map=vector_map,
            )
        )

        rows.append(
            {
                "source_id": source_id,
                "source_type": (
                    representative
                    .source_type
                ),
                "version": (
                    representative.version
                ),
                "chunk_id": (
                    representative.chunk_id
                ),
                "metadata": dict(
                    representative.metadata
                ),
                "score": score,
                "bm25_rank": (
                    bm25_result.rank
                    if bm25_result
                    is not None
                    else None
                ),
                "vector_rank": (
                    vector_result.rank
                    if vector_result
                    is not None
                    else None
                ),
                "bm25_score": (
                    float(
                        bm25_result.score
                    )
                    if bm25_result
                    is not None
                    else None
                ),
                "vector_score": (
                    float(
                        vector_result.score
                    )
                    if vector_result
                    is not None
                    else None
                ),
                "bm25_normalized": (
                    bm25_value
                ),
                "vector_normalized": (
                    vector_value
                ),
            }
        )

    return _sort_and_rank(
        rows,
        fusion_method=(
            "WEIGHTED"
        ),
    )