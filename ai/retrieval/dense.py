from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence
from ai.retrieval.filters import (
    MetadataFilter,
    apply_metadata_filters,
)

import numpy as np


@dataclass(frozen=True)
class DenseDocument:
    """Dense 검색 Index에 들어가는 하나의 Chunk."""

    chunk_id: str
    source_id: str
    source_type: str
    version: str
    text: str
    metadata: Mapping[str, str]


@dataclass(frozen=True)
class DenseSearchResult:
    """Dense 검색 결과."""

    rank: int
    chunk_id: str
    source_id: str
    source_type: str
    version: str
    score: float
    metadata: Mapping[str, str]


def cosine_similarity(
    left: np.ndarray,
    right: np.ndarray,
) -> float:
    """
    두 Vector의 Cosine Similarity를 계산한다.
    """

    left = np.asarray(
        left,
        dtype=np.float32,
    )

    right = np.asarray(
        right,
        dtype=np.float32,
    )

    if left.ndim != 1 or right.ndim != 1:
        raise ValueError(
            "cosine_similarity expects "
            "1-dimensional vectors"
        )

    if left.shape != right.shape:
        raise ValueError(
            "vector dimensions must match"
        )

    left_norm = float(
        np.linalg.norm(left)
    )

    right_norm = float(
        np.linalg.norm(right)
    )

    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    return float(
        np.dot(left, right)
        / (
            left_norm
            * right_norm
        )
    )


def snapshot_to_dense_documents(
    rows: Sequence[Mapping[str, Any]],
) -> list[DenseDocument]:
    documents: list[DenseDocument] = []

    for row in rows:
        metadata = row.get(
            "metadata"
        ) or {}

        if not isinstance(
            metadata,
            Mapping,
        ):
            raise ValueError(
                "snapshot metadata must be "
                f"a mapping: {row.get('chunk_id')}"
            )

        documents.append(
            DenseDocument(
                chunk_id=str(
                    row["chunk_id"]
                ),
                source_id=str(
                    row["source_id"]
                ),
                source_type=str(
                    row["source_type"]
                ),
                version=str(
                    row["version"]
                ),
                text=str(
                    row["text"]
                ),
                metadata={
                    str(key): str(value)
                    for key, value
                    in metadata.items()
                },
            )
        )

    return documents


class DenseIndex:
    """
    Sentence embedding + cosine similarity 기반
    Dense Retrieval baseline.
    """

    def __init__(
        self,
        documents: Sequence[DenseDocument],
        *,
        embed_texts: Callable[
            [list[str]],
            np.ndarray,
        ],
    ) -> None:
        if not documents:
            raise ValueError(
                "documents must not be empty"
            )

        self.documents = list(
            documents
        )

        self._embed_texts = (
            embed_texts
        )

        texts = [
            document.text
            for document
            in self.documents
        ]

        embeddings = np.asarray(
            self._embed_texts(
                texts
            ),
            dtype=np.float32,
        )

        if embeddings.ndim != 2:
            raise ValueError(
                "document embeddings must "
                "be a 2-dimensional matrix"
            )

        if embeddings.shape[0] != len(
            self.documents
        ):
            raise ValueError(
                "embedding/document count mismatch"
            )

        if embeddings.shape[1] <= 0:
            raise ValueError(
                "embedding dimension must "
                "be greater than 0"
            )

        self._embeddings = (
            embeddings
        )

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
                "Dense document chunk_id must "
                "be unique"
            )

    @property
    def document_count(self) -> int:
        return len(
            self.documents
        )

    @property
    def vector_dimension(self) -> int:
        return int(
            self._embeddings.shape[1]
        )

    @property
    def embeddings(self) -> np.ndarray:
        return self._embeddings.copy()

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: Sequence[
            MetadataFilter
        ] | None = None,
    ) -> list[DenseSearchResult]:
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

        query_matrix = np.asarray(
            self._embed_texts(
                [query]
            ),
            dtype=np.float32,
        )

        if (
            query_matrix.ndim != 2
            or query_matrix.shape[0] != 1
        ):
            raise ValueError(
                "query embedding must have "
                "shape (1, dimension)"
            )

        if (
            query_matrix.shape[1]
            != self.vector_dimension
        ):
            raise ValueError(
                "query/document vector "
                "dimensions must match"
            )

        query_vector = (
            query_matrix[0]
        )

        scored: list[
            tuple[float, DenseDocument]
        ] = []

        for document in candidates:
            document_index = (
                self
                ._document_index_by_chunk_id[
                    document.chunk_id
                ]
            )

            document_vector = (
                self._embeddings[
                    document_index
                ]
            )

            score = cosine_similarity(
                query_vector,
                document_vector,
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
            DenseSearchResult
        ] = []

        for rank, (
            score,
            document,
        ) in enumerate(
            scored[:top_k],
            start=1,
        ):
            results.append(
                DenseSearchResult(
                    rank=rank,
                    chunk_id=(
                        document.chunk_id
                    ),
                    source_id=(
                        document.source_id
                    ),
                    source_type=(
                        document.source_type
                    ),
                    version=(
                        document.version
                    ),
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