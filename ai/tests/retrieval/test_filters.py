from __future__ import annotations

from dataclasses import dataclass

from ai.retrieval.filters import (
    FilterConfidence,
    MetadataFilter,
    apply_metadata_filters,
)


@dataclass(frozen=True)
class FakeItem:
    source_id: str
    metadata: dict[str, str]


def _items() -> list[FakeItem]:
    return [
        FakeItem(
            source_id="product_strategy",
            metadata={
                "category": "전략",
                "language": "ko",
                "brand": "",
            },
        ),
        FakeItem(
            source_id="product_economy",
            metadata={
                "category": "경제 전략",
                "language": "ko",
                "brand": "",
            },
        ),
        FakeItem(
            source_id="product_english",
            metadata={
                "category": "전략",
                "language": "en",
                "brand": "",
            },
        ),
        FakeItem(
            source_id="policy_unknown",
            metadata={
                "category": "",
                "language": "",
                "brand": "",
            },
        ),
    ]


def test_exact_category_filter_removes_known_mismatch() -> None:
    results = apply_metadata_filters(
        _items(),
        filters=[
            MetadataFilter(
                field="category",
                value="전략",
                confidence=(
                    FilterConfidence.EXACT
                ),
            )
        ],
    )

    ids = {
        item.source_id
        for item in results
    }

    assert "product_strategy" in ids
    assert "product_english" in ids
    assert "policy_unknown" in ids
    assert "product_economy" not in ids


def test_uncertain_filter_does_not_reduce_candidates() -> None:
    original = _items()

    results = apply_metadata_filters(
        original,
        filters=[
            MetadataFilter(
                field="category",
                value="전략",
                confidence=(
                    FilterConfidence.UNCERTAIN
                ),
            )
        ],
    )

    assert results == original


def test_no_match_exact_filter_falls_back() -> None:
    original = _items()

    results = apply_metadata_filters(
        original,
        filters=[
            MetadataFilter(
                field="category",
                value="존재하지않는카테고리",
                confidence=(
                    FilterConfidence.EXACT
                ),
            )
        ],
    )

    assert results == original


def test_exact_language_filter_keeps_unknown_metadata() -> None:
    results = apply_metadata_filters(
        _items(),
        filters=[
            MetadataFilter(
                field="language",
                value="ko",
                confidence=(
                    FilterConfidence.EXACT
                ),
            )
        ],
    )

    ids = {
        item.source_id
        for item in results
    }

    assert "product_strategy" in ids
    assert "product_economy" in ids
    assert "policy_unknown" in ids
    assert "product_english" not in ids


def test_filter_is_case_insensitive() -> None:
    items = [
        FakeItem(
            source_id="english_product",
            metadata={
                "language": "EN",
            },
        ),
    ]

    results = apply_metadata_filters(
        items,
        filters=[
            MetadataFilter(
                field="language",
                value="en",
                confidence=(
                    FilterConfidence.EXACT
                ),
            )
        ],
    )

    assert len(results) == 1


def test_missing_brand_does_not_remove_all_results() -> None:
    original = _items()

    results = apply_metadata_filters(
        original,
        filters=[
            MetadataFilter(
                field="brand",
                value="Games Workshop",
                confidence=(
                    FilterConfidence.EXACT
                ),
            )
        ],
    )

    assert results == original


def test_multiple_exact_filters_are_applied_sequentially() -> None:
    results = apply_metadata_filters(
        _items(),
        filters=[
            MetadataFilter(
                field="category",
                value="전략",
                confidence=(
                    FilterConfidence.EXACT
                ),
            ),
            MetadataFilter(
                field="language",
                value="ko",
                confidence=(
                    FilterConfidence.EXACT
                ),
            ),
        ],
    )

    ids = {
        item.source_id
        for item in results
    }

    assert "product_strategy" in ids
    assert "policy_unknown" in ids
    assert "product_english" not in ids
    assert "product_economy" not in ids