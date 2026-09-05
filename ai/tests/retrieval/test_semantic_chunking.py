import numpy as np
import pytest

from ai.retrieval.chunking.semantic import (
    chunk_semantic,
    cosine_similarity,
    find_change_points,
    split_sentences,
)


def count_chars(text: str) -> int:
    return len(text)


def test_split_sentences() -> None:
    sentences = split_sentences(
        "배송됩니다. 입고가 지연됩니다. 반품이 가능합니다."
    )

    assert len(sentences) == 3


def test_cosine_similarity_identical_vectors() -> None:
    vector = np.array(
        [1.0, 0.0],
        dtype=float,
    )

    assert cosine_similarity(
        vector,
        vector,
    ) == pytest.approx(1.0)


def test_change_point_detects_semantic_shift() -> None:
    embeddings = np.array(
        [
            [1.0, 0.0],
            [0.9, 0.1],
            [0.0, 1.0],
        ],
        dtype=float,
    )

    change_points = find_change_points(
        embeddings,
        similarity_threshold=0.5,
    )

    assert change_points == [2]


def test_semantic_chunking_uses_change_point() -> None:
    record = {
        "source_id": "policy_test",
        "source_type": "POLICY",
        "version": "v1",
        "content": (
            "배송 안내입니다. "
            "예약 상품도 배송합니다. "
            "교환 안내입니다. "
            "반품도 가능합니다."
        ),
    }

    def fake_embeddings(
        sentences: list[str],
    ) -> np.ndarray:
        assert len(sentences) == 4

        return np.array(
            [
                [1.0, 0.0],
                [0.9, 0.1],
                [0.0, 1.0],
                [0.1, 0.9],
            ],
            dtype=float,
        )

    chunks = chunk_semantic(
        record,
        embed_sentences=fake_embeddings,
        count_tokens=count_chars,
        similarity_threshold=0.5,
        min_tokens=1,
        max_tokens=1000,
    )

    assert len(chunks) == 2
    assert "배송 안내입니다." in chunks[0].text
    assert "교환 안내입니다." in chunks[1].text


def test_min_tokens_prevents_excessive_fragmentation() -> None:
    record = {
        "source_id": "policy_test",
        "source_type": "POLICY",
        "version": "v1",
        "content": (
            "가. 나. 다. 라."
        ),
    }

    def fake_embeddings(
        sentences: list[str],
    ) -> np.ndarray:
        return np.array(
            [
                [1.0, 0.0],
                [0.0, 1.0],
                [1.0, 0.0],
                [0.0, 1.0],
            ],
            dtype=float,
        )

    chunks = chunk_semantic(
        record,
        embed_sentences=fake_embeddings,
        count_tokens=count_chars,
        similarity_threshold=0.9,
        min_tokens=10,
        max_tokens=1000,
    )

    assert len(chunks) < 4


def test_invalid_min_max_tokens() -> None:
    record = {
        "source_id": "policy_test",
        "source_type": "POLICY",
        "version": "v1",
        "content": "테스트 문장입니다.",
    }

    with pytest.raises(ValueError):
        chunk_semantic(
            record,
            embed_sentences=lambda x: np.array([]),
            count_tokens=count_chars,
            min_tokens=100,
            max_tokens=50,
        )

def test_short_final_chunk_merges_with_previous() -> None:
    record = {
        "source_id": "policy_test",
        "source_type": "POLICY",
        "version": "v1",
        "content": (
            "aaaaaaaaaa. "
            "bbbbbbbbbb. "
            "cc."
        ),
    }

    def fake_embeddings(
        sentences: list[str],
    ) -> np.ndarray:
        return np.array(
            [
                [1.0, 0.0],
                [0.0, 1.0],
                [1.0, 0.0],
            ],
            dtype=float,
        )

    chunks = chunk_semantic(
        record,
        embed_sentences=fake_embeddings,
        count_tokens=count_chars,
        similarity_threshold=0.9,
        min_tokens=10,
        max_tokens=100,
    )

    assert chunks[-1].token_count >= 1