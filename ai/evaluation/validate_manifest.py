from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL_FIELDS = {
    "schema_version",
    "official_item",
    "status",
    "production_write_allowed",
    "backend_handoff",
    "golden_retrieval",
    "measured_evaluation_baseline",
    "sanitized_real_input",
    "taxonomy_domain_fit",
    "corpus_query_separation",
    "leakage_controls",
    "findings",
}


def _require(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise ValueError(message)


def validate_retrieval_baseline(
    payload: dict[str, Any],
) -> None:
    missing = sorted(
        REQUIRED_TOP_LEVEL_FIELDS
        - set(payload)
    )

    _require(
        not missing,
        "missing top-level fields: "
        + ", ".join(missing),
    )

    _require(
        payload["schema_version"]
        == "retrieval-baseline.v1",
        "unexpected schema_version",
    )

    _require(
        payload["official_item"]
        == "D08-AI-02",
        "official_item must be D08-AI-02",
    )

    _require(
        payload["production_write_allowed"]
        is False,
        "production_write_allowed must be false",
    )

    backend = payload["backend_handoff"]

    _require(
        backend.get("source_classification")
        == "SANITIZED_REAL",
        "backend handoff must be SANITIZED_REAL",
    )

    _require(
        bool(backend.get("sha256")),
        "backend handoff sha256 is required",
    )

    golden = payload["golden_retrieval"]

    _require(
        golden.get("status") == "READY",
        "golden_retrieval must be READY",
    )

    _require(
        bool(golden.get("expected_hash")),
        "golden_retrieval expected_hash is required",
    )

    measured = payload[
        "measured_evaluation_baseline"
    ]

    _require(
        measured.get("source_classification")
        == "FIXTURE",
        "measured evaluation baseline must be FIXTURE",
    )

    dataset = measured["dataset"]

    _require(
        dataset.get("query_count") == 16,
        "measured dataset query_count must be 16",
    )

    _require(
        bool(dataset.get("sha256")),
        "measured dataset sha256 is required",
    )

    snapshot = measured["snapshot"]

    _require(
        snapshot.get("chunk_count") == 31,
        "snapshot chunk_count must be 31",
    )

    _require(
        bool(snapshot.get("hash")),
        "snapshot hash is required",
    )

    for retriever in ("bm25", "dense"):
        section = measured[retriever]

        _require(
            bool(section.get("result_sha256")),
            f"{retriever} result_sha256 is required",
        )

        _require(
            bool(section.get("index_version")),
            f"{retriever} index_version is required",
        )

        _require(
            bool(section.get("metrics")),
            f"{retriever} metrics are required",
        )

    dense = measured["dense"]

    embedding = dense.get("embedding") or {}

    _require(
        bool(embedding.get("model")),
        "dense embedding model is required",
    )

    _require(
        bool(embedding.get("revision")),
        "dense embedding revision is required",
    )

    real_input = payload[
        "sanitized_real_input"
    ]

    product = real_input["product"]

    _require(
        product.get("canonical_count") == 2167,
        "SANITIZED_REAL product count must be 2167",
    )

    _require(
        product.get("mapping_coverage_count")
        == 2167,
        "product mapping coverage must be 2167",
    )

    _require(
        product.get("mapping_unknown_count") == 0,
        "product mapping unknown must be 0",
    )

    inquiry = real_input["inquiry"]

    _require(
        inquiry.get(
            "total_sanitized_natural_language_seed"
        )
        == 608,
        "sanitized natural-language count must be 608",
    )

    _require(
        inquiry.get("customer_inquiry_count")
        == 302,
        "customer inquiry count must be 302",
    )

    _require(
        inquiry.get(
            "historical_reply_candidate_count"
        )
        == 306,
        "historical reply count must be 306",
    )

    _require(
        inquiry.get(
            "candidate_label_preassigned_count"
        )
        == 0,
        "Backend must not preassign AI labels",
    )

    taxonomy = payload[
        "taxonomy_domain_fit"
    ]

    _require(
        taxonomy.get("canonical_enum_extended")
        is False,
        "canonical taxonomy must not be extended yet",
    )

    leakage = payload["leakage_controls"]

    _require(
        leakage.get(
            "historical_reply_used_as_policy_truth"
        )
        is False,
        "historical reply must not be policy truth",
    )

    _require(
        leakage.get(
            "historical_reply_used_as_authoritative_answer_corpus"
        )
        is False,
        "historical reply must not be authoritative corpus",
    )

    _require(
        leakage.get("raw_community_text_included")
        is False,
        "raw community text must not be included",
    )

    _require(
        leakage.get("attachment_content_included")
        is False,
        "attachment content must not be included",
    )


def validate_file(path: Path) -> None:
    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(payload, dict):
        raise ValueError(
            "manifest root must be an object"
        )

    validate_retrieval_baseline(
        payload
    )


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "usage: python -m "
            "ai.evaluation.validate_manifest "
            "<retrieval_baseline.json>"
        )
        return 2

    path = Path(sys.argv[1])

    if not path.exists():
        print(
            f"ERROR: file not found: {path}"
        )
        return 2

    try:
        validate_file(path)
    except (
        json.JSONDecodeError,
        ValueError,
        KeyError,
        TypeError,
    ) as exc:
        print(
            f"VALIDATION_FAILED: {exc}"
        )
        return 1

    print(
        "VALIDATION_OK: "
        f"{path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())