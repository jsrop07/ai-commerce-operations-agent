import pytest

from ai.retrieval.chunking.fixed import chunk_fixed


def encode_chars(text: str) -> list[int]:
    return [ord(char) for char in text]


def decode_chars(tokens: list[int]) -> str:
    return "".join(chr(token) for token in tokens)


def make_record(
    content: str,
    *,
    version: str = "v1",
) -> dict:
    return {
        "source_id": "test_source",
        "source_type": "POLICY",
        "version": version,
        "content": content,
    }


def test_short_document_creates_one_chunk() -> None:
    record = make_record("abcdefghij")

    chunks = chunk_fixed(
        record,
        chunk_size=20,
        overlap=0,
        encode=encode_chars,
        decode=decode_chars,
    )

    assert len(chunks) == 1
    assert chunks[0].text == "abcdefghij"
    assert chunks[0].token_count == 10


def test_long_document_creates_multiple_chunks() -> None:
    record = make_record("abcdefghijklmnopqrst")

    chunks = chunk_fixed(
        record,
        chunk_size=8,
        overlap=0,
        encode=encode_chars,
        decode=decode_chars,
    )

    assert len(chunks) == 3
    assert chunks[0].start_token == 0
    assert chunks[1].start_token == 8
    assert chunks[2].start_token == 16


def test_overlap_changes_next_start_position() -> None:
    record = make_record("abcdefghijklmnopqrst")

    chunks = chunk_fixed(
        record,
        chunk_size=8,
        overlap=2,
        encode=encode_chars,
        decode=decode_chars,
    )

    assert chunks[0].start_token == 0
    assert chunks[1].start_token == 6


def test_overlap_equal_to_chunk_size_is_invalid() -> None:
    record = make_record("abcdefghij")

    with pytest.raises(ValueError):
        chunk_fixed(
            record,
            chunk_size=8,
            overlap=8,
            encode=encode_chars,
            decode=decode_chars,
        )


def test_version_is_preserved_in_chunk_id() -> None:
    record_v1 = make_record(
        "abcdefghij",
        version="v1",
    )
    record_v2 = make_record(
        "abcdefghij",
        version="v2",
    )

    chunk_v1 = chunk_fixed(
        record_v1,
        chunk_size=20,
        overlap=0,
        encode=encode_chars,
        decode=decode_chars,
    )[0]

    chunk_v2 = chunk_fixed(
        record_v2,
        chunk_size=20,
        overlap=0,
        encode=encode_chars,
        decode=decode_chars,
    )[0]

    assert ":v1:" in chunk_v1.chunk_id
    assert ":v2:" in chunk_v2.chunk_id
    assert chunk_v1.chunk_id != chunk_v2.chunk_id