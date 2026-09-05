from dataclasses import dataclass

from ai.evaluation.analyze_fixed_chunking import (
    calculate_duplicate_ratio,
    summarize_chunks,
)


@dataclass
class DummyChunk:
    text: str
    token_count: int


def test_duplicate_ratio_zero_when_unique() -> None:
    chunks = [
        DummyChunk("alpha", 10),
        DummyChunk("beta", 20),
    ]

    assert calculate_duplicate_ratio(
        chunks
    ) == 0.0


def test_duplicate_ratio_detects_exact_duplicate() -> None:
    chunks = [
        DummyChunk("alpha", 10),
        DummyChunk("alpha", 10),
        DummyChunk("beta", 20),
    ]

    assert calculate_duplicate_ratio(
        chunks
    ) == 1 / 3


def test_summary_contains_length_statistics() -> None:
    chunks = [
        DummyChunk("a", 10),
        DummyChunk("b", 20),
        DummyChunk("c", 30),
    ]

    summary = summarize_chunks(chunks)

    assert summary["chunk_count"] == 3
    assert summary["min_tokens"] == 10
    assert summary["mean_tokens"] == 20
    assert summary["median_tokens"] == 20
    assert summary["max_tokens"] == 30