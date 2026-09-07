from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import math
import re
from typing import Any, Iterable, Mapping, Sequence
from ai.retrieval.filters import (
    MetadataFilter,
    apply_metadata_filters,
)

# Day 7 BM25 baseline의 명시적 설정값.
# 현재 fixture에 brand / sku가 없으므로 실제 검색 점수에는 영향을 주지 않는다.
# 이후 Sanitized/Canonical Product Seed에 해당 필드가 존재할 때만 사용된다.
DEFAULT_FIELD_WEIGHTS: dict[str, float] = {
    "sku": 4.0,
    "name": 3.0,
    "brand": 2.5,
    "title": 3.0,
    "category": 1.5,
    "content": 1.0,
}


_TOKEN_PATTERN = re.compile(
    r"[0-9A-Za-z가-힣]+",
    flags=re.UNICODE,
)


@dataclass(frozen=True)
class BM25Config:
    """BM25 계산 설정."""

    k1: float = 1.5
    b: float = 0.75
    field_weights: Mapping[str, float] = field(
        default_factory=lambda: dict(
            DEFAULT_FIELD_WEIGHTS
        )
    )

    def __post_init__(self) -> None:
        if self.k1 <= 0:
            raise ValueError(
                "k1 must be greater than 0"
            )

        if not 0.0 <= self.b <= 1.0:
            raise ValueError(
                "b must be between 0 and 1"
            )

        for field_name, weight in (
            self.field_weights.items()
        ):
            if weight < 0:
                raise ValueError(
                    f"field weight must be >= 0: "
                    f"{field_name}"
                )


@dataclass(frozen=True)
class BM25Document:
    """검색 Index에 들어가는 하나의 Chunk."""

    chunk_id: str
    source_id: str
    source_type: str
    version: str
    text: str
    metadata: Mapping[str, str]


@dataclass(frozen=True)
class BM25SearchResult:
    """BM25 검색 결과."""

    rank: int
    chunk_id: str
    source_id: str
    source_type: str
    version: str
    score: float
    metadata: Mapping[str, str]


def tokenize(text: str) -> list[str]:
    """
    Day 7 BM25 baseline용 결정론적 tokenizer.

    한국어 형태소 분석기를 추가하지 않고
    영문/숫자/한글 문자열을 lexical token으로 나눈다.
    """

    if not text:
        return []

    return [
        token.lower()
        for token in _TOKEN_PATTERN.findall(
            text
        )
    ]


def _string_value(value: Any) -> str:
    """None 등을 안전하게 빈 문자열로 변환한다."""

    if value is None:
        return ""

    if isinstance(value, str):
        return value

    return str(value)


def _record_identity(
    record: Mapping[str, Any],
) -> tuple[str, str]:
    return (
        _string_value(record.get("source_id")),
        _string_value(record.get("version")),
    )


def build_bm25_documents(
    *,
    chunks: Iterable[Any],
    records: Sequence[Mapping[str, Any]],
) -> list[BM25Document]:
    """
    Day 6 Chunk와 원본 CLEAN fixture metadata를 연결한다.

    중요한 점:
    - source_id만 쓰지 않고 version까지 같이 사용한다.
    - fixture에 없는 brand/SKU 값을 만들어내지 않는다.
    """

    records_by_identity = {
        _record_identity(record): record
        for record in records
    }

    documents: list[BM25Document] = []

    for chunk in chunks:
        identity = (
            _string_value(chunk.source_id),
            _string_value(chunk.version),
        )

        record = records_by_identity.get(identity)

        if record is None:
            raise ValueError(
                "matching source record not found for "
                f"chunk={chunk.chunk_id}, "
                f"source_id={chunk.source_id}, "
                f"version={chunk.version}"
            )

        fields = record.get("fields") or {}

        if not isinstance(fields, Mapping):
            raise ValueError(
                "record fields must be a mapping: "
                f"{identity}"
            )

        metadata = {
            "title": _string_value(
                record.get("title")
            ),
            "name": _string_value(
                fields.get("name")
            ),
            "brand": _string_value(
                fields.get("brand")
            ),
            "sku": _string_value(
                fields.get("sku")
            ),
            "category": _string_value(
                fields.get("category")
            ),
            "language": _string_value(
                fields.get("language")
            ),
        }

        documents.append(
            BM25Document(
                chunk_id=_string_value(
                    chunk.chunk_id
                ),
                source_id=_string_value(
                    chunk.source_id
                ),
                source_type=_string_value(
                    chunk.source_type
                ),
                version=_string_value(
                    chunk.version
                ),
                text=_string_value(
                    chunk.text
                ),
                metadata=metadata,
            )
        )

    return documents


class BM25Index:
    """
    Field-weighted BM25 baseline.

    각 field를 별도로 BM25 scoring한 뒤
    field weight를 곱해 합산한다.
    """

    def __init__(
        self,
        documents: Sequence[BM25Document],
        config: BM25Config | None = None,
    ) -> None:
        if not documents:
            raise ValueError(
                "documents must not be empty"
            )

        self.documents = list(documents)
        self.config = config or BM25Config()

        self._field_tokens: dict[
            str,
            list[list[str]],
        ] = {}

        self._field_term_frequencies: dict[
            str,
            list[Counter[str]],
        ] = {}

        self._field_document_frequencies: dict[
            str,
            Counter[str],
        ] = {}

        self._field_average_lengths: dict[
            str,
            float,
        ] = {}

        self._build()

        self._document_index_by_chunk_id = {
            document.chunk_id: index
            for index, document
            in enumerate(self.documents)
        }

        if (
            len(
                self._document_index_by_chunk_id
            )
            != len(self.documents)
        ):
            raise ValueError(
                "BM25 document chunk_id must "
                "be unique"
            )

    @property
    def document_count(self) -> int:
        return len(self.documents)

    def _field_text(
        self,
        document: BM25Document,
        field_name: str,
    ) -> str:
        if field_name == "content":
            return document.text

        return _string_value(
            document.metadata.get(field_name)
        )

    def _build(self) -> None:
        """
        각 field의 token/TF/DF/평균 길이를 계산한다.
        """

        for field_name in (
            self.config.field_weights
        ):
            tokenized_documents: list[
                list[str]
            ] = []

            term_frequencies: list[
                Counter[str]
            ] = []

            document_frequency: Counter[
                str
            ] = Counter()

            total_length = 0

            for document in self.documents:
                tokens = tokenize(
                    self._field_text(
                        document,
                        field_name,
                    )
                )

                tokenized_documents.append(
                    tokens
                )

                frequencies = Counter(tokens)

                term_frequencies.append(
                    frequencies
                )

                document_frequency.update(
                    set(tokens)
                )

                total_length += len(tokens)

            self._field_tokens[
                field_name
            ] = tokenized_documents

            self._field_term_frequencies[
                field_name
            ] = term_frequencies

            self._field_document_frequencies[
                field_name
            ] = document_frequency

            self._field_average_lengths[
                field_name
            ] = (
                total_length
                / len(self.documents)
            )

    def _idf(
        self,
        *,
        field_name: str,
        term: str,
    ) -> float:
        """
        BM25의 IDF.

        log(1 + (N - df + 0.5) / (df + 0.5))
        """

        document_frequency = (
            self._field_document_frequencies[
                field_name
            ].get(term, 0)
        )

        return math.log(
            1.0
            + (
                (
                    self.document_count
                    - document_frequency
                    + 0.5
                )
                / (
                    document_frequency
                    + 0.5
                )
            )
        )

    def _field_score(
        self,
        *,
        field_name: str,
        document_index: int,
        query_tokens: Sequence[str],
    ) -> float:
        term_frequency = (
            self._field_term_frequencies[
                field_name
            ][document_index]
        )

        document_length = len(
            self._field_tokens[
                field_name
            ][document_index]
        )

        average_length = (
            self._field_average_lengths[
                field_name
            ]
        )

        # 현재 corpus처럼 어떤 metadata field가
        # 모든 record에서 비어 있을 수도 있다.
        if average_length <= 0:
            return 0.0

        score = 0.0

        for term in set(query_tokens):
            frequency = term_frequency.get(
                term,
                0,
            )

            if frequency <= 0:
                continue

            idf = self._idf(
                field_name=field_name,
                term=term,
            )

            denominator = (
                frequency
                + self.config.k1
                * (
                    1.0
                    - self.config.b
                    + self.config.b
                    * (
                        document_length
                        / average_length
                    )
                )
            )

            term_score = (
                idf
                * (
                    frequency
                    * (
                        self.config.k1
                        + 1.0
                    )
                )
                / denominator
            )

            score += term_score

        return score

    def score_document(
        self,
        *,
        document_index: int,
        query: str,
    ) -> float:
        query_tokens = tokenize(query)

        if not query_tokens:
            return 0.0

        total_score = 0.0

        for (
            field_name,
            weight,
        ) in self.config.field_weights.items():
            if weight <= 0:
                continue

            field_score = self._field_score(
                field_name=field_name,
                document_index=document_index,
                query_tokens=query_tokens,
            )

            total_score += (
                weight
                * field_score
            )

        return total_score

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: Sequence[
            MetadataFilter
        ] | None = None,
    ) -> list[BM25SearchResult]:
        """
        BM25 검색.

        확정 metadata filter는 scoring 전에
        후보 문서에 적용한다.

        UNCERTAIN / no-match는
        filters.py의 fallback 정책에 따라
        recall을 강제로 차단하지 않는다.
        """

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than 0"
            )

        candidates = (
            apply_metadata_filters(
                self.documents,
                filters=filters or [],
            )
        )

        scored: list[
            tuple[float, BM25Document]
        ] = []

        for document in candidates:
            document_index = (
                self
                ._document_index_by_chunk_id[
                    document.chunk_id
                ]
            )

            score = self.score_document(
                document_index=(
                    document_index
                ),
                query=query,
            )

            scored.append(
                (
                    score,
                    document,
                )
            )

        scored.sort(
            key=lambda item: (
                -item[0],
                item[1].source_id,
                item[1].version,
                item[1].chunk_id,
            )
        )

        results: list[
            BM25SearchResult
        ] = []

        for rank, (
            score,
            document,
        ) in enumerate(
            scored[:top_k],
            start=1,
        ):
            results.append(
                BM25SearchResult(
                    rank=rank,
                    chunk_id=document.chunk_id,
                    source_id=document.source_id,
                    source_type=(
                        document.source_type
                    ),
                    version=document.version,
                    score=round(
                        score,
                        8,
                    ),
                    metadata=(
                        document.metadata
                    ),
                )
            )

        return results