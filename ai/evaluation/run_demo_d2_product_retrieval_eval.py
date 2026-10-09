from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any

from backend.app.core.config import Settings
from backend.app.db.session_v2 import (
    build_v2_engine,
    build_v2_session_factory,
)
from backend.app.services.c15_synthetic_seed import (
    TENANT_ID,
    generate_seed,
)
from backend.app.services.c16_pgvector_store import (
    EMBEDDING,
    build_c15_product_chunks,
    encode_fixed,
    query_c15_products,
)
from ai.retrieval.bm25 import (
    BM25Document,
    BM25Index,
)
from ai.retrieval.hybrid import reciprocal_rank_fusion
from ai.retrieval.reranker import (
    LocalCrossEncoderScorer,
    RerankCandidate,
    rerank_candidates,
)
from sentence_transformers import SentenceTransformer

CANDIDATE_TOP_K = 8
METRIC_TOP_K = 5
RRF_K = 60

# 실제 candidate 구성과 별개인 진단용 범위.
# D1 Dense Hero rank 12 finding을 추적하기 위해 사용한다.
DIAGNOSTIC_TOP_K = 50
RERANK_CANDIDATE_TOP_K = 16
RERANK_OUTPUT_TOP_K = 5
DIAG_PRODUCT_INDEXES = [
    0, 4, 8, 12,
    15, 30, 45, 59,
    60, 89, 119, 149,
]

NL12_CASES = [
    {
        "seed_index": 0,
        "query": "왕국 길 상품 찾아줘",
    },
    {
        "seed_index": 4,
        "query": "비밀 신호 제품 보여줘",
    },
    {
        "seed_index": 8,
        "query": "아침 시장 상품 검색해줘",
    },
    {
        "seed_index": 12,
        "query": "섬 탐험가들 찾아줘",
    },
    {
        "seed_index": 15,
        "query": "과수원 왕국 상품",
    },
    {
        "seed_index": 30,
        "query": "항구 상인 플러스 찾아줘",
    },
    {
        "seed_index": 45,
        "query": "투명 슬리브 찾아줘",
    },
    {
        "seed_index": 59,
        "query": "변경 순찰대 입문 제품",
    },
    {
        "seed_index": 60,
        "query": "폭풍 항구 확장 제품",
    },
    {
        "seed_index": 89,
        "query": "에어브러시 색상 제품 찾아줘",
    },
    {
        "seed_index": 119,
        "query": "투명 주사위 찾아줘",
    },
    {
        "seed_index": 149,
        "query": "상상력 선물 꾸러미 찾아줘",
    },
]

REJECT8_CASES = [
    {
        "query": "변경 순찰대 입문",
        "expected_decision": "AMBIGUOUS",
    },
    {
        "query": "폭풍 항구 확장",
        "expected_decision": "AMBIGUOUS",
    },
    {
        "query": "왕국 길",
        "expected_decision": "AMBIGUOUS",
    },
    {
        "query": "비밀 신호",
        "expected_decision": "AMBIGUOUS",
    },
    {
        "query": "재고가 부족한 이유 알려줘",
        "expected_decision": "NO_MATCH",
    },
    {
        "query": "오늘 처리할 업무 보여줘",
        "expected_decision": "NO_MATCH",
    },
    {
        "query": "예약 부족 원인 분석해줘",
        "expected_decision": "NO_MATCH",
    },
    {
        "query": "가장 인기 있는 상품 추천해줘",
        "expected_decision": "NO_MATCH",
    },
]

@dataclass(frozen=True)
class RankedVectorHit:
    rank: int
    chunk_id: str
    source_id: str
    source_type: str
    version: str
    score: float
    metadata: dict[str, str]

class FixedQueryEncoder:
    def __init__(self) -> None:
        started = time.perf_counter()

        self.model = SentenceTransformer(
            EMBEDDING.model,
            revision=EMBEDDING.revision,
            device="cpu",
        )

        self.model_load_ms = (
            time.perf_counter() - started
        ) * 1000.0

    def encode(self, text: str):
        started = time.perf_counter()

        vectors = self.model.encode(
            [text],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        elapsed_ms = (
            time.perf_counter() - started
        ) * 1000.0

        if len(vectors) != 1:
            raise ValueError("D2_QUERY_EMBEDDING_COUNT")

        return vectors[0], elapsed_ms
    
def _product_lookup(bundle) -> dict[str, dict[str, Any]]:
    return {
        str(product["id"]): product
        for product in bundle.products
    }
def _chunk_lookup():
    return {
        str(chunk.source_id): chunk
        for chunk in build_c15_product_chunks()
    }
def _diag_cases(bundle) -> list[dict[str, str | int]]:
    cases = []

    for index in DIAG_PRODUCT_INDEXES:
        product = bundle.products[index]

        cases.append(
            {
                "query": str(product["product_name"]),
                "expected_product_id": str(product["id"]),
                "product_code": str(product["product_code"]),
                "product_name": str(product["product_name"]),
                "seed_index": index,
            }
        )

    return cases

def _nl12_cases(bundle) -> list[dict[str, str | int]]:
    cases = []

    for item in NL12_CASES:
        index = int(item["seed_index"])
        product = bundle.products[index]

        cases.append(
            {
                "query": str(item["query"]),
                "expected_product_id": str(product["id"]),
                "product_code": str(product["product_code"]),
                "product_name": str(product["product_name"]),
                "seed_index": index,
            }
        )

    return cases

def _build_bm25_index() -> BM25Index:
    chunks = build_c15_product_chunks()

    documents = [
        BM25Document(
            chunk_id=str(chunk.id),
            source_id=str(chunk.source_id),
            source_type=str(chunk.source_type),
            version=str(chunk.source_version),
            text=str(chunk.chunk_text),
            metadata={
                "title": str(chunk.product_name),
                "name": str(chunk.product_name),
                "brand": "",
                "sku": str(chunk.product_code),
                "category": ", ".join(
                    chunk.metadata.get("categories", [])
                ),
                "language": "ko",
            },
        )
        for chunk in chunks
    ]

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
        for rank, hit in enumerate(hits, start=1)
    ]

def _build_rerank_candidates(
    rrf_results,
    chunks: dict[str, Any],
) -> list[RerankCandidate]:
    candidates = []

    for result in rrf_results:
        source_id = str(result.source_id)
        chunk = chunks.get(source_id)

        if chunk is None:
            raise ValueError(
                f"D2_RERANK_CHUNK_MISSING:{source_id}"
            )

        candidates.append(
            RerankCandidate(
                original_rank=int(result.rank),
                source_id=source_id,
                source_type=str(result.source_type),
                version=str(result.version),
                text=str(chunk.chunk_text),
                metadata={
                    "fusion_method": str(
                        result.fusion_method
                    ),
                    "rrf_score": float(
                        result.score
                    ),
                },
            )
        )

    return candidates

def _rank_of(results, source_id: str) -> int | None:
    for result in results:
        if str(result.source_id) == source_id:
            return int(result.rank)
    return None

def _rerank_rank_of(
    results,
    source_id: str,
) -> int | None:
    for result in results:
        if str(result.source_id) == source_id:
            return int(result.rank)

    return None
def _top_payload(
    results,
    products: dict[str, dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    payload = []

    for result in results[:top_k]:
        source_id = str(result.source_id)
        product = products.get(source_id, {})

        payload.append(
            {
                "rank": int(result.rank),
                "source_id": source_id,
                "product_code": product.get("product_code"),
                "product_name": product.get("product_name"),
                "score": float(result.score),
            }
        )

    return payload

def _rerank_payload(
    results,
    products: dict[str, dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    payload = []

    for result in results[:top_k]:
        source_id = str(result.source_id)
        product = products.get(source_id, {})

        payload.append(
            {
                "rank": int(result.rank),
                "original_rrf_rank": int(
                    result.original_rank
                ),
                "source_id": source_id,
                "product_code": product.get(
                    "product_code"
                ),
                "product_name": product.get(
                    "product_name"
                ),
                "rerank_score": (
                    None
                    if result.rerank_score is None
                    else float(result.rerank_score)
                ),
                "fallback": bool(
                    result.fallback
                ),
            }
        )

    return payload

def _evaluate_query(
    *,
    query: str,
    expected_product_id: str,
    bm25: BM25Index,
    session,
    products: dict[str, dict[str, Any]],
    encoder: FixedQueryEncoder,
    chunks: dict[str, Any],
    reranker: LocalCrossEncoderScorer,
) -> dict[str, Any]:
    # 실제 candidate retrieval
    bm25_started = time.perf_counter()
    bm25_candidates = bm25.search(
        query,
        top_k=CANDIDATE_TOP_K,
    )
    bm25_ms = (time.perf_counter() - bm25_started) * 1000.0
    query_vector, encode_ms = encoder.encode(query)

    dense_started = time.perf_counter()
    vector_hits = query_c15_products(
        session,
        tenant_id=TENANT_ID,
        query_vector=query_vector,
        top_k=CANDIDATE_TOP_K,
    )
    dense_ms = (time.perf_counter() - dense_started) * 1000.0
    dense_candidates = _rank_vector_hits(vector_hits)

    rrf_started = time.perf_counter()
    rrf_results = reciprocal_rank_fusion(
        bm25_candidates,
        dense_candidates,
        candidate_top_k=CANDIDATE_TOP_K,
        rrf_k=RRF_K,
    )
    rrf_ms = (time.perf_counter() - rrf_started) * 1000.0

    rerank_candidates_input = _build_rerank_candidates(
        rrf_results,
        chunks,
    )

    rerank_outcome = rerank_candidates(
        query,
        rerank_candidates_input,
        scorer=reranker,
        candidate_top_k=RERANK_CANDIDATE_TOP_K,
        output_top_k=RERANK_OUTPUT_TOP_K,
    )

    reranked_results = list(
        rerank_outcome.results
    )
    # 진단용 wider search.
    # candidate_top_k=8 평가 결과에는 절대 사용하지 않는다.
    bm25_diagnostic = bm25.search(
        query,
        top_k=DIAGNOSTIC_TOP_K,
    )

    diagnostic_vector_hits = query_c15_products(
        session,
        tenant_id=TENANT_ID,
        query_vector=query_vector,
        top_k=DIAGNOSTIC_TOP_K,
    )
    dense_diagnostic = _rank_vector_hits(
        diagnostic_vector_hits
    )

    bm25_candidate_rank = _rank_of(
        bm25_candidates,
        expected_product_id,
    )
    dense_candidate_rank = _rank_of(
        dense_candidates,
        expected_product_id,
    )
    rrf_rank = _rank_of(
        rrf_results,
        expected_product_id,
    )
    rerank_rank = _rerank_rank_of(
        reranked_results,
        expected_product_id,
    )
    bm25_diagnostic_rank = _rank_of(
        bm25_diagnostic,
        expected_product_id,
    )
    dense_diagnostic_rank = _rank_of(
        dense_diagnostic,
        expected_product_id,
    )

    return {
        "query": query,
        "expected_product_id": expected_product_id,
        "candidate": {
            "bm25_rank": bm25_candidate_rank,
            "dense_rank": dense_candidate_rank,
            "rrf_rank": rrf_rank,
            "rerank_rank": rerank_rank,
            "bm25_candidate_miss": bm25_candidate_rank is None,
            "dense_candidate_miss": dense_candidate_rank is None,
            "rrf_candidate_miss": rrf_rank is None,
        },
        "diagnostic": {
            "top_k": DIAGNOSTIC_TOP_K,
            "bm25_rank": bm25_diagnostic_rank,
            "dense_rank": dense_diagnostic_rank,
        },
        "top5": {
            "bm25": _top_payload(
                bm25_candidates,
                products,
                METRIC_TOP_K,
            ),
            "dense": _top_payload(
                dense_candidates,
                products,
                METRIC_TOP_K,
            ),
            "rrf": _top_payload(
                rrf_results,
                products,
                METRIC_TOP_K,
            ),
        },
        "reranked_top5": _rerank_payload(
            reranked_results,
            products,
            METRIC_TOP_K,
        ),
        "rerank_margin": (
            None
            if (
                len(reranked_results) < 2
                or reranked_results[0].rerank_score is None
                or reranked_results[1].rerank_score is None
            )
            else round(
                float(
                    reranked_results[0].rerank_score
                )
                - float(
                    reranked_results[1].rerank_score
                ),
                6,
            )
        ),
        "reranker": {
            "status": rerank_outcome.trace.status,
            "model": rerank_outcome.trace.model,
            "revision": rerank_outcome.trace.revision,
            "candidate_count": (
                rerank_outcome.trace.candidate_count
            ),
            "output_count": (
                rerank_outcome.trace.output_count
            ),
            "latency_ms": round(
                rerank_outcome.trace.latency_ms,
                3,
            ),
            "fallback_count": (
                rerank_outcome.trace.fallback_count
            ),
        },
        "latency_ms": {
            "bm25": round(bm25_ms, 3),
            "query_embedding": round(encode_ms, 3),
            "dense_pgvector": round(dense_ms, 3),
            "rrf_fusion": round(rrf_ms, 3),
        },
    }

def _reciprocal_rank(
    rank: int | None,
    *,
    cutoff: int,
) -> float:
    if rank is None or rank > cutoff:
        return 0.0

    return 1.0 / rank


def _aggregate_retriever_metrics(
    cases: list[dict[str, Any]],
    key: str,
) -> dict[str, float | int]:
    ranks = [
        case["candidate"][key]
        for case in cases
    ]

    hit5 = sum(
        rank is not None and rank <= METRIC_TOP_K
        for rank in ranks
    )

    hit8 = sum(
        rank is not None and rank <= CANDIDATE_TOP_K
        for rank in ranks
    )

    mrr5 = sum(
        _reciprocal_rank(
            rank,
            cutoff=METRIC_TOP_K,
        )
        for rank in ranks
    ) / len(ranks)

    return {
        "cases": len(ranks),
        "recall_at_5": round(
            hit5 / len(ranks),
            4,
        ),
        "candidate_recall_at_8": round(
            hit8 / len(ranks),
            4,
        ),
        "mrr_at_5": round(
            mrr5,
            4,
        ),
    }


def _aggregate_rrf_metrics(
    cases: list[dict[str, Any]],
) -> dict[str, float | int]:
    ranks = [
        case["candidate"]["rrf_rank"]
        for case in cases
    ]

    hit5 = sum(
        rank is not None and rank <= METRIC_TOP_K
        for rank in ranks
    )

    mrr5 = sum(
        _reciprocal_rank(
            rank,
            cutoff=METRIC_TOP_K,
        )
        for rank in ranks
    ) / len(ranks)

    return {
        "cases": len(ranks),
        "recall_at_5": round(
            hit5 / len(ranks),
            4,
        ),
        "mrr_at_5": round(
            mrr5,
            4,
        ),
    }

def _aggregate_rerank_metrics(
    cases: list[dict[str, Any]],
) -> dict[str, float | int]:
    ranks = [
        case["candidate"]["rerank_rank"]
        for case in cases
    ]

    hit5 = sum(
        rank is not None
        and rank <= RERANK_OUTPUT_TOP_K
        for rank in ranks
    )

    mrr5 = sum(
        _reciprocal_rank(
            rank,
            cutoff=RERANK_OUTPUT_TOP_K,
        )
        for rank in ranks
    ) / len(ranks)

    return {
        "cases": len(ranks),
        "recall_at_5": round(
            hit5 / len(ranks),
            4,
        ),
        "mrr_at_5": round(
            mrr5,
            4,
        ),
    }

def main() -> None:
    bundle = generate_seed()
    products = _product_lookup(bundle)

    hero_product_id = str(
        bundle.manifest["hero_product_id"]
    )
    hero = products[hero_product_id]

    bm25 = _build_bm25_index()
    encoder = FixedQueryEncoder()
    chunks = _chunk_lookup()

    reranker = LocalCrossEncoderScorer(
        device="cpu",
    )
    engine = build_v2_engine(
        Settings().postgres_v2_url
    )
    session_factory = build_v2_session_factory(
        engine
    )

    # Hero name/code는 소스에 하드코딩하지 않고 C15 seed에서 읽는다.
    queries = [
        str(hero["product_name"]),
        str(hero["product_code"]),
    ]
    diagnostic_inputs = _diag_cases(bundle)
    nl12_inputs = _nl12_cases(bundle)
    reject8_inputs = REJECT8_CASES
    try:
        with session_factory() as session:
            cases = [
                _evaluate_query(
                    query=query,
                    expected_product_id=hero_product_id,
                    bm25=bm25,
                    session=session,
                    products=products,
                    encoder=encoder,
                    chunks=chunks,
                    reranker=reranker,
                )
                for query in queries
            ]

            diagnostic_cases = [
                _evaluate_query(
                    query=item["query"],
                    expected_product_id=item["expected_product_id"],
                    bm25=bm25,
                    session=session,
                    products=products,
                    encoder=encoder,
                    chunks=chunks,
                    reranker=reranker,
                )
                for item in diagnostic_inputs
            ]
            nl12_cases = [
                _evaluate_query(
                    query=item["query"],
                    expected_product_id=item["expected_product_id"],
                    bm25=bm25,
                    session=session,
                    products=products,
                    encoder=encoder,
                    chunks=chunks,
                    reranker=reranker,
                )
                for item in nl12_inputs
            ]
            reject8_cases = []

            for item in reject8_inputs:
                case = _evaluate_query(
                    query=item["query"],
                    expected_product_id="00000000-0000-0000-0000-000000000000",
                    bm25=bm25,
                    session=session,
                    products=products,
                    encoder=encoder,
                    chunks=chunks,
                    reranker=reranker,
                )

                case["expected_product_id"] = None
                case["expected_decision"] = item[
                    "expected_decision"
                ]

                reject8_cases.append(case)
    finally:
        engine.dispose()

    output = {
        "task_id": "DEMO-D2-AI-01",
        "scope": "SYNTHETIC_DEMO_PRODUCT150_RETRIEVAL_BASELINE",
        "seed": {
            "version": bundle.manifest["seed_version"],
            "hash": bundle.manifest["seed_hash"],
            "tenant_id": bundle.manifest["tenant_id"],
            "product_count": bundle.manifest["counts"]["products"],
            "data_mode": bundle.manifest["data_mode"],
        },
        "embedding": {
            "model": EMBEDDING.model,
            "revision": EMBEDDING.revision,
            "dimension": EMBEDDING.dimension,
            "normalized": EMBEDDING.normalized,
        },
        "retrieval": {
            "candidate_top_k": CANDIDATE_TOP_K,
            "metric_top_k": METRIC_TOP_K,
            "rrf_k": RRF_K,
            "reranker_enabled": True,
            "diagnostic_top_k": DIAGNOSTIC_TOP_K,
        },
        "hero": {
            "product_id": hero_product_id,
            "product_code": hero["product_code"],
            "product_name": hero["product_name"],
        },
        "cases": cases,
        "diagnostic_suite": {
            "name": "D2_PRODUCT_DIAG12",
            "status": "DIAGNOSTIC_NOT_FINAL_EVAL",
            "query_type": "EXACT_PRODUCT_NAME",
            "case_count": len(diagnostic_cases),
            "metrics": {
                "bm25": _aggregate_retriever_metrics(
                    diagnostic_cases,
                    "bm25_rank",
                ),
                "dense": _aggregate_retriever_metrics(
                    diagnostic_cases,
                    "dense_rank",
                ),
                "rrf": _aggregate_rrf_metrics(
                    diagnostic_cases,
                ),
                "reranker": _aggregate_rerank_metrics(
                    diagnostic_cases,
                ),
            },
            "cases": diagnostic_cases,
        },
        "natural_query_suite": {
            "name": "D2_PRODUCT_NL12",
            "status": "DIAGNOSTIC_NOT_FINAL_EVAL",
            "query_type": "SHORTENED_NATURAL_PRODUCT_QUERY",
            "case_count": len(nl12_cases),
            "metrics": {
                "bm25": _aggregate_retriever_metrics(
                    nl12_cases,
                    "bm25_rank",
                ),
                "dense": _aggregate_retriever_metrics(
                    nl12_cases,
                    "dense_rank",
                ),
                "rrf": _aggregate_rrf_metrics(
                    nl12_cases,
                ),
                "reranker": _aggregate_rerank_metrics(
                    nl12_cases,
                ),
            },

            "cases": nl12_cases,
        },
        "reject_suite": {
            "name": "D2_PRODUCT_REJECT8",
            "status": "DIAGNOSTIC_NOT_FINAL_EVAL",
            "query_type": (
                "AMBIGUOUS_AND_NO_SINGLE_PRODUCT_TARGET"
            ),
            "case_count": len(reject8_cases),
            "purpose": (
                "Product UUID 자동 resolve 전에 "
                "ambiguity/no-match gate를 검증한다."
            ),
            "cases": reject8_cases,
        },
        "runtime": {
            "embedding_model_load_ms": round(
                encoder.model_load_ms,
                3,
            ),
            "model_load_count": 1,
        },
    }

    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()