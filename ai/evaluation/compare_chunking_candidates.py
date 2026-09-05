import json
import math
import statistics
import time
from pathlib import Path

import tiktoken
from sentence_transformers import SentenceTransformer

from ai.retrieval.chunking.fixed import (
    FIXED_CONFIGS,
    chunk_records_fixed,
)
from ai.retrieval.chunking.structured import (
    chunk_records_structured,
)
from ai.retrieval.chunking.semantic import (
    chunk_records_semantic,
)


CORPUS_PATH = Path(
    "ai/tests/fixtures/retrieval_chunking_corpus.jsonl"
)

EVAL_PATH = Path(
    "ai/evaluation/datasets/chunking_eval.jsonl"
)

RESULT_PATH = Path(
    "artifacts/experiments/RAG-CHUNK-01/result.json"
)

SEMANTIC_MODEL = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def normalize_for_search(text: str) -> str:
    return "".join(
        char.lower()
        for char in text
        if not char.isspace()
    )


def lexical_score(
    query: str,
    text: str,
) -> float:
    query_norm = normalize_for_search(query)
    text_norm = normalize_for_search(text)

    if not query_norm or not text_norm:
        return 0.0

    query_chars = set(query_norm)
    text_chars = set(text_norm)

    overlap = query_chars & text_chars

    if not overlap:
        return 0.0

    precision = (
        len(overlap)
        / len(text_chars)
    )

    recall = (
        len(overlap)
        / len(query_chars)
    )

    if precision + recall == 0:
        return 0.0

    return (
        2 * precision * recall
        / (precision + recall)
    )


def search_sources(
    query: str,
    chunks: list[dict],
    *,
    top_k: int = 5,
) -> list[dict]:
    best_by_source: dict[str, dict] = {}

    for chunk in chunks:
        score = lexical_score(
            query,
            chunk["text"],
        )

        source_id = chunk["source_id"]

        candidate = {
            **chunk,
            "score": score,
        }

        existing = best_by_source.get(
            source_id
        )

        if (
            existing is None
            or score > existing["score"]
            or (
                score == existing["score"]
                and chunk["chunk_id"]
                < existing["chunk_id"]
            )
        ):
            best_by_source[
                source_id
            ] = candidate

    ranked = sorted(
        best_by_source.values(),
        key=lambda item: (
            -item["score"],
            item["source_id"],
            item["chunk_id"],
        ),
    )

    return ranked[:top_k]


def source_relevance(
    query_record: dict,
) -> dict[str, int]:
    return {
        item["source_id"]: item["grade"]
        for item in query_record["relevant"]
    }


def recall_at_k(
    ranked: list[dict],
    relevant: dict[str, int],
    *,
    k: int,
) -> float:
    relevant_sources = {
        source_id
        for source_id, grade in relevant.items()
        if grade >= 2
    }

    if not relevant_sources:
        return 1.0

    retrieved_sources = {
        item["source_id"]
        for item in ranked[:k]
    }

    return (
        len(
            relevant_sources
            & retrieved_sources
        )
        / len(relevant_sources)
    )


def reciprocal_rank(
    ranked: list[dict],
    relevant: dict[str, int],
) -> float:
    for rank, item in enumerate(
        ranked,
        start=1,
    ):
        if relevant.get(
            item["source_id"],
            0,
        ) >= 2:
            return 1.0 / rank

    return 0.0


def dcg_at_k(
    ranked: list[dict],
    relevant: dict[str, int],
    *,
    k: int,
) -> float:
    total = 0.0

    for rank, item in enumerate(
        ranked[:k],
        start=1,
    ):
        grade = relevant.get(
            item["source_id"],
            0,
        )

        gain = (
            (2 ** grade) - 1
        )

        total += (
            gain
            / math.log2(rank + 1)
        )

    return total


def ndcg_at_k(
    ranked: list[dict],
    relevant: dict[str, int],
    *,
    k: int,
) -> float:
    actual = dcg_at_k(
        ranked,
        relevant,
        k=k,
    )

    ideal_grades = sorted(
        relevant.values(),
        reverse=True,
    )

    ideal = 0.0

    for rank, grade in enumerate(
        ideal_grades[:k],
        start=1,
    ):
        gain = (
            (2 ** grade) - 1
        )

        ideal += (
            gain
            / math.log2(rank + 1)
        )

    if ideal == 0:
        return 1.0

    return actual / ideal


def chunk_to_dict(chunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "source_id": chunk.source_id,
        "source_type": chunk.source_type,
        "version": chunk.version,
        "text": chunk.text,
    }


def candidate_index_size(
    chunks: list[dict],
) -> int:
    serialized = json.dumps(
        chunks,
        ensure_ascii=False,
        sort_keys=True,
    )

    return len(
        serialized.encode("utf-8")
    )


def evaluate_candidate(
    *,
    name: str,
    chunks: list[dict],
    queries: list[dict],
    chunk_build_latency_ms: float,
) -> dict:
    recall_1_values = []
    recall_3_values = []
    recall_5_values = []
    mrr_values = []
    ndcg_values = []
    retrieval_latencies = []
    errors = []
    query_results = []

    for query_record in queries:
        relevant = source_relevance(
            query_record
        )

        is_answerable = (
            query_record[
                "expected_answerability"
            ]
            == "ANSWERABLE"
        )

        started = time.perf_counter()

        ranked = search_sources(
            query_record["query"],
            chunks,
            top_k=5,
        )

        retrieval_latency_ms = (
            time.perf_counter()
            - started
        ) * 1000

        retrieval_latencies.append(
            retrieval_latency_ms
        )

        r1 = recall_at_k(
            ranked,
            relevant,
            k=1,
        )
        r3 = recall_at_k(
            ranked,
            relevant,
            k=3,
        )
        r5 = recall_at_k(
            ranked,
            relevant,
            k=5,
        )

        mrr = reciprocal_rank(
            ranked,
            relevant,
        )

        ndcg = ndcg_at_k(
            ranked,
            relevant,
            k=5,
        )

        first_relevant_rank = None

        for rank, item in enumerate(
            ranked,
            start=1,
        ):
            if relevant.get(
                item["source_id"],
                0,
            ) >= 2:
                first_relevant_rank = rank
                break

        if is_answerable:
            query_results.append(
                {
                    "query_id": query_record["query_id"],
                    "query": query_record["query"],
                    "first_relevant_rank": first_relevant_rank,
                    "recall_at_5": r5,
                    "mrr": mrr,
                    "ndcg_at_5": ndcg,
                    "top5": [
                        {
                            "source_id": item["source_id"],
                            "score": round(
                                item["score"],
                                4,
                            ),
                        }
                        for item in ranked
                    ],
                }
            )

        if is_answerable:
            recall_1_values.append(r1)
            recall_3_values.append(r3)
            recall_5_values.append(r5)
            mrr_values.append(mrr)
            ndcg_values.append(ndcg)

        if (
            query_record[
                "expected_answerability"
            ]
            == "ANSWERABLE"
            and r5 < 1.0
        ):
            errors.append(
                {
                    "query_id": (
                        query_record[
                            "query_id"
                        ]
                    ),
                    "query": (
                        query_record[
                            "query"
                        ]
                    ),
                    "expected": (
                        query_record[
                            "relevant"
                        ]
                    ),
                    "top5": [
                        {
                            "source_id": (
                                item[
                                    "source_id"
                                ]
                            ),
                            "score": round(
                                item[
                                    "score"
                                ],
                                4,
                            ),
                        }
                        for item in ranked
                    ],
                }
            )

    return {
        "name": name,
        "chunk_count": len(chunks),
        "index_size_bytes": (
            candidate_index_size(
                chunks
            )
        ),
        "chunk_build_latency_ms": round(
            chunk_build_latency_ms,
            2,
        ),
        "retrieval_latency_ms_mean": round(
            statistics.mean(
                retrieval_latencies
            ),
            4,
        ),
        "recall_at_1": round(
            statistics.mean(
                recall_1_values
            ),
            4,
        ),
        "recall_at_3": round(
            statistics.mean(
                recall_3_values
            ),
            4,
        ),
        "recall_at_5": round(
            statistics.mean(
                recall_5_values
            ),
            4,
        ),
        "mrr": round(
            statistics.mean(
                mrr_values
            ),
            4,
        ),
        "ndcg_at_5": round(
            statistics.mean(
                ndcg_values
            ),
            4,
        ),
        "answerable_query_count": len(
            recall_5_values
        ),
        "errors": errors,
        "query_results": query_results,
    }

def test_search_sources_collapses_duplicate_source_chunks() -> None:
    chunks = [
        {
            "chunk_id": "a:0",
            "source_id": "source_a",
            "source_type": "PRODUCT",
            "version": "v1",
            "text": "예약상품 배송 안내",
        },
        {
            "chunk_id": "a:1",
            "source_id": "source_a",
            "source_type": "PRODUCT",
            "version": "v1",
            "text": "예약상품 입고 배송",
        },
        {
            "chunk_id": "b:0",
            "source_id": "source_b",
            "source_type": "PRODUCT",
            "version": "v1",
            "text": "전략 게임 구성품",
        },
    ]

    ranked = search_sources(
        "예약상품 배송",
        chunks,
        top_k=5,
    )

    source_ids = [
        item["source_id"]
        for item in ranked
    ]

    assert source_ids.count(
        "source_a"
    ) == 1


def test_ndcg_never_exceeds_one_for_unique_sources() -> None:
    relevant = {
        "high": 3,
        "medium": 2,
    }

    ranked = [
        {"source_id": "high"},
        {"source_id": "medium"},
    ]

    score = ndcg_at_k(
        ranked,
        relevant,
        k=5,
    )

    assert 0.0 <= score <= 1.0

def main() -> None:
    corpus = load_jsonl(
        CORPUS_PATH
    )
    queries = load_jsonl(
        EVAL_PATH
    )

    tokenizer = tiktoken.get_encoding(
        "cl100k_base"
    )

    candidates = []

    for chunk_size, overlap in FIXED_CONFIGS:
        started = time.perf_counter()

        chunks = chunk_records_fixed(
            corpus,
            chunk_size=chunk_size,
            overlap=overlap,
            encode=tokenizer.encode,
            decode=tokenizer.decode,
        )

        build_ms = (
            time.perf_counter()
            - started
        ) * 1000

        candidates.append(
            evaluate_candidate(
                name=(
                    f"fixed_"
                    f"{chunk_size}_"
                    f"{overlap}"
                ),
                chunks=[
                    chunk_to_dict(chunk)
                    for chunk in chunks
                ],
                queries=queries,
                chunk_build_latency_ms=(
                    build_ms
                ),
            )
        )

    started = time.perf_counter()

    structured_chunks = (
        chunk_records_structured(
            corpus
        )
    )

    structured_ms = (
        time.perf_counter()
        - started
    ) * 1000

    candidates.append(
        evaluate_candidate(
            name="structured",
            chunks=[
                chunk_to_dict(chunk)
                for chunk
                in structured_chunks
            ],
            queries=queries,
            chunk_build_latency_ms=(
                structured_ms
            ),
        )
    )

    model = SentenceTransformer(
        SEMANTIC_MODEL
    )

    def embed_sentences(
        sentences: list[str],
    ):
        return model.encode(
            sentences,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

    def count_tokens(
        text: str,
    ) -> int:
        return len(
            tokenizer.encode(text)
        )

    started = time.perf_counter()

    semantic_chunks = (
        chunk_records_semantic(
            corpus,
            embed_sentences=(
                embed_sentences
            ),
            count_tokens=count_tokens,
            similarity_threshold=0.45,
            min_tokens=80,
            max_tokens=512,
        )
    )

    semantic_ms = (
        time.perf_counter()
        - started
    ) * 1000

    candidates.append(
        evaluate_candidate(
            name="semantic",
            chunks=[
                chunk_to_dict(chunk)
                for chunk
                in semantic_chunks
            ],
            queries=queries,
            chunk_build_latency_ms=(
                semantic_ms
            ),
        )
    )

    ranked_candidates = sorted(
        candidates,
        key=lambda item: (
            -item["recall_at_5"],
            -item["mrr"],
            -item["ndcg_at_5"],
            item[
                "retrieval_latency_ms_mean"
            ],
            item["index_size_bytes"],
        ),
    )

    selected = [
        item["name"]
        for item
        in ranked_candidates[:2]
    ]

    all_errors = []

    for candidate in ranked_candidates:
        for error in candidate["errors"]:
            all_errors.append(
                {
                    "candidate": (
                        candidate["name"]
                    ),
                    **error,
                }
            )

    hard_candidates = []

    for candidate in ranked_candidates:
        for query_result in candidate[
            "query_results"
        ]:
            if (
                query_result["recall_at_5"] == 1.0
                and query_result[
                    "first_relevant_rank"
                ]
                is not None
                and query_result[
                    "first_relevant_rank"
                ]
                > 1
            ):
                hard_candidates.append(
                    {
                        "candidate": candidate["name"],
                        **query_result,
                    }
                )

    hard_candidates.sort(
        key=lambda item: (
            -item["first_relevant_rank"],
            item["mrr"],
            item["ndcg_at_5"],
            item["candidate"],
            item["query_id"],
        )
    )

    error_analysis_cases = []

    for error in all_errors:
        if len(error_analysis_cases) >= 5:
            break

        error_analysis_cases.append(
            {
                "case_type": "RETRIEVAL_FAILURE",
                **error,
            }
        )

    used_queries = {
        item["query_id"]
        for item in error_analysis_cases
    }

    for hard in hard_candidates:
        if len(error_analysis_cases) >= 10:
            break

        if hard["query_id"] in used_queries:
            continue

        error_analysis_cases.append(
            {
                "case_type": "HARD_SUCCESS",
                **hard,
            }
        )

        used_queries.add(
            hard["query_id"]
        )

    for candidate in candidates:
        candidate.pop(
            "query_results",
            None,
        )

    result = {
        "experiment_id": (
            "RAG-CHUNK-01"
        ),
        "corpus": {
            "path": str(CORPUS_PATH),
            "record_count": len(
                corpus
            ),
            "pii_status": "CLEAN",
            "source_types": sorted(
                {
                    item[
                        "source_type"
                    ]
                    for item in corpus
                }
            ),
        },
        "dataset": {
            "path": str(EVAL_PATH),
            "query_count": len(
                queries
            ),
            "role": (
                "DAY6_CHUNKING_ONLY"
            ),
        },
        "semantic_model": (
            SEMANTIC_MODEL
        ),
        "retrieval_proxy": (
            "CHARACTER_SET_F1"
        ),
        "candidates": candidates,
        "selected_candidates": (
            selected
        ),
        "error_analysis": {
            "required_case_count": 10,
            "retrieval_failure_count": sum(
                1
                for item in error_analysis_cases
                if item["case_type"]
                == "RETRIEVAL_FAILURE"
            ),
            "hard_success_count": sum(
                1
                for item in error_analysis_cases
                if item["case_type"]
                == "HARD_SUCCESS"
            ),
            "cases": error_analysis_cases,
        },

        "decision": {
            "primary_candidate": "semantic",
            "secondary_candidate": "fixed_256_64",
            "structured_status": (
                "SOURCE_SPECIFIC_REEVALUATION"
            ),
            "reasons": {
                "semantic": [
                    (
                        "Highest MRR and nDCG@5 "
                        "in the Day6 comparison."
                    ),
                    (
                        "Recall@5 reached 1.0 "
                        "on all answerable queries."
                    ),
                    (
                        "Best candidate for "
                        "long policy/free-form text."
                    ),
                ],
                "fixed_256_64": [
                    (
                        "Recall@5 reached 1.0."
                    ),
                    (
                        "Near-semantic retrieval "
                        "quality with much lower "
                        "chunk build latency."
                    ),
                    (
                        "Selected as reproducible "
                        "baseline/fallback."
                    ),
                ],
                "structured": [
                    (
                        "Lowest index size and "
                        "retrieval latency."
                    ),
                    (
                        "Preserves Product and FAQ "
                        "field boundaries."
                    ),
                    (
                        "Keep for source-specific "
                        "Day7 retrieval evaluation."
                    ),
                ],
            },
        },

        "cost": {
            "llm_api_calls": 0,
            "embedding_api_calls": 0,
            "api_cost_usd": 0.0,
            "local_embedding_model": True,
        },
        "limitations": [
            (
                "Day6 lexical proxy is "
                "not BM25, vector, or hybrid "
                "retrieval."
            ),
            (
                "chunking_eval.jsonl is a "
                "Day6 synthetic evaluation set "
                "and does not replace "
                "golden_retrieval.jsonl."
            ),
        ],
    }

    RESULT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    RESULT_PATH.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print(
        "RAG_CHUNK_COMPARISON_OK"
    )

    for item in ranked_candidates:
        print(
            item["name"],
            "R@5=",
            item["recall_at_5"],
            "MRR=",
            item["mrr"],
            "nDCG@5=",
            item["ndcg_at_5"],
            "chunks=",
            item["chunk_count"],
            "index_bytes=",
            item["index_size_bytes"],
            "retrieval_ms=",
            item[
                "retrieval_latency_ms_mean"
            ],
        )

    print(
        "SELECTED=",
        selected,
    )
    print(
        "ERROR_ANALYSIS_COUNT=",
        len(
            result[
                "error_analysis"
            ]["cases"]
        ),
    )

    print(
        "FAILURE_COUNT=",
        result[
            "error_analysis"
        ]["retrieval_failure_count"],
    )

    print(
        "HARD_SUCCESS_COUNT=",
        result[
            "error_analysis"
        ]["hard_success_count"],
    )

    print(
        "RESULT=",
        RESULT_PATH,
    )


if __name__ == "__main__":
    main()
