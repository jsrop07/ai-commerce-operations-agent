from __future__ import annotations

from dataclasses import dataclass

import pytest

from ai.retrieval.filters import (
    FilterConfidence,
    MetadataFilter,
)

from ai.retrieval.bm25 import (
    BM25Config,
    BM25Document,
    BM25Index,
    build_bm25_documents,
    tokenize,
)


@dataclass(frozen=True)
class FakeChunk:
    chunk_id: str
    source_id: str
    source_type: str
    version: str
    text: str


def _documents() -> list[BM25Document]:
    return [
        BM25Document(
            chunk_id="chunk_product_1",
            source_id="product_demo_001",
            source_type="PRODUCT",
            version="v1",
            text=(
                "별빛 항해자는 우주 탐사와 "
                "자원 관리를 중심으로 진행하는 "
                "전략 보드게임입니다."
            ),
            metadata={
                "title": "별빛 항해자",
                "name": "별빛 항해자",
                "brand": "",
                "sku": "",
                "category": "전략",
                "language": "ko",
            },
        ),
        BM25Document(
            chunk_id="chunk_product_2",
            source_id="product_demo_002",
            source_type="PRODUCT",
            version="v1",
            text=(
                "왕국의 상인들은 상품 가격 변화와 "
                "자원 배분을 이용하는 경제 전략 "
                "게임입니다."
            ),
            metadata={
                "title": "왕국의 상인들",
                "name": "왕국의 상인들",
                "brand": "",
                "sku": "",
                "category": "경제 전략",
                "language": "ko",
            },
        ),
        BM25Document(
            chunk_id="chunk_policy_v1",
            source_id="policy_shipping_demo",
            source_type="POLICY",
            version="v1",
            text=(
                "일반 배송은 영업일 기준으로 "
                "처리합니다."
            ),
            metadata={
                "title": "배송 및 예약상품 정책",
                "name": "",
                "brand": "",
                "sku": "",
                "category": "",
                "language": "",
            },
        ),
        BM25Document(
            chunk_id="chunk_policy_v2",
            source_id="policy_shipping_demo",
            source_type="POLICY",
            version="v2",
            text=(
                "예약상품 배송은 입고 확인 후 "
                "처리합니다."
            ),
            metadata={
                "title": "배송 및 예약상품 정책",
                "name": "",
                "brand": "",
                "sku": "",
                "category": "",
                "language": "",
            },
        ),
    ]


def test_tokenize_is_deterministic_and_lowercases_english() -> None:
    assert tokenize("WarHammer 상품 123") == [
        "warhammer",
        "상품",
        "123",
    ]


def test_exact_product_name_is_ranked_first() -> None:
    index = BM25Index(_documents())

    results = index.search(
        "별빛 항해자",
        top_k=3,
    )

    assert results[0].source_id == "product_demo_001"
    assert results[0].score > 0


def test_name_field_weight_improves_exact_name_score() -> None:
    documents = _documents()

    weighted = BM25Index(documents)

    no_name_weight = BM25Index(
        documents,
        config=BM25Config(
            field_weights={
                "sku": 4.0,
                "name": 0.0,
                "brand": 2.5,
                "title": 0.0,
                "category": 1.5,
                "content": 1.0,
            }
        ),
    )

    weighted_score = weighted.search(
        "별빛 항해자",
        top_k=1,
    )[0].score

    unweighted_score = no_name_weight.search(
        "별빛 항해자",
        top_k=1,
    )[0].score

    assert weighted_score > unweighted_score


def test_policy_title_search_returns_policy_source() -> None:
    index = BM25Index(_documents())

    results = index.search(
        "배송 및 예약상품 정책",
        top_k=4,
    )

    assert results[0].source_id == "policy_shipping_demo"
    assert results[0].source_type == "POLICY"


def test_same_source_id_preserves_different_versions() -> None:
    index = BM25Index(_documents())

    results = index.search(
        "배송",
        top_k=4,
    )

    policy_versions = {
        result.version
        for result in results
        if result.source_id == "policy_shipping_demo"
    }

    assert policy_versions == {"v1", "v2"}


def test_missing_brand_and_sku_do_not_break_index() -> None:
    index = BM25Index(_documents())

    results = index.search(
        "전략",
        top_k=2,
    )

    assert len(results) == 2


def test_top_k_limits_result_count() -> None:
    index = BM25Index(_documents())

    results = index.search(
        "전략",
        top_k=2,
    )

    assert len(results) == 2


def test_empty_query_returns_zero_scores_deterministically() -> None:
    index = BM25Index(_documents())

    first = index.search(
        "",
        top_k=4,
    )

    second = index.search(
        "",
        top_k=4,
    )

    assert [
        (
            result.source_id,
            result.version,
            result.chunk_id,
            result.score,
        )
        for result in first
    ] == [
        (
            result.source_id,
            result.version,
            result.chunk_id,
            result.score,
        )
        for result in second
    ]

    assert all(
        result.score == 0.0
        for result in first
    )


def test_invalid_config_is_rejected() -> None:
    with pytest.raises(ValueError):
        BM25Config(k1=0)

    with pytest.raises(ValueError):
        BM25Config(b=1.5)

    with pytest.raises(ValueError):
        BM25Config(
            field_weights={
                "content": -1.0,
            }
        )


def test_invalid_top_k_is_rejected() -> None:
    index = BM25Index(_documents())

    with pytest.raises(ValueError):
        index.search(
            "별빛",
            top_k=0,
        )


def test_build_documents_uses_source_id_and_version() -> None:
    records = [
        {
            "source_id": "policy_shipping_demo",
            "source_type": "POLICY",
            "version": "v1",
            "title": "배송 정책",
            "fields": {},
        },
        {
            "source_id": "policy_shipping_demo",
            "source_type": "POLICY",
            "version": "v2",
            "title": "배송 정책 개정",
            "fields": {},
        },
    ]

    chunks = [
        FakeChunk(
            chunk_id="chunk_v1",
            source_id="policy_shipping_demo",
            source_type="POLICY",
            version="v1",
            text="기존 배송 정책",
        ),
        FakeChunk(
            chunk_id="chunk_v2",
            source_id="policy_shipping_demo",
            source_type="POLICY",
            version="v2",
            text="개정 배송 정책",
        ),
    ]

    documents = build_bm25_documents(
        chunks=chunks,
        records=records,
    )

    assert documents[0].metadata["title"] == "배송 정책"
    assert documents[1].metadata["title"] == "배송 정책 개정"


def test_build_documents_does_not_invent_brand_or_sku() -> None:
    records = [
        {
            "source_id": "product_demo_001",
            "source_type": "PRODUCT",
            "version": "v1",
            "title": "별빛 항해자",
            "fields": {
                "name": "별빛 항해자",
                "category": "전략",
                "language": "ko",
            },
        },
    ]

    chunks = [
        FakeChunk(
            chunk_id="chunk_product_1",
            source_id="product_demo_001",
            source_type="PRODUCT",
            version="v1",
            text="별빛 항해자 설명",
        ),
    ]

    documents = build_bm25_documents(
        chunks=chunks,
        records=records,
    )

    assert documents[0].metadata["brand"] == ""
    assert documents[0].metadata["sku"] == ""


def test_build_documents_rejects_unknown_chunk_source() -> None:
    records = [
        {
            "source_id": "product_demo_001",
            "source_type": "PRODUCT",
            "version": "v1",
            "title": "별빛 항해자",
            "fields": {},
        },
    ]

    chunks = [
        FakeChunk(
            chunk_id="unknown_chunk",
            source_id="unknown_source",
            source_type="PRODUCT",
            version="v1",
            text="알 수 없는 source",
        ),
    ]

    with pytest.raises(ValueError):
        build_bm25_documents(
            chunks=chunks,
            records=records,
        )

def test_bm25_exact_filter_is_applied_before_ranking() -> None:
    index = BM25Index(_documents())

    results = index.search(
        "전략",
        top_k=4,
        filters=[
            MetadataFilter(
                field="category",
                value="경제 전략",
                confidence=(
                    FilterConfidence.EXACT
                ),
            )
        ],
    )

    source_ids = {
        result.source_id
        for result in results
    }

    assert "product_demo_002" in source_ids
    assert "product_demo_001" not in source_ids


def test_bm25_uncertain_filter_keeps_recall() -> None:
    index = BM25Index(_documents())

    results = index.search(
        "별빛 항해자",
        top_k=4,
        filters=[
            MetadataFilter(
                field="category",
                value="경제 전략",
                confidence=(
                    FilterConfidence.UNCERTAIN
                ),
            )
        ],
    )

    assert (
        results[0].source_id
        == "product_demo_001"
    )


def test_bm25_no_match_filter_falls_back() -> None:
    index = BM25Index(_documents())

    results = index.search(
        "별빛 항해자",
        top_k=4,
        filters=[
            MetadataFilter(
                field="category",
                value="없는 카테고리",
                confidence=(
                    FilterConfidence.EXACT
                ),
            )
        ],
    )

    assert (
        results[0].source_id
        == "product_demo_001"
    )