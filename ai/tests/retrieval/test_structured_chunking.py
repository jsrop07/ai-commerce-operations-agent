from ai.retrieval.chunking.structured import (
    chunk_structured,
)


def test_product_stays_as_one_record_chunk() -> None:
    record = {
        "source_id": "product_1",
        "source_type": "PRODUCT",
        "version": "v1",
        "fields": {
            "name": "테스트 게임",
            "category": "전략",
            "language": "ko",
            "description": "상품 설명",
            "components": "보드, 카드",
            "compatibility": "기본판",
        },
    }

    chunks = chunk_structured(record)

    assert len(chunks) == 1
    assert (
        chunks[0].structure_type
        == "PRODUCT_RECORD"
    )
    assert "name: 테스트 게임" in chunks[0].text
    assert "components: 보드, 카드" in chunks[0].text


def test_policy_preserves_heading_boundary() -> None:
    record = {
        "source_id": "policy_1",
        "source_type": "POLICY",
        "version": "v1",
        "paragraphs": [
            {
                "heading": "배송",
                "text": "배송 안내입니다.",
            },
            {
                "heading": "반품",
                "text": "반품 안내입니다.",
            },
        ],
    }

    chunks = chunk_structured(record)

    assert len(chunks) == 2
    assert chunks[0].text == (
        "배송\n배송 안내입니다."
    )
    assert chunks[1].text == (
        "반품\n반품 안내입니다."
    )


def test_faq_preserves_question_answer_pair() -> None:
    record = {
        "source_id": "faq_1",
        "source_type": "POLICY",
        "version": "v1",
        "faq": [
            {
                "question": "언제 배송되나요?",
                "answer": "입고 후 배송됩니다.",
            }
        ],
    }

    chunks = chunk_structured(record)

    assert len(chunks) == 1
    assert chunks[0].structure_type == "FAQ_PAIR"
    assert "언제 배송되나요?" in chunks[0].text
    assert "입고 후 배송됩니다." in chunks[0].text


def test_version_is_preserved() -> None:
    record = {
        "source_id": "policy_1",
        "source_type": "POLICY",
        "version": "v2",
        "paragraphs": [
            {
                "heading": "배송",
                "text": "새 정책",
            }
        ],
    }

    chunk = chunk_structured(
        record
    )[0]

    assert chunk.version == "v2"
    assert ":v2:" in chunk.chunk_id