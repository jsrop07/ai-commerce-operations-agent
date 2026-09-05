from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class FixedChunk:
    chunk_id: str
    source_id: str
    source_type: str
    version: str
    chunk_index: int
    text: str
    token_count: int
    start_token: int
    end_token: int


FIXED_CONFIGS = [
    (256, 0),
    (256, 64),
    (256, 128),
    (512, 0),
    (512, 64),
    (512, 128),
    (800, 0),
    (800, 64),
    (800, 128),
]


def chunk_fixed(
    record: dict,
    *,
    chunk_size: int,
    overlap: int,
    encode: Callable[[str], list[int]],
    decode: Callable[[list[int]], str],
) -> list[FixedChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if overlap < 0:
        raise ValueError("overlap must be greater than or equal to 0")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    tokens = encode(record["content"])

    if not tokens:
        return []

    step = chunk_size - overlap
    chunks: list[FixedChunk] = []

    start = 0
    chunk_index = 0

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]

        chunk_id = (
            f"{record['source_id']}:"
            f"{record['version']}:"
            f"fixed:"
            f"{chunk_size}:"
            f"{overlap}:"
            f"{chunk_index}"
        )

        chunks.append(
            FixedChunk(
                chunk_id=chunk_id,
                source_id=record["source_id"],
                source_type=record["source_type"],
                version=record["version"],
                chunk_index=chunk_index,
                text=decode(chunk_tokens),
                token_count=len(chunk_tokens),
                start_token=start,
                end_token=end,
            )
        )

        if end >= len(tokens):
            break

        start += step
        chunk_index += 1

    return chunks


def chunk_records_fixed(
    records: list[dict],
    *,
    chunk_size: int,
    overlap: int,
    encode: Callable[[str], list[int]],
    decode: Callable[[list[int]], str],
) -> list[FixedChunk]:
    chunks: list[FixedChunk] = []

    for record in records:
        chunks.extend(
            chunk_fixed(
                record,
                chunk_size=chunk_size,
                overlap=overlap,
                encode=encode,
                decode=decode,
            )
        )

    return chunks