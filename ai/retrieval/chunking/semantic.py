from dataclasses import dataclass
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class SemanticChunk:
    chunk_id: str
    source_id: str
    source_type: str
    version: str
    chunk_index: int
    text: str
    sentence_start: int
    sentence_end: int
    token_count: int


def cosine_similarity(
    left: np.ndarray,
    right: np.ndarray,
) -> float:
    left_norm = np.linalg.norm(left)
    right_norm = np.linalg.norm(right)

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return float(
        np.dot(left, right)
        / (left_norm * right_norm)
    )


def split_sentences(text: str) -> list[str]:
    normalized = (
        text.replace("?", "?\n")
        .replace("!", "!\n")
        .replace(". ", ".\n")
    )

    return [
        sentence.strip()
        for sentence in normalized.splitlines()
        if sentence.strip()
    ]


def find_change_points(
    embeddings: np.ndarray,
    *,
    similarity_threshold: float,
) -> list[int]:
    change_points: list[int] = []

    for index in range(
        len(embeddings) - 1
    ):
        similarity = cosine_similarity(
            embeddings[index],
            embeddings[index + 1],
        )

        if similarity < similarity_threshold:
            change_points.append(index + 1)

    return change_points


def chunk_semantic(
    record: dict,
    *,
    embed_sentences: Callable[
        [list[str]],
        np.ndarray,
    ],
    count_tokens: Callable[[str], int],
    similarity_threshold: float = 0.45,
    min_tokens: int = 80,
    max_tokens: int = 512,
) -> list[SemanticChunk]:
    if min_tokens <= 0:
        raise ValueError(
            "min_tokens must be greater than 0"
        )

    if max_tokens < min_tokens:
        raise ValueError(
            "max_tokens must be >= min_tokens"
        )

    if not 0.0 <= similarity_threshold <= 1.0:
        raise ValueError(
            "similarity_threshold must be between 0 and 1"
        )

    sentences = split_sentences(
        record["content"]
    )

    if not sentences:
        return []

    if len(sentences) == 1:
        text = sentences[0]

        return [
            SemanticChunk(
                chunk_id=(
                    f"{record['source_id']}:"
                    f"{record['version']}:"
                    "semantic:0"
                ),
                source_id=record["source_id"],
                source_type=record["source_type"],
                version=record["version"],
                chunk_index=0,
                text=text,
                sentence_start=0,
                sentence_end=1,
                token_count=count_tokens(text),
            )
        ]

    embeddings = embed_sentences(sentences)

    if len(embeddings) != len(sentences):
        raise ValueError(
            "embedding count must match sentence count"
        )

    change_points = set(
        find_change_points(
            embeddings,
            similarity_threshold=similarity_threshold,
        )
    )

    chunks: list[SemanticChunk] = []

    current_sentences: list[str] = []
    current_start = 0
    chunk_index = 0

    for index, sentence in enumerate(
        sentences
    ):
        candidate = (
            " ".join(
                current_sentences
                + [sentence]
            )
        )

        candidate_tokens = count_tokens(
            candidate
        )

        should_split_for_size = (
            bool(current_sentences)
            and candidate_tokens > max_tokens
        )

        current_text = " ".join(
            current_sentences
        )

        current_tokens = (
            count_tokens(current_text)
            if current_sentences
            else 0
        )

        should_split_for_semantics = (
            bool(current_sentences)
            and index in change_points
            and current_tokens >= min_tokens
        )

        if (
            should_split_for_size
            or should_split_for_semantics
        ):
            chunks.append(
                SemanticChunk(
                    chunk_id=(
                        f"{record['source_id']}:"
                        f"{record['version']}:"
                        f"semantic:{chunk_index}"
                    ),
                    source_id=record["source_id"],
                    source_type=record["source_type"],
                    version=record["version"],
                    chunk_index=chunk_index,
                    text=current_text,
                    sentence_start=current_start,
                    sentence_end=index,
                    token_count=current_tokens,
                )
            )

            chunk_index += 1
            current_sentences = [sentence]
            current_start = index
        else:
            current_sentences.append(
                sentence
            )

    if current_sentences:
        final_text = " ".join(
            current_sentences
        )
        final_tokens = count_tokens(
            final_text
        )

        if (
            final_tokens < min_tokens
            and chunks
        ):
            previous = chunks[-1]

            merged_text = (
                f"{previous.text} {final_text}"
            )

            merged_tokens = count_tokens(
                merged_text
            )

            if merged_tokens <= max_tokens:
                chunks[-1] = SemanticChunk(
                    chunk_id=previous.chunk_id,
                    source_id=previous.source_id,
                    source_type=previous.source_type,
                    version=previous.version,
                    chunk_index=previous.chunk_index,
                    text=merged_text,
                    sentence_start=previous.sentence_start,
                    sentence_end=len(sentences),
                    token_count=merged_tokens,
                )
            else:
                chunks.append(
                    SemanticChunk(
                        chunk_id=(
                            f"{record['source_id']}:"
                            f"{record['version']}:"
                            f"semantic:{chunk_index}"
                        ),
                        source_id=record["source_id"],
                        source_type=record["source_type"],
                        version=record["version"],
                        chunk_index=chunk_index,
                        text=final_text,
                        sentence_start=current_start,
                        sentence_end=len(sentences),
                        token_count=final_tokens,
                    )
                )
        else:
            chunks.append(
                SemanticChunk(
                    chunk_id=(
                        f"{record['source_id']}:"
                        f"{record['version']}:"
                        f"semantic:{chunk_index}"
                    ),
                    source_id=record["source_id"],
                    source_type=record["source_type"],
                    version=record["version"],
                    chunk_index=chunk_index,
                    text=final_text,
                    sentence_start=current_start,
                    sentence_end=len(sentences),
                    token_count=final_tokens,
                )
            )
    return chunks

def chunk_records_semantic(
    records: list[dict],
    *,
    embed_sentences: Callable[
        [list[str]],
        np.ndarray,
    ],
    count_tokens: Callable[[str], int],
    similarity_threshold: float = 0.45,
    min_tokens: int = 80,
    max_tokens: int = 512,
) -> list[SemanticChunk]:
    chunks: list[SemanticChunk] = []

    for record in records:
        chunks.extend(
            chunk_semantic(
                record,
                embed_sentences=embed_sentences,
                count_tokens=count_tokens,
                similarity_threshold=similarity_threshold,
                min_tokens=min_tokens,
                max_tokens=max_tokens,
            )
        )

    return chunks