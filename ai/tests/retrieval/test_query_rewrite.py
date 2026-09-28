import pytest

from ai.retrieval.query_rewrite import (
    entity_preservation_failures,
    entity_preservation_rate,
    rewrite_query,
)


PRODUCTS = [
    "Warhammer 40,000 Ultimate Starter Set",
    "Kill Team Starter Set",
    "아크 노바",
    "7 원더스 듀얼 판테온",
]


def test_non_conversational_query_is_unchanged() -> None:
    query = (
        "Warhammer 40,000 Ultimate Starter Set "
        "한국어판 재고 확인"
    )

    result = rewrite_query(
        query,
        product_name_lexicon=PRODUCTS,
    )

    assert result.rewritten_query == query
    assert result.reason == "NO_REWRITE_NEEDED"
    assert result.changed_fields == ()


def test_referential_product_is_resolved() -> None:
    result = rewrite_query(
        "그거 재고도 있어?",
        previous_query=(
            "Warhammer 40,000 "
            "Ultimate Starter Set 상품 정보 알려줘"
        ),
        product_name_lexicon=PRODUCTS,
    )

    assert (
        "Warhammer 40,000 "
        "Ultimate Starter Set"
        in result.rewritten_query
    )

    assert "그거" not in (
        result.rewritten_query
    )

    assert result.reason == (
        "REFERENTIAL_PRODUCT_RESOLVED"
    )


def test_previous_language_is_preserved() -> None:
    result = rewrite_query(
        "그거 재고도 있어?",
        previous_query=(
            "Kill Team Starter Set "
            "한국어판 상품 정보 알려줘"
        ),
        product_name_lexicon=PRODUCTS,
    )

    assert "Kill Team Starter Set" in (
        result.rewritten_query
    )

    assert "한국어판" in (
        result.rewritten_query
    )


def test_previous_edition_is_preserved() -> None:
    result = rewrite_query(
        "그 상품 재고 있어?",
        previous_query=(
            "Warhammer 40,000 "
            "Ultimate Starter Set "
            "10th Edition 상품 정보"
        ),
        product_name_lexicon=PRODUCTS,
    )

    assert "10th Edition" in (
        result.rewritten_query
    )


def test_expansion_expression_is_preserved() -> None:
    result = rewrite_query(
        "그거 살 수 있어?",
        previous_query=(
            "Kill Team Starter Set "
            "expansion pack 정보"
        ),
        product_name_lexicon=PRODUCTS,
    )

    assert "expansion pack" in (
        result.rewritten_query
    )


def test_current_quantity_is_not_removed() -> None:
    result = rewrite_query(
        "그거 2개 필요해",
        previous_query=(
            "아크 노바 상품 정보 알려줘"
        ),
        product_name_lexicon=PRODUCTS,
    )

    assert "2개" in (
        result.rewritten_query
    )

    quantity_entities = [
        entity.value
        for entity
        in result.preserved_entities
        if entity.entity_type
        == "quantity"
    ]

    assert "2개" in quantity_entities


def test_current_negation_is_not_removed() -> None:
    result = rewrite_query(
        "그거 영문판 말고 한국어판 있어?",
        previous_query=(
            "아크 노바 상품 정보 알려줘"
        ),
        product_name_lexicon=PRODUCTS,
    )

    assert "말고" in (
        result.rewritten_query
    )

    assert "한국어판" in (
        result.rewritten_query
    )

def test_current_time_condition_is_not_removed() -> None:
    result = rewrite_query(
        "그거 이번 주 안에 받을 수 있어?",
        previous_query=(
            "아크 노바 상품 정보 알려줘"
        ),
        product_name_lexicon=PRODUCTS,
    )

    assert "이번 주 안에" in (
        result.rewritten_query
    )

    time_entities = [
        entity.value
        for entity
        in result.preserved_entities
        if entity.entity_type
        == "time_condition"
    ]

    assert time_entities == [
        "이번 주 안에"
    ]


def test_product_name_is_not_alias_expanded() -> None:
    query = "아크 노바 한국어판 찾아줘"

    result = rewrite_query(
        query,
        product_name_lexicon=PRODUCTS,
    )

    assert "아크 노바" in (
        result.rewritten_query
    )

    assert "아크노바" not in (
        result.rewritten_query
    )


def test_edition_product_name_is_not_shortened() -> None:
    query = (
        "7 원더스 듀얼 판테온 "
        "한국어판 찾아줘"
    )

    result = rewrite_query(
        query,
        product_name_lexicon=PRODUCTS,
    )

    assert (
        "7 원더스 듀얼 판테온"
        in result.rewritten_query
    )


def test_missing_previous_context_fails_closed() -> None:
    result = rewrite_query(
        "그거 재고 있어?",
        product_name_lexicon=PRODUCTS,
    )

    assert (
        result.rewritten_query
        == "그거 재고 있어?"
    )

    assert (
        "REFERENTIAL_CONTEXT_MISSING"
        in result.warnings
    )

    assert result.reason == (
        "REFERENTIAL_QUERY_LEFT_UNCHANGED"
    )


def test_changed_fields_are_structured() -> None:
    result = rewrite_query(
        "그 상품 재고 있어?",
        previous_query=(
            "아크 노바 상품 알려줘"
        ),
        product_name_lexicon=PRODUCTS,
    )

    payload = result.to_dict()

    assert payload["changed_fields"]

    first = payload[
        "changed_fields"
    ][0]

    assert first["field"] == (
        "referential_expression"
    )

    assert first["before"] == "그 상품"
    assert first["after"] == "아크 노바"


@pytest.mark.parametrize(
    (
        "current_query",
        "previous_query",
    ),
    [
        (
            "그거 2개 필요해",
            "아크 노바 한국어판 상품 정보 알려줘",
        ),
        (
            "그거 이번 주 안에 받을 수 있어?",
            "Kill Team Starter Set "
            "3rd Edition 상품 정보",
        ),
        (
            "그 상품 영문판 말고 한국어판 있어?",
            "Warhammer 40,000 "
            "Ultimate Starter Set 상품 정보",
        ),
        (
            "그거 재고도 있어?",
            "7 원더스 듀얼 판테온 "
            "한국어판 상품 정보",
        ),
    ],
)
def test_entity_preservation_rate_is_100_percent(
    current_query: str,
    previous_query: str,
) -> None:
    result = rewrite_query(
        current_query,
        previous_query=previous_query,
        product_name_lexicon=PRODUCTS,
    )

    assert (
        entity_preservation_failures(
            result
        )
        == ()
    )

    assert (
        entity_preservation_rate(
            result
        )
        == pytest.approx(1.0)
    )


def test_empty_query_uses_day09_validation() -> None:
    with pytest.raises(
        ValueError
    ):
        rewrite_query(
            "   ",
            product_name_lexicon=PRODUCTS,
        )

def test_language_longest_surface_is_preserved_once() -> None:
    result = rewrite_query(
        "그거 재고 있어?",
        previous_query=(
            "Kill Team Starter Set "
            "한국어판 상품 정보 알려줘"
        ),
        product_name_lexicon=PRODUCTS,
    )

    language_entities = [
        entity.value
        for entity
        in result.preserved_entities
        if entity.entity_type
        == "language"
    ]

    assert language_entities == [
        "한국어판"
    ]

    assert (
        result.rewritten_query.count(
            "한국어판"
        )
        == 1
    )

    assert (
        "한국어판 한국어"
        not in result.rewritten_query
    )

def test_rewrite_keeps_exact_complex_constraints() -> None:
    result = rewrite_query(
        "그거 2개 이번 주 안에 필요해",
        previous_query=(
            "Kill Team Starter Set "
            "3rd Edition 한국어판 "
            "상품 정보 알려줘"
        ),
        product_name_lexicon=[
            "Kill Team Starter Set"
        ],
    )

    assert "Kill Team Starter Set" in (
        result.rewritten_query
    )
    assert "3rd Edition" in (
        result.rewritten_query
    )
    assert "한국어판" in (
        result.rewritten_query
    )
    assert "2개" in (
        result.rewritten_query
    )
    assert "이번 주 안에" in (
        result.rewritten_query
    )

    assert "한국어판 한국어" not in (
        result.rewritten_query
    )

    preserved = {
        (
            entity.entity_type,
            entity.value,
        )
        for entity
        in result.preserved_entities
    }

    assert (
        "time_condition",
        "이번 주 안에",
    ) in preserved

    assert (
        "language",
        "한국어판",
    ) in preserved

    assert (
        "language",
        "한국어",
    ) not in preserved

    assert (
        entity_preservation_rate(
            result
        )
        == pytest.approx(1.0)
    )