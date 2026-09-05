import json
import statistics
import time
from pathlib import Path

import tiktoken
from sentence_transformers import (
    SentenceTransformer,
)

from ai.retrieval.chunking.semantic import (
    chunk_records_semantic,
)


FIXTURE_PATH = Path(
    "ai/tests/fixtures/retrieval_chunking_corpus.jsonl"
)

MODEL_NAME = (
    "sentence-transformers/"
    "paraphrase-multilingual-MiniLM-L12-v2"
)


def load_records() -> list[dict]:
    return [
        json.loads(line)
        for line in FIXTURE_PATH.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def main() -> None:
    records = load_records()

    tokenizer = tiktoken.get_encoding(
        "cl100k_base"
    )

    model = SentenceTransformer(
        MODEL_NAME
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

    chunks = chunk_records_semantic(
        records,
        embed_sentences=embed_sentences,
        count_tokens=count_tokens,
        similarity_threshold=0.45,
        min_tokens=80,
        max_tokens=512,
    )

    elapsed_ms = (
        time.perf_counter()
        - started
    ) * 1000

    lengths = [
        chunk.token_count
        for chunk in chunks
    ]

    print("SEMANTIC_CHUNKING_ANALYSIS")
    print(f"MODEL={MODEL_NAME}")
    print(f"RECORD_COUNT={len(records)}")
    print(f"CHUNK_COUNT={len(chunks)}")
    print(f"MIN_TOKENS={min(lengths)}")
    print(
        "MEAN_TOKENS="
        f"{statistics.mean(lengths):.2f}"
    )
    print(
        "MEDIAN_TOKENS="
        f"{statistics.median(lengths):.2f}"
    )
    print(f"MAX_TOKENS={max(lengths)}")
    print(
        "LATENCY_MS="
        f"{elapsed_ms:.2f}"
    )

    for chunk in chunks:
        print(
            f"{chunk.chunk_id} "
            f"tokens={chunk.token_count} "
            f"sentences="
            f"{chunk.sentence_start}:"
            f"{chunk.sentence_end}"
        )


if __name__ == "__main__":
    main()