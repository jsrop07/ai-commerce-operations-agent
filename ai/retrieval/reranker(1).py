from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError,
)
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Iterable, Sequence

from sentence_transformers import CrossEncoder


MODEL_NAME = "BAAI/bge-reranker-v2-m3"
MODEL_REVISION = (
    "953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e"
)
MODEL_LICENSE = "Apache-2.0"
MODEL_EXECUTION = "LOCAL"

DEFAULT_CANDIDATE_TOP_K = 30
DEFAULT_OUTPUT_TOP_K = 10
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 1


@dataclass(frozen=True)
class RerankCandidate:
    original_rank: int
    source_id: str
    source_type: str
    version: str
    text: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class RerankedResult:
    rank: int
    original_rank: int
    source_id: str
    source_type: str
    version: str
    text: str

    rerank_score: float | None
    metadata: dict[str, object]

    fallback: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "rank": self.rank,
            "original_rank":
                self.original_rank,
            "source_id":
                self.source_id,
            "source_type":
                self.source_type,
            "version":
                self.version,
            "text":
                self.text,
            "rerank_score":
                self.rerank_score,
            "metadata":
                self.metadata,
            "fallback":
                self.fallback,
        }


@dataclass(frozen=True)
class RerankTrace:
    model: str
    revision: str
    license: str
    execution: str

    candidate_count: int
    output_count: int

    latency_ms: float
    timeout_count: int
    retry_count: int
    fallback_count: int

    status: str

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "revision": self.revision,
            "license": self.license,
            "execution": self.execution,
            "candidate_count":
                self.candidate_count,
            "output_count":
                self.output_count,
            "latency_ms":
                self.latency_ms,
            "timeout_count":
                self.timeout_count,
            "retry_count":
                self.retry_count,
            "fallback_count":
                self.fallback_count,
            "status":
                self.status,
        }


@dataclass(frozen=True)
class RerankOutcome:
    results: tuple[
        RerankedResult,
        ...
    ]
    trace: RerankTrace

    def to_dict(self) -> dict[str, object]:
        return {
            "results": [
                item.to_dict()
                for item in self.results
            ],
            "trace":
                self.trace.to_dict(),
        }


class LocalCrossEncoderScorer:
    """
    로컬 CrossEncoder scorer.

    외부 inference API를 호출하지 않는다.
    최초 실행 시 Hugging Face 모델 파일을
    내려받을 수 있지만, 실제 scoring은 로컬에서 수행한다.
    """

    def __init__(
        self,
        *,
        model_name: str = MODEL_NAME,
        revision: str = MODEL_REVISION,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.revision = revision
        self.device = device

        self._model = CrossEncoder(
            model_name,
            revision=revision,
            trust_remote_code=False,
            device=device,
        )

    def __call__(
        self,
        pairs: Sequence[
            tuple[str, str]
        ],
    ) -> list[float]:
        if not pairs:
            return []

        scores = self._model.predict(
            list(pairs),
            show_progress_bar=False,
        )

        return [
            float(score)
            for score in scores
        ]


def _dedupe_candidates(
    candidates: Iterable[
        RerankCandidate
    ],
) -> list[RerankCandidate]:
    output: list[
        RerankCandidate
    ] = []

    seen: set[str] = set()

    for candidate in sorted(
        candidates,
        key=lambda item:
            item.original_rank,
    ):
        if candidate.source_id in seen:
            continue

        seen.add(
            candidate.source_id
        )

        output.append(
            candidate
        )

    return output


def _fallback_results(
    candidates: Sequence[
        RerankCandidate
    ],
    *,
    output_top_k: int,
) -> tuple[
    RerankedResult,
    ...
]:
    return tuple(
        RerankedResult(
            rank=index,
            original_rank=(
                candidate.original_rank
            ),
            source_id=(
                candidate.source_id
            ),
            source_type=(
                candidate.source_type
            ),
            version=(
                candidate.version
            ),
            text=(
                candidate.text
            ),
            rerank_score=None,
            metadata=dict(
                candidate.metadata
            ),
            fallback=True,
        )
        for index, candidate
        in enumerate(
            candidates[
                :output_top_k
            ],
            start=1,
        )
    )


def _score_with_timeout(
    scorer: Callable[
        [
            Sequence[
                tuple[str, str]
            ]
        ],
        Sequence[float],
    ],
    pairs: Sequence[
        tuple[str, str]
    ],
    *,
    timeout_seconds: float,
) -> list[float]:
    executor = ThreadPoolExecutor(
        max_workers=1
    )

    future = executor.submit(
        scorer,
        pairs,
    )

    try:
        values = future.result(
            timeout=timeout_seconds
        )

        return [
            float(value)
            for value in values
        ]

    except TimeoutError:
        future.cancel()
        raise

    finally:
        executor.shutdown(
            wait=False,
            cancel_futures=True,
        )


def rerank_candidates(
    query: str,
    candidates: Sequence[
        RerankCandidate
    ],
    *,
    scorer: Callable[
        [
            Sequence[
                tuple[str, str]
            ]
        ],
        Sequence[float],
    ],
    candidate_top_k: int = (
        DEFAULT_CANDIDATE_TOP_K
    ),
    output_top_k: int = (
        DEFAULT_OUTPUT_TOP_K
    ),
    timeout_seconds: float = (
        DEFAULT_TIMEOUT_SECONDS
    ),
    max_retries: int = (
        DEFAULT_MAX_RETRIES
    ),
) -> RerankOutcome:
    if not query.strip():
        raise ValueError(
            "query must not be empty"
        )

    if candidate_top_k <= 0:
        raise ValueError(
            "candidate_top_k must be greater than 0"
        )

    if output_top_k <= 0:
        raise ValueError(
            "output_top_k must be greater than 0"
        )

    if timeout_seconds <= 0:
        raise ValueError(
            "timeout_seconds must be greater than 0"
        )

    if max_retries < 0:
        raise ValueError(
            "max_retries must not be negative"
        )

    # Retry 폭주 방지
    max_retries = min(
        max_retries,
        2,
    )

    prepared = (
        _dedupe_candidates(
            candidates
        )[
            :candidate_top_k
        ]
    )

    if not prepared:
        return RerankOutcome(
            results=(),
            trace=RerankTrace(
                model=MODEL_NAME,
                revision=MODEL_REVISION,
                license=MODEL_LICENSE,
                execution=MODEL_EXECUTION,
                candidate_count=0,
                output_count=0,
                latency_ms=0.0,
                timeout_count=0,
                retry_count=0,
                fallback_count=0,
                status="NO_CANDIDATES",
            ),
        )

    pairs = [
        (
            query,
            candidate.text,
        )
        for candidate in prepared
    ]

    started = perf_counter()

    timeout_count = 0
    retry_count = 0

    scores: list[float] | None = None

    attempts = (
        1 + max_retries
    )

    for attempt in range(
        attempts
    ):
        try:
            scores = (
                _score_with_timeout(
                    scorer,
                    pairs,
                    timeout_seconds=(
                        timeout_seconds
                    ),
                )
            )

            break

        except TimeoutError:
            timeout_count += 1

        except Exception:
            # scoring failure도 bounded retry 후
            # safe fallback으로 처리한다.
            pass

        if attempt < (
            attempts - 1
        ):
            retry_count += 1

    latency_ms = (
        perf_counter()
        - started
    ) * 1000.0

    if (
        scores is None
        or len(scores)
        != len(prepared)
    ):
        fallback = (
            _fallback_results(
                prepared,
                output_top_k=(
                    output_top_k
                ),
            )
        )

        return RerankOutcome(
            results=fallback,
            trace=RerankTrace(
                model=MODEL_NAME,
                revision=MODEL_REVISION,
                license=MODEL_LICENSE,
                execution=MODEL_EXECUTION,
                candidate_count=(
                    len(prepared)
                ),
                output_count=(
                    len(fallback)
                ),
                latency_ms=(
                    latency_ms
                ),
                timeout_count=(
                    timeout_count
                ),
                retry_count=(
                    retry_count
                ),
                fallback_count=1,
                status="FALLBACK",
            ),
        )

    rows = list(
        zip(
            prepared,
            scores,
            strict=True,
        )
    )

    rows.sort(
        key=lambda item: (
            -float(item[1]),
            item[0].original_rank,
            item[0].source_id,
        )
    )

    reranked = tuple(
        RerankedResult(
            rank=index,
            original_rank=(
                candidate.original_rank
            ),
            source_id=(
                candidate.source_id
            ),
            source_type=(
                candidate.source_type
            ),
            version=(
                candidate.version
            ),
            text=(
                candidate.text
            ),
            rerank_score=float(
                score
            ),
            metadata=dict(
                candidate.metadata
            ),
            fallback=False,
        )
        for index, (
            candidate,
            score,
        )
        in enumerate(
            rows[
                :output_top_k
            ],
            start=1,
        )
    )

    return RerankOutcome(
        results=reranked,
        trace=RerankTrace(
            model=MODEL_NAME,
            revision=MODEL_REVISION,
            license=MODEL_LICENSE,
            execution=MODEL_EXECUTION,
            candidate_count=(
                len(prepared)
            ),
            output_count=(
                len(reranked)
            ),
            latency_ms=(
                latency_ms
            ),
            timeout_count=(
                timeout_count
            ),
            retry_count=(
                retry_count
            ),
            fallback_count=0,
            status="RERANKED",
        ),
    )