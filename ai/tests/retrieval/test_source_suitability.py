from ai.retrieval.source_suitability import (
    SourceEvidence,
    SuitabilityStatus,
    evaluate_source_suitability,
)


def test_answer_when_required_evidence_is_suitable() -> None:
    result = evaluate_source_suitability(
        required_source_types=("POLICY",),
        evidence=(
            SourceEvidence(
                source_type="POLICY",
                source_id="policy_shipping_demo",
                freshness="FRESH",
                supports_claim=True,
            ),
        ),
    )

    assert result.status == SuitabilityStatus.ANSWER
    assert result.provider_call_allowed is True
    assert result.reasons == ()


def test_no_source_holds_before_provider_call() -> None:
    result = evaluate_source_suitability(
        required_source_types=("PRODUCT",),
        evidence=(),
    )

    assert result.status == SuitabilityStatus.HOLD
    assert result.provider_call_allowed is False
    assert "NO_SOURCE" in result.reasons
    assert "REQUIRED_SOURCE_MISSING:PRODUCT" in result.reasons


def test_stale_evidence_holds_before_provider_call() -> None:
    result = evaluate_source_suitability(
        required_source_types=("INVENTORY_SNAPSHOT",),
        evidence=(
            SourceEvidence(
                source_type="INVENTORY_SNAPSHOT",
                source_id="inventory_snapshot_demo_sku_001",
                freshness="STALE",
                supports_claim=True,
            ),
        ),
    )

    assert result.status == SuitabilityStatus.HOLD
    assert result.provider_call_allowed is False
    assert "STALE_EVIDENCE:inventory_snapshot_demo_sku_001" in result.reasons


def test_high_retrieval_score_is_not_an_input() -> None:
    result = evaluate_source_suitability(
        required_source_types=("POLICY", "INCOMING_STOCK"),
        evidence=(
            SourceEvidence(
                source_type="POLICY",
                source_id="policy_reservation_shortage_demo",
                freshness="FRESH",
                supports_claim=True,
            ),
        ),
    )

    assert result.status == SuitabilityStatus.HOLD
    assert result.provider_call_allowed is False
    assert "REQUIRED_SOURCE_MISSING:INCOMING_STOCK" in result.reasons


def test_unverified_target_holds() -> None:
    result = evaluate_source_suitability(
        required_source_types=("INVENTORY_SNAPSHOT",),
        evidence=(
            SourceEvidence(
                source_type="INVENTORY_SNAPSHOT",
                source_id="inventory_snapshot_demo_sku_001",
                freshness="FRESH",
                supports_claim=True,
            ),
        ),
        target_verified=False,
    )

    assert result.status == SuitabilityStatus.HOLD
    assert result.provider_call_allowed is False
    assert "TARGET_UNVERIFIED" in result.reasons
