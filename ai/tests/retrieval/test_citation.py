from ai.retrieval.citation import (
    build_citation,
    build_excerpt_hash,
    citation_or_abstain,
)


def make_inventory_evidence() -> dict:
    return {
        "source_id": "inventory_demo_001",
        "title": "Demo Inventory Snapshot",
        "record_id": "inv_demo_001",
        "source_type": "INVENTORY_SNAPSHOT",
        "as_of": "2026-09-04T07:00:00Z",
        "field_or_path": "on_hand",
        "excerpt": "현재 재고는 3개입니다.",
    }


def test_build_citation_has_required_fields() -> None:
    citation = build_citation(
        make_inventory_evidence()
    )

    payload = citation.to_dict()

    assert payload["source_id"] == "inventory_demo_001"
    assert payload["title"] == "Demo Inventory Snapshot"
    assert payload["record_id"] == "inv_demo_001"
    assert payload["as_of"] == "2026-09-04T07:00:00Z"
    assert payload["field_or_path"] == "on_hand"
    assert payload["excerpt_hash"].startswith("sha256:")


def test_excerpt_hash_is_deterministic() -> None:
    first = build_excerpt_hash(
        "현재 재고는   3개입니다."
    )
    second = build_excerpt_hash(
        "현재 재고는 3개입니다."
    )

    assert first == second


def test_live_source_without_as_of_is_rejected() -> None:
    evidence = make_inventory_evidence()
    evidence["as_of"] = None

    decision = citation_or_abstain([evidence])

    assert decision.decision == "ABSTAIN"
    assert decision.reason == "INVALID_EVIDENCE"
    assert decision.citations == ()


def test_missing_evidence_abstains() -> None:
    decision = citation_or_abstain([])

    assert decision.decision == "ABSTAIN"
    assert decision.reason == "INSUFFICIENT_EVIDENCE"
    assert decision.citations == ()


def test_missing_required_field_abstains() -> None:
    evidence = make_inventory_evidence()
    del evidence["record_id"]

    decision = citation_or_abstain([evidence])

    assert decision.decision == "ABSTAIN"
    assert decision.reason == "INVALID_EVIDENCE"


def test_valid_evidence_allows_answer() -> None:
    decision = citation_or_abstain(
        [make_inventory_evidence()]
    )

    assert decision.decision == "ANSWER"
    assert decision.reason is None
    assert len(decision.citations) == 1