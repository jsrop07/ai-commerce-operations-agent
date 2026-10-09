from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from ai.retrieval.bm25 import BM25Document, BM25Index
from ai.retrieval.hybrid import reciprocal_rank_fusion
from ai.retrieval.reranker import (
    LocalCrossEncoderScorer,
    RerankCandidate,
    rerank_candidates,
)
from backend.app.services.c15_synthetic_seed import (
    TENANT_ID,
    generate_seed,
)
from backend.app.services.c16_pgvector_store import (
    EMBEDDING,
    build_c15_product_chunks,
    query_c15_products,
    vector_literal,
)
from sentence_transformers import SentenceTransformer


CANDIDATE_TOP_K = 8
RRF_K = 60
RERANK_CANDIDATE_TOP_K = 16
OUTPUT_TOP_K = 5

RESOLVE_MIN_SCORE = 0.10
RESOLVE_MIN_MARGIN = 0.15

@dataclass(frozen=True)
class RankedVectorHit:
    rank: int
    chunk_id: str
    source_id: str
    source_type: str
    version: str
    score: float
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ProductSearchHit:
    rank: int
    product_id: UUID
    product_code: str
    product_name: str
    rerank_score: float | None
    rrf_rank: int
    fallback: bool


def _build_bm25_index() -> BM25Index:
    documents = []

    for chunk in build_c15_product_chunks():
        documents.append(
            BM25Document(
                chunk_id=str(chunk.id),
                source_id=str(chunk.source_id),
                source_type=str(chunk.source_type),
                version=str(chunk.source_version),
                text=str(chunk.chunk_text),
                metadata={
                    "title": str(chunk.product_name),
                    "name": str(chunk.product_name),
                    "sku": str(chunk.product_code),
                    "category": ", ".join(
                        chunk.metadata.get(
                            "categories",
                            [],
                        )
                    ),
                    "language": "ko",
                    "brand": "",
                },
            )
        )

    return BM25Index(documents)


def _rank_vector_hits(hits) -> list[RankedVectorHit]:
    return [
        RankedVectorHit(
            rank=rank,
            chunk_id=f"{hit.source_id}:{hit.chunk_no}",
            source_id=str(hit.source_id),
            source_type=str(hit.source_type),
            version=str(hit.source_version),
            score=float(hit.score),
            metadata={},
        )
        for rank, hit in enumerate(
            hits,
            start=1,
        )
    ]

class ProductQueryEncoder:
    """One-time loaded C16-compatible query encoder."""

    def __init__(self) -> None:
        self._model = SentenceTransformer(
            EMBEDDING.model,
            revision=EMBEDDING.revision,
            device="cpu",
        )

    def encode(
        self,
        text: str,
    ):
        vectors = self._model.encode(
            [text],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        if len(vectors) != 1:
            raise ValueError(
                "C18_QUERY_EMBEDDING_COUNT"
            )

        vector = vectors[0]

        # C16과 동일한 dimension/vector validation 유지.
        vector_literal(vector)

        return vector

class ProductSearchService:
    def __init__(self) -> None:
        self._encoder = ProductQueryEncoder()
        self._bm25 = _build_bm25_index()

        self._chunks = {
            str(chunk.source_id): chunk
            for chunk in build_c15_product_chunks()
        }

        self._products = {
            str(product["id"]): product
            for product in generate_seed().products
        }

        self._reranker = LocalCrossEncoderScorer(
            device="cpu",
        )

    def search(
        self,
        session: Session,
        *,
        tenant_id: UUID,
        query: str,
        top_k: int = OUTPUT_TOP_K,
    ) -> list[ProductSearchHit]:
        if tenant_id != TENANT_ID:
            raise ValueError(
                "C18_PRODUCT_SEARCH_TENANT_FORBIDDEN"
            )

        normalized = query.strip()

        if not normalized:
            raise ValueError(
                "C18_PRODUCT_SEARCH_QUERY_EMPTY"
            )

        if top_k < 1 or top_k > OUTPUT_TOP_K:
            raise ValueError(
                "C18_PRODUCT_SEARCH_TOP_K_INVALID"
            )

        bm25_results = self._bm25.search(
            normalized,
            top_k=CANDIDATE_TOP_K,
        )

        query_vector = self._encoder.encode(
            normalized
        )

        vector_hits = query_c15_products(
            session,
            tenant_id=tenant_id,
            query_vector=query_vector,
            top_k=CANDIDATE_TOP_K,
        )

        dense_results = _rank_vector_hits(
            vector_hits
        )

        rrf_results = reciprocal_rank_fusion(
            bm25_results,
            dense_results,
            candidate_top_k=CANDIDATE_TOP_K,
            rrf_k=RRF_K,
        )

        candidates = []

        for result in rrf_results:
            source_id = str(result.source_id)
            chunk = self._chunks.get(source_id)

            if chunk is None:
                continue

            candidates.append(
                RerankCandidate(
                    original_rank=int(
                        result.rank
                    ),
                    source_id=source_id,
                    source_type=str(
                        result.source_type
                    ),
                    version=str(
                        result.version
                    ),
                    text=str(
                        chunk.chunk_text
                    ),
                    metadata={
                        "rrf_score": float(
                            result.score
                        ),
                    },
                )
            )

        outcome = rerank_candidates(
            normalized,
            candidates,
            scorer=self._reranker,
            candidate_top_k=(
                RERANK_CANDIDATE_TOP_K
            ),
            output_top_k=top_k,
        )

        hits = []

        for result in outcome.results:
            product = self._products.get(
                str(result.source_id)
            )

            if product is None:
                continue

            hits.append(
                ProductSearchHit(
                    rank=int(result.rank),
                    product_id=UUID(
                        str(result.source_id)
                    ),
                    product_code=str(
                        product["product_code"]
                    ),
                    product_name=str(
                        product["product_name"]
                    ),
                    rerank_score=(
                        None
                        if result.rerank_score
                        is None
                        else float(
                            result.rerank_score
                        )
                    ),
                    rrf_rank=int(
                        result.original_rank
                    ),
                    fallback=bool(
                        result.fallback
                    ),
                )
            )

        return hits
    
    def resolve_product_ids(
        self,
        session: Session,
        tenant_id: UUID,
        query: str,
    ) -> tuple[UUID, ...]:
        """Resolve only when Product identity is sufficiently unambiguous."""

        hits = self.search(
            session,
            tenant_id=tenant_id,
            query=query,
            top_k=2,
        )

        if not hits:
            return ()

        top1 = hits[0]

        # Reranker fallback이나 score 부재 상태에서는
        # 자동 Product identity를 확정하지 않는다.
        if (
            top1.fallback
            or top1.rerank_score is None
            or top1.rerank_score < RESOLVE_MIN_SCORE
        ):
            return ()

        if len(hits) == 1:
            return (top1.product_id,)

        top2 = hits[1]

        # 정상적인 CrossEncoder 비교가 불가능하면 fail closed.
        if (
            top2.fallback
            or top2.rerank_score is None
        ):
            return (
                top1.product_id,
                top2.product_id,
            )

        margin = (
            top1.rerank_score
            - top2.rerank_score
        )

        if margin < RESOLVE_MIN_MARGIN:
            # C18-3는 여러 UUID가 반환되면
            # ambiguous로 처리한다.
            return (
                top1.product_id,
                top2.product_id,
            )

        return (top1.product_id,)