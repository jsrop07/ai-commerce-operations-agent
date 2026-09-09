"""Day 8 Backend 최종 통합 검증."""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
    .parent
)

DAY08 = (
    ROOT
    / "artifacts"
    / "integration"
    / "day08"
)


def _json(
    name: str,
) -> dict:
    return json.loads(
        (DAY08 / name).read_text(
            encoding="utf-8"
        )
    )


def test_day08_required_artifacts_exist() -> None:
    required = {
        "ai_handoff.json",
        "cafe24_read.json",
        "toss_ecount.json",
        "provider_read_manifest.json",
        "consumer_contract_report.json",
        "provider_decision.md",
        "defects.csv",
        "retrieval_baseline.json",
        "retrieval_trace.json",
        "retrieval_cost.csv",
        "retrieval_consumer_report.json",
    }

    actual = {
        path.name
        for path in DAY08.iterdir()
        if path.is_file()
    }

    assert required <= actual


def test_day08_cafe24_counts_are_locked() -> None:
    payload = _json(
        "cafe24_read.json"
    )

    assert (
        payload["products"][
            "canonical_record_count"
        ]
        == 2167
    )

    assert (
        payload["orders"][
            "api_order_count"
        ]
        == 1402
    )

    assert (
        payload["orders"][
            "api_order_item_count"
        ]
        == 3934
    )

    assert (
        payload["community"][
            "canonical_article_count"
        ]
        == 624
    )


def test_day08_ai_handoff_counts_are_locked() -> None:
    payload = _json(
        "ai_handoff.json"
    )

    inquiries = payload[
        "inquiries"
    ]

    quality = inquiries[
        "quality"
    ]

    assert (
        quality[
            "query_candidate_count"
        ]
        == 308
    )

    assert (
        quality[
            "reply_candidate_count"
        ]
        == 316
    )

    assert (
        quality[
            "query_text_included_count"
        ]
        == 302
    )

    assert (
        quality[
            "reply_text_included_count"
        ]
        == 306
    )


def test_day08_retrieval_consumer_is_pass() -> None:
    payload = _json(
        "retrieval_consumer_report.json"
    )

    assert payload["status"] == "PASS"

    assert (
        payload["test_evidence"][
            "blocking_defects"
        ]
        == 0
    )


def test_day08_retrieval_is_safety_gated() -> None:
    payload = _json(
        "retrieval_consumer_report.json"
    )

    safety = payload[
        "safety_contract"
    ]

    assert (
        safety[
            "citation_missing"
        ]
        == "INSUFFICIENT_EVIDENCE"
    )

    assert (
        safety[
            "non_high_confidence"
        ]
        == "HOLD"
    )

    assert (
        safety[
            "production_write_allowed"
        ]
        is False
    )

    assert (
        safety[
            "provider_calls_allowed"
        ]
        is False
    )


def test_day08_backend_retrieval_contract_is_pass() -> None:
    payload = _json(
        "consumer_contract_report.json"
    )

    retrieval = payload[
        "backend_retrieval"
    ]

    assert (
        retrieval["official_item"]
        == "D08-BE-04"
    )

    assert (
        retrieval["status"]
        == "PASS"
    )

    assert (
        retrieval[
            "production_write_count"
        ]
        == 0
    )


def test_day08_has_no_open_blocking_defect() -> None:
    with (
        DAY08
        / "defects.csv"
    ).open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as fp:
        rows = list(
            csv.DictReader(fp)
        )

    blocking = [
        row
        for row in rows
        if (
            row.get("status")
            not in {
                "CLOSED",
                "OPEN_NON_BLOCKING",
            }
        )
        and row.get("severity")
        in {
            "HIGH",
            "CRITICAL",
        }
    ]

    assert blocking == []