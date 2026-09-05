import pytest

from ai.retrieval.deduplicate import (
    build_source_hash,
    build_text_hash,
    deduplicate_records,
    near_duplicate_score,
    normalize_text,
)


def make_record(
    source_id: str,
    version: str,
    content: str,
) -> dict:
    return {
        "source_id": source_id,
        "source_type": "POLICY",
        "version": version,
        "pii_status": "CLEAN",
        "title": source_id,
        "content": content,
    }


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text(
        "예약   상품은\n배송됩니다."
    ) == "예약 상품은 배송됩니다."


def test_normalized_text_hash_matches_equivalent_text() -> None:
    left = build_text_hash(
        "예약   상품은 배송됩니다."
    )
    right = build_text_hash(
        "예약 상품은 배송됩니다."
    )

    assert left == right


def test_source_hash_preserves_version() -> None:
    v1 = build_source_hash(
        "policy_shipping",
        "v1",
    )
    v2 = build_source_hash(
        "policy_shipping",
        "v2",
    )

    assert v1 != v2


def test_exact_normalized_duplicate_is_removed() -> None:
    records = [
        make_record(
            "policy_a",
            "v1",
            "예약 상품은 배송됩니다.",
        ),
        make_record(
            "policy_b",
            "v1",
            "예약   상품은 배송됩니다.",
        ),
    ]

    result = deduplicate_records(records)

    assert len(result.kept) == 1
    assert len(result.removed) == 1
    assert (
        result.duplicate_pairs[0]["reason"]
        == "NORMALIZED_TEXT_HASH"
    )


def test_near_duplicate_is_removed() -> None:
    left = (
        "예약 상품은 입고 완료 후 "
        "순차적으로 배송됩니다."
    )
    right = (
        "예약 상품은 입고 완료 후 "
        "순차적으로 배송됩니다"
    )

    assert near_duplicate_score(
        left,
        right,
    ) >= 0.92

    result = deduplicate_records(
        [
            make_record(
                "policy_a",
                "v1",
                left,
            ),
            make_record(
                "policy_b",
                "v1",
                right,
            ),
        ],
        near_duplicate_threshold=0.92,
    )

    assert len(result.removed) == 1


def test_different_versions_are_preserved() -> None:
    records = [
        make_record(
            "policy_shipping",
            "v1",
            "예약 상품은 입고 후 배송됩니다.",
        ),
        make_record(
            "policy_shipping",
            "v2",
            "예약 상품은 입고 후 배송됩니다.",
        ),
    ]

    result = deduplicate_records(records)

    assert len(result.kept) == 2
    assert len(result.removed) == 0


def test_invalid_near_duplicate_threshold() -> None:
    with pytest.raises(ValueError):
        deduplicate_records(
            [],
            near_duplicate_threshold=1.5,
        )