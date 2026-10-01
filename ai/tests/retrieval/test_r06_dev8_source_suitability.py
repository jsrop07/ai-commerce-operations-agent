import pytest

from ai.retrieval.source_suitability import (
    SourceEvidence,
    SuitabilityStatus,
    evaluate_source_suitability,
)


DEV8 = [
    (
        "GE-D-005",
        ("POLICY",),
        (SourceEvidence("POLICY", "policy_shipping_demo", "FRESH", True),),
        SuitabilityStatus.ANSWER,
    ),
    (
        "GE-D-007",
        ("POLICY",),
        (SourceEvidence("POLICY", "policy_reservation_shortage_demo", "FRESH", True),),
        SuitabilityStatus.ANSWER,
    ),
    (
        "GE-D-009",
        ("POLICY", "INCOMING_STOCK"),
        (
            SourceEvidence("POLICY", "policy_reservation_shortage_demo", "FRESH", True),
            SourceEvidence("INCOMING_STOCK", "incoming_stock_demo_confirmed_001", "FRESH", True),
        ),
        SuitabilityStatus.ANSWER,
    ),
    (
        "GE-D-011",
        ("INVENTORY_SNAPSHOT", "POLICY"),
        (
            SourceEvidence("INVENTORY_SNAPSHOT", "inventory_snapshot_demo_sku_001", "FRESH", True),
            SourceEvidence("POLICY", "policy_reservation_shortage_demo", "FRESH", True),
        ),
        SuitabilityStatus.ANSWER,
    ),
    (
        "GE-D-013",
        ("INCOMING_STOCK", "POLICY"),
        (
            SourceEvidence("INCOMING_STOCK", "incoming_stock_demo_confirmed_001", "FRESH", True),
            SourceEvidence("POLICY", "policy_shipping_demo", "FRESH", True),
        ),
        SuitabilityStatus.ANSWER,
    ),
    (
        "GE-D-016",
        ("INCOMING_STOCK", "POLICY"),
        (
            SourceEvidence("INCOMING_STOCK", "incoming_stock_demo_tentative_001", "FRESH", True),
            SourceEvidence("POLICY", "policy_shipping_demo", "FRESH", True),
        ),
        SuitabilityStatus.ANSWER,
    ),
    (
        "GE-D-021",
        ("PRODUCT",),
        (),
        SuitabilityStatus.HOLD,
    ),
    (
        "GE-D-023",
        ("INVENTORY_SNAPSHOT",),
        (SourceEvidence("INVENTORY_SNAPSHOT", "inventory_snapshot_demo_sku_001", "STALE", True),),
        SuitabilityStatus.HOLD,
    ),
]


@pytest.mark.parametrize(
    "case_id,required,evidence,expected",
    DEV8,
)
def test_r06_dev8_precheck(
    case_id: str,
    required: tuple[str, ...],
    evidence: tuple[SourceEvidence, ...],
    expected: SuitabilityStatus,
) -> None:
    result = evaluate_source_suitability(
        required_source_types=required,
        evidence=evidence,
    )

    assert result.status == expected, case_id
    assert result.provider_call_allowed is (
        expected == SuitabilityStatus.ANSWER
    )


def test_r06_dev8_planned_call_counts() -> None:
    answerable = sum(
        1 for *_, expected in DEV8
        if expected == SuitabilityStatus.ANSWER
    )
    preblocked = len(DEV8) - answerable

    prompt_conditions = 2

    assert len(DEV8) == 8
    assert answerable == 6
    assert preblocked == 2
    assert len(DEV8) * prompt_conditions == 16
    assert preblocked * prompt_conditions == 4
    assert answerable * prompt_conditions == 12
