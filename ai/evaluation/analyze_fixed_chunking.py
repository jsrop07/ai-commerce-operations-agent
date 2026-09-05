import json
import statistics
from pathlib import Path

import tiktoken

from ai.retrieval.chunking.fixed import (
    FIXED_CONFIGS,
    chunk_records_fixed,
)


FIXTURE_PATH = Path(
    "ai/tests/fixtures/retrieval_chunking_corpus.jsonl"
)


def load_records() -> list[dict]:
    return [
        json.loads(line)
        for line in FIXTURE_PATH.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def calculate_duplicate_ratio(
    chunks,
) -> float:
    if not chunks:
        return 0.0

    normalized = [
        " ".join(chunk.text.split()).strip()
        for chunk in chunks
    ]

    duplicate_count = (
        len(normalized)
        - len(set(normalized))
    )

    return duplicate_count / len(normalized)


def summarize_chunks(
    chunks,
) -> dict:
    lengths = [
        chunk.token_count
        for chunk in chunks
    ]

    return {
        "chunk_count": len(chunks),
        "min_tokens": min(lengths),
        "mean_tokens": round(
            statistics.mean(lengths),
            2,
        ),
        "median_tokens": round(
            statistics.median(lengths),
            2,
        ),
        "max_tokens": max(lengths),
        "duplicate_ratio": round(
            calculate_duplicate_ratio(chunks),
            4,
        ),
    }


def main() -> None:
    records = load_records()
    encoding = tiktoken.get_encoding(
        "cl100k_base"
    )

    print("FIXED_CHUNKING_ANALYSIS")
    print(f"RECORD_COUNT={len(records)}")
    print("TOKENIZER=cl100k_base")

    for chunk_size, overlap in FIXED_CONFIGS:
        chunks = chunk_records_fixed(
            records,
            chunk_size=chunk_size,
            overlap=overlap,
            encode=encoding.encode,
            decode=encoding.decode,
        )

        summary = summarize_chunks(chunks)

        print()
        print(
            f"CONFIG={chunk_size}/{overlap}"
        )

        for key, value in summary.items():
            print(f"{key}={value}")


if __name__ == "__main__":
    main()