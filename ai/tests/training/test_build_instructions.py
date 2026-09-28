import json
from pathlib import Path

from ai.training.datasets.build_instructions import (
    EXPECTED_CANONICAL,
    EXPECTED_COLLECTED,
    EXPECTED_CONFLICTS,
    EXPECTED_CUSTOMER_INQUIRIES,
    EXPECTED_DEDUPE_EXCLUDED,
    EXPECTED_QUERY_EVAL_SEED,
    EXPECTED_REPLY_CANDIDATES,
    build_review_candidates,
    load_handoff,
    stable_group_id,
    validate_source_counts,
)


HANDOFF = Path("artifacts/integration/day08/ai_handoff.json")


def test_real_handoff_counts() -> None:
    data = load_handoff(HANDOFF)
    inquiries = data["inquiries"]

    validate_source_counts(inquiries)

    assert inquiries["collected_article_count"] == EXPECTED_COLLECTED
    assert inquiries["canonical_candidate_count"] == EXPECTED_CANONICAL
    assert inquiries["dedupe_excluded_count"] == EXPECTED_DEDUPE_EXCLUDED
    assert inquiries["conflict_quarantine_count"] == EXPECTED_CONFLICTS
    assert len(inquiries["query_eval_seed"]) == EXPECTED_QUERY_EVAL_SEED


def test_review_candidates_only_use_customer_inquiries() -> None:
    data = load_handoff(HANDOFF)
    candidates = build_review_candidates(data["inquiries"])

    assert len(candidates) == EXPECTED_CUSTOMER_INQUIRIES

    for row in candidates:
        assert row["input_text"]
        assert row["review"]["status"] == "REVIEW_REQUIRED"
        assert row["review"]["intent"] is None
        assert row["review"]["risk"] is None
        assert row["review"]["human_review_required"] is None


def test_historical_replies_are_not_promoted_to_nlu_truth() -> None:
    data = load_handoff(HANDOFF)
    seed = data["inquiries"]["query_eval_seed"]

    inquiries = [
        row
        for row in seed
        if row.get("source_type") == "CUSTOMER_INQUIRY"
    ]
    replies = [
        row
        for row in seed
        if row.get("source_type") == "HISTORICAL_REPLY_CANDIDATE"
    ]

    assert len(inquiries) == EXPECTED_CUSTOMER_INQUIRIES
    assert len(replies) == EXPECTED_REPLY_CANDIDATES
    assert all(row.get("policy_truth") is False for row in replies)


def test_group_id_is_deterministic_and_contains_no_raw_text() -> None:
    record = {
        "board_no": 6,
        "article_no": 123,
        "parent_article_no": None,
        "sanitized_query_text": "배송지 변경 문의입니다.",
    }

    group1 = stable_group_id(record)
    group2 = stable_group_id(record)

    assert group1 == group2
    assert len(group1) == 16
    assert "배송" not in group1


def test_review_candidates_have_unique_record_ids() -> None:
    data = load_handoff(HANDOFF)
    candidates = build_review_candidates(data["inquiries"])

    ids = [row["record_id"] for row in candidates]

    assert len(ids) == len(set(ids))


def test_generated_audit_remains_blocked_before_review() -> None:
    audit_path = Path("artifacts/experiments/day11/label_audit.json")

    assert audit_path.exists()

    audit = json.loads(audit_path.read_text(encoding="utf-8"))

    assert audit["real_inquiry_candidates"] == EXPECTED_CUSTOMER_INQUIRIES
    assert audit["reviewed_count"] == 0
    assert audit["unreviewed_count"] == EXPECTED_CUSTOMER_INQUIRIES
    assert audit["train_ready_count"] == 0
    assert audit["validation_ready_count"] == 0
    assert audit["test_accessed"] is False
    assert audit["status"] == "BLOCKED_REVIEW_REQUIRED"