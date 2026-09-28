import pytest

from ai.retrieval.query_preprocess import (
    normalize_query,
    preprocess_query,
)


def test_normalize_only_collapses_whitespace() -> None:
    result = normalize_query(
        "Warhammer   40,000   Starter"
    )

    assert result == (
        "Warhammer 40,000 Starter"
    )


def test_parenthesized_edition_is_preserved() -> None:
    query = (
        "Warhammer 40,000 "
        "(10th Edition) Starter 재고"
    )

    result = preprocess_query(
        query
    )

    assert (
        "(10th Edition)"
        in result.normalized_query
    )

    assert (
        "(10th Edition)"
        in result.edition_expressions
    )


def test_numeric_product_token_is_not_changed() -> None:
    query = (
        "Warhammer 40,000 "
        "(10th Edition) Starter"
    )

    result = preprocess_query(
        query
    )

    assert "40,000" in (
        result.normalized_query
    )

    assert "10th Edition" in (
        result.normalized_query
    )


def test_language_expression_is_preserved() -> None:
    result = preprocess_query(
        "워해머 스타터 영문판 재고"
    )

    assert "영문판" in (
        result.normalized_query
    )

    assert "영문판" in (
        result.language_expressions
    )


def test_expansion_expression_is_preserved() -> None:
    result = preprocess_query(
        "Necromunda 확장판 재고"
    )

    assert "확장판" in (
        result.normalized_query
    )

    assert "확장판" in (
        result.expansion_expressions
    )


def test_known_product_name_is_extracted_without_mutation() -> None:
    product = (
        "Warhammer 40,000 "
        "Ultimate Starter Set"
    )

    result = preprocess_query(
        (
            "Warhammer 40,000 "
            "Ultimate Starter Set 재고"
        ),
        product_name_lexicon=[
            product
        ],
    )

    assert (
        result.product_name_candidates
        == (product,)
    )


def test_known_brand_preserves_query_surface() -> None:
    result = preprocess_query(
        "Games Workshop 스타터 재고",
        brand_lexicon=[
            "Games Workshop"
        ],
    )

    assert (
        result.brand_candidates
        == ("Games Workshop",)
    )


def test_unknown_brand_is_not_invented() -> None:
    result = preprocess_query(
        "워해머 스타터 재고"
    )

    assert (
        result.brand_candidates
        == ()
    )

    assert (
        "BRAND_LEXICON_NOT_PROVIDED"
        in result.warnings
    )


def test_quoted_product_candidate_is_preserved() -> None:
    result = preprocess_query(
        '"Kill Team Starter Set" 재고 있나요?'
    )

    assert (
        result.product_name_candidates
        == ("Kill Team Starter Set",)
    )


def test_fallback_candidate_keeps_product_expression() -> None:
    result = preprocess_query(
        (
            "Warhammer 40,000 "
            "(10th Edition) Starter 재고"
        )
    )

    assert (
        result.product_name_candidates
        == (
            "Warhammer 40,000 "
            "(10th Edition) Starter",
        )
    )


def test_english_edition_expression() -> None:
    result = preprocess_query(
        "Kill Team 3rd Edition 재고"
    )

    assert "3rd Edition" in (
        result.edition_expressions
    )


def test_empty_query_is_rejected() -> None:
    with pytest.raises(
        ValueError
    ):
        preprocess_query(
            "   "
        )


def test_non_string_query_is_rejected() -> None:
    with pytest.raises(
        TypeError
    ):
        normalize_query(
            None  # type: ignore[arg-type]
        )