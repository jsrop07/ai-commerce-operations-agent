from ai.retrieval.context_compression import (
    compress_context,
)


def _product_evidence() -> dict:
    return {
        "source_id": "product-101",
        "title": (
            "CHAOS SPACE MARINES: TERMINATORS"
        ),
        "record_id": "product-101",
        "source_type": "PRODUCT",
        "as_of": (
            "2026-09-08T04:00:00Z"
        ),
        "field_or_path": (
            "product_name"
        ),
        "excerpt": (
            "CHAOS SPACE MARINES: "
            "TERMINATORS"
        ),
        "evidence_ids": [
            "cafe24-sanitized:product:101"
        ],
        "product_name": (
            "CHAOS SPACE MARINES: "
            "TERMINATORS"
        ),
        "product_code": "P0000101",
        "rank": 1,
        "score": 0.91,
        "bm25_rank": 2,
        "vector_rank": 1,
        "rerank_score": 0.99,
        "fusion_method": "RRF",
        "debug": {
            "internal": True,
        },
    }


def test_search_metadata_is_removed() -> None:
    result = compress_context(
        [
            _product_evidence()
        ]
    )

    payload = (
        result.items[0]
        .compressed
    )

    assert "rank" not in payload
    assert "score" not in payload

    assert (
        "rerank_score"
        not in payload
    )

    assert (
        "fusion_method"
        not in payload
    )

    assert "debug" not in payload


def test_citation_fields_are_preserved() -> None:
    original = (
        _product_evidence()
    )

    result = compress_context(
        [original]
    )

    payload = (
        result.items[0]
        .compressed
    )

    for field in (
        "source_id",
        "title",
        "record_id",
        "source_type",
        "as_of",
        "field_or_path",
        "excerpt",
    ):
        assert (
            payload[field]
            == original[field]
        )


def test_evidence_ids_are_preserved() -> None:
    result = compress_context(
        [
            _product_evidence()
        ]
    )

    payload = (
        result.items[0]
        .compressed
    )

    assert payload[
        "evidence_ids"
    ] == [
        "cafe24-sanitized:product:101"
    ]


def test_duplicate_context_is_removed() -> None:
    evidence = (
        _product_evidence()
    )

    result = compress_context(
        [
            evidence,
            dict(evidence),
        ]
    )

    assert (
        result.trace.input_count
        == 2
    )

    assert (
        result.trace.output_count
        == 1
    )

    assert (
        result.trace.duplicate_count
        == 1
    )


def test_compression_reduces_context_size() -> None:
    result = compress_context(
        [
            _product_evidence()
        ]
    )

    assert (
        result.trace.after_char_count
        < result.trace.before_char_count
    )

    assert (
        result.trace.reduction_ratio
        > 0
    )


def test_citation_answerability_is_preserved() -> None:
    result = compress_context(
        [
            _product_evidence()
        ]
    )

    assert (
        result.trace
        .citation_answerable_before
        == 1
    )

    assert (
        result.trace
        .citation_answerable_after
        == 1
    )

    assert (
        result.trace
        .evidence_loss_count
        == 0
    )


def test_live_inventory_keeps_as_of() -> None:
    evidence = {
        "source_id":
            "inventory-1",
        "title":
            "Inventory Snapshot",
        "record_id":
            "inventory-1",
        "source_type":
            "INVENTORY_SNAPSHOT",
        "as_of":
            "2026-09-11T03:00:00Z",
        "field_or_path":
            "on_hand",
        "excerpt":
            "on_hand=3",
        "rank":
            1,
        "score":
            0.8,
    }

    result = compress_context(
        [evidence]
    )

    payload = (
        result.items[0]
        .compressed
    )

    assert payload[
        "as_of"
    ] == (
        "2026-09-11T03:00:00Z"
    )

    assert (
        result.items[0]
        .fallback
        is False
    )


def test_invalid_live_evidence_falls_back() -> None:
    evidence = {
        "source_id":
            "inventory-1",
        "title":
            "Inventory Snapshot",
        "record_id":
            "inventory-1",
        "source_type":
            "INVENTORY_SNAPSHOT",
        "as_of":
            None,
        "field_or_path":
            "on_hand",
        "excerpt":
            "on_hand=3",
        "rank":
            1,
    }

    result = compress_context(
        [evidence]
    )

    assert (
        result.items[0]
        .fallback
        is True
    )

    assert (
        result.trace
        .fallback_count
        == 1
    )


def test_policy_exception_is_preserved() -> None:
    evidence = {
        "source_id":
            "policy-1",
        "title":
            "Return Policy",
        "record_id":
            "policy-1",
        "source_type":
            "POLICY",
        "as_of":
            "2026-09-01T00:00:00Z",
        "field_or_path":
            "returns.exception",
        "excerpt":
            "Opened products are excluded.",
        "policy_exception":
            "OPENED_PRODUCT_EXCLUDED",
        "rank":
            3,
        "score":
            0.3,
    }

    result = compress_context(
        [evidence]
    )

    assert (
        result.items[0]
        .compressed[
            "policy_exception"
        ]
        == "OPENED_PRODUCT_EXCLUDED"
    )


def test_product_business_fields_are_preserved() -> None:
    result = compress_context(
        [
            _product_evidence()
        ]
    )

    payload = (
        result.items[0]
        .compressed
    )

    assert payload[
        "product_name"
    ] == (
        "CHAOS SPACE MARINES: "
        "TERMINATORS"
    )

    assert (
        payload[
            "product_code"
        ]
        == "P0000101"
    )