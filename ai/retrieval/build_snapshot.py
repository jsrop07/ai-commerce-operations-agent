from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import tiktoken
from sentence_transformers import SentenceTransformer

from ai.retrieval.bm25 import build_bm25_documents
from ai.retrieval.chunking.semantic import (
    chunk_records_semantic,
)


CORPUS_PATH = Path(
    "ai/tests/fixtures/"
    "retrieval_chunking_corpus.jsonl"
)

EVAL_PATH = Path(
    "ai/evaluation/datasets/"
    "chunking_eval.jsonl"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/"
    "RAG-01/chunk_snapshot.jsonl"
)

MANIFEST_PATH = Path(
    "artifacts/experiments/"
    "RAG-01/chunk_snapshot_manifest.json"
)


SNAPSHOT_SCHEMA_VERSION = (
    "retrieval-chunk-snapshot.v1"
)

CHUNKING_METHOD = "semantic"

CHUNKING_VERSION = "day06-semantic-v1"

TOKENIZER_NAME = "cl100k_base"

SEMANTIC_MODEL = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)

SIMILARITY_THRESHOLD = 0.45
MIN_TOKENS = 80
MAX_TOKENS = 512


def load_jsonl(
    path: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for line in path.read_text(
        encoding="utf-8"
    ).splitlines():
        if not line.strip():
            continue

        rows.append(
            json.loads(line)
        )

    return rows


def sha256_file(
    path: Path,
) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def sha256_text(
    text: str,
) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def resolve_model_revision(
    model: SentenceTransformer,
) -> str:
    """
    현재 로컬에서 실제 로드된 Hugging Face
    model revision / commit hash를 확인한다.

    재현 가능한 revision을 얻지 못하면
    조용히 'unknown'으로 진행하지 않고 실패한다.
    """

    candidates: list[Any] = []

    try:
        first_module = model[0]
    except Exception:
        first_module = None

    if first_module is not None:
        auto_model = getattr(
            first_module,
            "auto_model",
            None,
        )

        if auto_model is not None:
            config = getattr(
                auto_model,
                "config",
                None,
            )

            if config is not None:
                candidates.extend(
                    [
                        getattr(
                            config,
                            "_commit_hash",
                            None,
                        ),
                        getattr(
                            config,
                            "commit_hash",
                            None,
                        ),
                    ]
                )

    for candidate in candidates:
        if (
            isinstance(candidate, str)
            and candidate.strip()
        ):
            return candidate.strip()

    raise RuntimeError(
        "Could not resolve embedding model "
        "revision/commit hash. "
        "Day 7 requires a reproducible "
        "embedding model version."
    )


def validate_corpus(
    records: list[dict[str, Any]],
) -> None:
    if not records:
        raise ValueError(
            "corpus must not be empty"
        )

    for record in records:
        if record.get("pii_status") != "CLEAN":
            raise ValueError(
                "Only pii_status=CLEAN records "
                "may enter the Day 7 index: "
                f"{record.get('source_id')}"
            )

        required = {
            "source_id",
            "source_type",
            "version",
            "content",
        }

        missing = sorted(
            key
            for key in required
            if not record.get(key)
        )

        if missing:
            raise ValueError(
                "corpus record missing required "
                f"fields {missing}: "
                f"{record.get('source_id')}"
            )


def build_snapshot() -> dict[str, Any]:
    records = load_jsonl(
        CORPUS_PATH
    )

    queries = load_jsonl(
        EVAL_PATH
    )

    validate_corpus(records)

    tokenizer = tiktoken.get_encoding(
        TOKENIZER_NAME
    )

    model = SentenceTransformer(
        SEMANTIC_MODEL
    )

    model_revision = (
        resolve_model_revision(model)
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

    chunks = chunk_records_semantic(
        records,
        embed_sentences=(
            embed_sentences
        ),
        count_tokens=count_tokens,
        similarity_threshold=(
            SIMILARITY_THRESHOLD
        ),
        min_tokens=MIN_TOKENS,
        max_tokens=MAX_TOKENS,
    )

    documents = build_bm25_documents(
        chunks=chunks,
        records=records,
    )

    if len(chunks) != len(documents):
        raise RuntimeError(
            "chunk/document count mismatch"
        )

    snapshot_rows: list[
        dict[str, Any]
    ] = []

    for chunk, document in zip(
        chunks,
        documents,
        strict=True,
    ):
        snapshot_rows.append(
            {
                "schema_version": (
                    SNAPSHOT_SCHEMA_VERSION
                ),
                "chunk_id": (
                    chunk.chunk_id
                ),
                "source_id": (
                    chunk.source_id
                ),
                "source_type": (
                    chunk.source_type
                ),
                "version": (
                    chunk.version
                ),
                "chunk_index": (
                    chunk.chunk_index
                ),
                "text": (
                    chunk.text
                ),
                "token_count": (
                    chunk.token_count
                ),
                "sentence_start": (
                    chunk.sentence_start
                ),
                "sentence_end": (
                    chunk.sentence_end
                ),
                "metadata": dict(
                    document.metadata
                ),
            }
        )

    serialized_lines = [
        json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
        )
        for row in snapshot_rows
    ]

    serialized = (
        "\n".join(serialized_lines)
        + "\n"
    )

    snapshot_hash = sha256_text(
        serialized
    )

    corpus_source_ids = {
        row["source_id"]
        for row in records
    }

    relevant_source_ids = {
        relevant["source_id"]
        for query in queries
        for relevant in query.get(
            "relevant",
            [],
        )
        if relevant.get(
            "grade",
            0,
        ) >= 2
    }

    missing_relevant = sorted(
        relevant_source_ids
        - corpus_source_ids
    )

    answerable = [
        query
        for query in queries
        if query.get(
            "expected_answerability"
        )
        == "ANSWERABLE"
    ]

    covered_answerable = sum(
        1
        for query in answerable
        if any(
            relevant.get(
                "grade",
                0,
            ) >= 2
            and relevant.get(
                "source_id"
            )
            in corpus_source_ids
            for relevant
            in query.get(
                "relevant",
                [],
            )
        )
    )

    manifest = {
        "schema_version": (
            "retrieval-snapshot-manifest.v1"
        ),
        "snapshot_version": (
            "day07-semantic-v1"
        ),
        "snapshot_hash": (
            snapshot_hash
        ),
        "corpus": {
            "path": str(
                CORPUS_PATH
            ),
            "sha256": sha256_file(
                CORPUS_PATH
            ),
            "record_count": len(
                records
            ),
            "unique_source_count": len(
                corpus_source_ids
            ),
            "pii_required_status": (
                "CLEAN"
            ),
            "provider_raw_data_used": (
                False
            ),
        },
        "evaluation": {
            "path": str(
                EVAL_PATH
            ),
            "sha256": sha256_file(
                EVAL_PATH
            ),
            "query_count": len(
                queries
            ),
            "answerable_count": len(
                answerable
            ),
            "answerable_covered": (
                covered_answerable
            ),
            "answerable_coverage": (
                covered_answerable
                / len(answerable)
                if answerable
                else None
            ),
            "missing_relevant_source_ids": (
                missing_relevant
            ),
        },
        "chunking": {
            "method": (
                CHUNKING_METHOD
            ),
            "version": (
                CHUNKING_VERSION
            ),
            "chunk_count": len(
                snapshot_rows
            ),
            "similarity_threshold": (
                SIMILARITY_THRESHOLD
            ),
            "min_tokens": (
                MIN_TOKENS
            ),
            "max_tokens": (
                MAX_TOKENS
            ),
            "tokenizer": (
                TOKENIZER_NAME
            ),
        },
        "embedding": {
            "model": (
                SEMANTIC_MODEL
            ),
            "revision": (
                model_revision
            ),
            "normalized": True,
        },
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        serialized,
        encoding="utf-8",
    )

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return manifest


def main() -> None:
    manifest = build_snapshot()

    print(
        "RETRIEVAL_SNAPSHOT_BUILD_OK"
    )

    print(
        "SNAPSHOT_VERSION=",
        manifest[
            "snapshot_version"
        ],
    )

    print(
        "SNAPSHOT_HASH=",
        manifest[
            "snapshot_hash"
        ],
    )

    print(
        "CHUNK_COUNT=",
        manifest[
            "chunking"
        ][
            "chunk_count"
        ],
    )

    print(
        "MODEL=",
        manifest[
            "embedding"
        ][
            "model"
        ],
    )

    print(
        "MODEL_REVISION=",
        manifest[
            "embedding"
        ][
            "revision"
        ],
    )

    print(
        "ANSWERABLE_COVERAGE=",
        manifest[
            "evaluation"
        ][
            "answerable_coverage"
        ],
    )

    print(
        "MISSING_RELEVANT_SOURCE_COUNT=",
        len(
            manifest[
                "evaluation"
            ][
                "missing_relevant_source_ids"
            ]
        ),
    )

    print(
        "SNAPSHOT=",
        OUTPUT_PATH,
    )

    print(
        "MANIFEST=",
        MANIFEST_PATH,
    )


if __name__ == "__main__":
    main()