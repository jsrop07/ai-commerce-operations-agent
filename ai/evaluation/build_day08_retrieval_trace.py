from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from ai.retrieval.bm25 import (
    BM25Document,
    BM25Index,
)
from ai.retrieval.dense import (
    DenseDocument,
    DenseIndex,
)
from ai.retrieval.filters import (
    FilterConfidence,
    MetadataFilter,
)
from ai.retrieval.trace import (
    build_retrieval_trace,
    validate_retrieval_trace,
)
from ai.services.retrieval_service import (
    RetrievalMethod,
    RetrievalRequest,
    RetrievalService,
)


OUTPUT_PATH = Path(
    "artifacts/integration/day08/"
    "retrieval_trace.json"
)


def embed_texts(
    texts: list[str],
) -> np.ndarray:
    vectors: list[list[float]] = []

    for text in texts:
        lowered = text.casefold()

        if "스타터" in lowered:
            vectors.append(
                [1.0, 0.0]
            )
        elif "페인트" in lowered:
            vectors.append(
                [0.0, 1.0]
            )
        else:
            vectors.append(
                [0.5, 0.5]
            )

    return np.asarray(
        vectors,
        dtype=np.float32,
    )


def main() -> int:
    bm25_documents = [
        BM25Document(
            chunk_id="chunk-001",
            source_id="product-001",
            source_type="PRODUCT",
            version="v1",
            text="워해머 스타터 세트 입문용 상품",
            metadata={
                "title": "워해머 스타터 세트",
                "category": "starter",
                "language": "ko",
            },
        ),
        BM25Document(
            chunk_id="chunk-002",
            source_id="product-002",
            source_type="PRODUCT",
            version="v1",
            text="워해머 페인트 세트 도색용 상품",
            metadata={
                "title": "워해머 페인트 세트",
                "category": "paint",
                "language": "ko",
            },
        ),
    ]

    dense_documents = [
        DenseDocument(
            chunk_id=document.chunk_id,
            source_id=document.source_id,
            source_type=document.source_type,
            version=document.version,
            text=document.text,
            metadata=document.metadata,
        )
        for document in bm25_documents
    ]

    bm25_index = BM25Index(
        bm25_documents
    )

    dense_index = DenseIndex(
        dense_documents,
        embed_texts=embed_texts,
    )

    service = RetrievalService(
        bm25_index=bm25_index,
        dense_index=dense_index,
        bm25_index_version=(
            "bm25-day08-trace-v1"
        ),
        dense_index_version=(
            "dense-day08-trace-v1"
        ),
    )

    request = RetrievalRequest(
        query="워해머 스타터",
        method=RetrievalMethod.BM25,
        top_k=2,
        filters=(
            MetadataFilter(
                field="category",
                value="starter",
                confidence=(
                    FilterConfidence.EXACT
                ),
            ),
        ),
    )

    response = service.search(
        request
    )

    search_results = bm25_index.search(
        request.query,
        top_k=request.top_k,
        filters=request.filters,
    )

    trace = build_retrieval_trace(
        request=request,
        response=response,
        search_results=search_results,
        sanitized_query=(
            "워해머 스타터"
        ),
        rewritten_query=None,
    )

    errors = validate_retrieval_trace(
        trace
    )

    if errors:
        print(
            "RETRIEVAL_TRACE_VALIDATION_FAIL"
        )

        for error in errors:
            print(error)

        return 1

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            trace.to_dict(),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "RETRIEVAL_TRACE_OK"
    )
    print(
        f"PATH={OUTPUT_PATH}"
    )
    print(
        f"REQUEST_ID={trace.request_id}"
    )
    print(
        f"TRACE_ID={trace.trace_id}"
    )
    print(
        f"METHOD={trace.method}"
    )
    print(
        f"INDEX_VERSION={trace.index_version}"
    )
    print(
        f"CANDIDATE_COUNT="
        f"{len(trace.candidates_before_rerank)}"
    )
    print(
        f"CITATION_COUNT="
        f"{len(trace.citations)}"
    )
    print(
        f"CONFIDENCE={trace.confidence}"
    )
    print(
        f"ANSWER_STATUS="
        f"{trace.answer_status}"
    )
    print(
        f"RAW_PII_INCLUDED="
        f"{trace.raw_pii_included}"
    )
    print(
        f"PROVIDER_CALLS="
        f"{trace.provider_calls}"
    )
    print(
        f"TOOL_CALLS="
        f"{trace.tool_calls}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())