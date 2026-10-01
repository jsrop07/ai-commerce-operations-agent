from ai.retrieval.claim_support import (
    ClaimEvidence,
    ClaimType,
    classify_claim_type,
    evaluate_claim_support,
)


def policy(
    source_id: str,
    excerpt: str,
) -> ClaimEvidence:
    return ClaimEvidence(
        source_type="POLICY",
        source_id=source_id,
        version="v1",
        excerpt=excerpt,
    )


def incoming(
    source_id: str,
    excerpt: str,
) -> ClaimEvidence:
    return ClaimEvidence(
        source_type="INCOMING_STOCK",
        source_id=source_id,
        version="v1",
        excerpt=excerpt,
    )


def test_classifies_shipping_policy():
    result = classify_claim_type(
        "예약상품은 언제 출고해?"
    )

    assert (
        result
        == ClaimType.RESERVATION_SHIPPING_POLICY
    )


def test_classifies_tentative_shortage():
    result = classify_claim_type(
        "잠정입고가 3개 있는데 "
        "왜 예약 부족수량에서 안 빼?"
    )

    assert (
        result
        == ClaimType.TENTATIVE_SHORTAGE_POLICY
    )


def test_classifies_shipping_readiness():
    result = classify_claim_type(
        "잠정입고 상태인 물량을 근거로 "
        "예약상품 출고 준비가 끝났다고 봐도 돼?"
    )

    assert (
        result
        == ClaimType.TENTATIVE_SHIPPING_READINESS
    )


def test_unknown_question_is_unsupported():
    decision = evaluate_claim_support(
        "이 상품 재밌어?",
        (),
    )

    assert decision.supported is False

    assert (
        decision.claim_type
        == ClaimType.UNSUPPORTED
    )


def test_shipping_policy_supported():
    decision = evaluate_claim_support(
        "예약상품은 언제 출고해?",
        (
            policy(
                "policy_shipping_demo",
                "예약상품은 상품 입고와 "
                "검수 완료 후 순차적으로 "
                "출고합니다.",
            ),
        ),
    )

    assert decision.supported is True

    assert (
        decision.supported_source_ids
        == ("policy_shipping_demo",)
    )


def test_shipping_policy_not_supported_by_irrelevant_policy():
    decision = evaluate_claim_support(
        "예약상품은 언제 출고해?",
        (
            policy(
                "irrelevant_policy",
                "교환 신청은 수령 후 "
                "일정 기간 내 가능합니다.",
            ),
        ),
    )

    assert decision.supported is False


def test_tentative_shortage_supported():
    decision = evaluate_claim_support(
        "잠정입고가 3개 있는데 "
        "왜 예약 부족수량에서 안 빼?",
        (
            policy(
                "policy_reservation_shortage_demo",
                "잠정입고 수량은 아직 "
                "확정되지 않았으므로 "
                "예약 부족수량 차감에 "
                "사용하지 않습니다.",
            ),
        ),
    )

    assert decision.supported is True


def test_shipping_readiness_requires_both_sources():
    decision = evaluate_claim_support(
        "잠정입고 상태인 물량을 근거로 "
        "예약상품 출고 준비가 끝났다고 봐도 돼?",
        (
            incoming(
                "incoming_stock_demo_tentative_001",
                "상태는 TENTATIVE이며 "
                "아직 확정입고가 아닙니다.",
            ),
        ),
    )

    assert decision.supported is False

    assert (
        "RESERVATION_SHIPPING_POLICY"
        in decision.missing_requirements
    )


def test_shipping_readiness_supported_with_both_sources():
    decision = evaluate_claim_support(
        "잠정입고 상태인 물량을 근거로 "
        "예약상품 출고 준비가 끝났다고 봐도 돼?",
        (
            incoming(
                "incoming_stock_demo_tentative_001",
                "상태는 TENTATIVE이며 "
                "아직 확정입고가 아닙니다.",
            ),
            policy(
                "policy_shipping_demo",
                "예약상품은 상품 입고와 "
                "검수 완료 후 순차적으로 "
                "출고합니다.",
            ),
        ),
    )

    assert decision.supported is True

    assert set(
        decision.supported_source_ids
    ) == {
        "incoming_stock_demo_tentative_001",
        "policy_shipping_demo",
    }


def test_search_result_presence_alone_is_not_support():
    decision = evaluate_claim_support(
        "예약상품은 언제 출고해?",
        (
            ClaimEvidence(
                source_type="POLICY",
                source_id="high_score_result",
                version="v1",
                excerpt="검색 결과는 존재하지만 "
                "예약상품 출고 조건은 없습니다.",
            ),
        ),
    )

    assert decision.supported is False