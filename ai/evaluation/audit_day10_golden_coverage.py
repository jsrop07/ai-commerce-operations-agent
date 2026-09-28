from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


GOLDEN_PATH = Path(
    "ai/evaluation/datasets/golden_retrieval.jsonl"
)

CORPUS_PATH = Path(
    "ai/tests/fixtures/retrieval_chunking_corpus.jsonl"
)

OUTPUT_PATH = Path(
    "artifacts/experiments/day10/coverage_audit.json"
)

SCHEMA_VERSION = "day10-coverage-audit.v1"
AUDIT_VERSION = "day10-f01-audit-v1"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def classify_missing(slice_name: str) -> str:
    if slice_name in {
        "product_exact",
        "product_alias_typo",
    }:
        return "PRODUCT_SOURCE_DOCUMENT_MISSING"

    if slice_name == "compatibility":
        return "RELATION_SOURCE_DOCUMENT_MISSING"

    if slice_name == "component":
        return "COMPONENT_SOURCE_DOCUMENT_MISSING"

    if slice_name == "inventory_freshness":
        return "SQL_INVENTORY_EVIDENCE_MISSING"

    if slice_name == "order_delivery":
        return "SQL_ORDER_OR_INCOMING_EVIDENCE_MISSING"

    if slice_name == "policy":
        return "POLICY_SOURCE_DOCUMENT_MISSING"

    return "UNCLASSIFIED_EVIDENCE_MISSING"


def build_audit() -> dict[str, Any]:
    golden = load_jsonl(GOLDEN_PATH)
    corpus = load_jsonl(CORPUS_PATH)

    corpus_ids = {
        str(row["source_id"])
        for row in corpus
        if row.get("source_id")
    }

    answerable = [
        row
        for row in golden
        if row.get("expected_answerability")
        == "ANSWERABLE"
    ]

    covered: list[dict[str, Any]] = []
    uncovered: list[dict[str, Any]] = []

    relevant_ids: set[str] = set()

    for query in answerable:
        query_relevant_ids = [
            str(item["source_id"])
            for item in query.get(
                "relevant",
                [],
            )
            if item.get("source_id")
        ]

        relevant_ids.update(
            query_relevant_ids
        )

        matched = sorted(
            set(query_relevant_ids)
            & corpus_ids
        )

        item = {
            "query_id": query["query_id"],
            "slice": query["slice"],
            "split": query["split"],
            "relevant_source_ids":
                query_relevant_ids,
            "matched_source_ids": matched,
        }

        if matched:
            covered.append(item)
        else:
            item["reason"] = (
                classify_missing(
                    query["slice"]
                )
            )
            uncovered.append(item)

    missing_by_slice = Counter(
        row["slice"]
        for row in uncovered
    )

    missing_by_reason = Counter(
        row["reason"]
        for row in uncovered
    )

    validation = [
        row
        for row in answerable
        if row["split"] == "validation"
    ]

    test = [
        row
        for row in answerable
        if row["split"] == "test"
    ]

    validation_covered = sum(
        1
        for query in validation
        if any(
            str(rel["source_id"])
            in corpus_ids
            for rel in query.get(
                "relevant",
                [],
            )
        )
    )

    test_covered = sum(
        1
        for query in test
        if any(
            str(rel["source_id"])
            in corpus_ids
            for rel in query.get(
                "relevant",
                [],
            )
        )
    )

    result = {
        "schema_version": SCHEMA_VERSION,
        "audit_version": AUDIT_VERSION,
        "finding_id": "D09-AI-05-F01",
        "status": "ROOT_CAUSE_CONFIRMED",
        "golden": {
            "path": str(GOLDEN_PATH),
            "sha256": sha256_file(
                GOLDEN_PATH
            ),
            "query_count": len(golden),
            "answerable_count":
                len(answerable),
            "unique_relevant_source_count":
                len(relevant_ids),
        },
        "current_corpus": {
            "path": str(CORPUS_PATH),
            "sha256": sha256_file(
                CORPUS_PATH
            ),
            "record_count": len(corpus),
            "unique_source_count":
                len(corpus_ids),
        },
        "coverage": {
            "covered": len(covered),
            "uncovered": len(uncovered),
            "answerable_total":
                len(answerable),
            "ratio": (
                len(covered)
                / len(answerable)
                if answerable
                else None
            ),
            "validation": {
                "covered":
                    validation_covered,
                "total": len(validation),
            },
            "test": {
                "covered":
                    test_covered,
                "total": len(test),
            },
        },
        "missing_by_slice":
            dict(sorted(
                missing_by_slice.items()
            )),
        "missing_by_reason":
            dict(sorted(
                missing_by_reason.items()
            )),
        "covered_queries": covered,
        "uncovered_queries":
            uncovered,
        "root_cause": (
            "Golden60 contains relevance labels "
            "for evidence IDs whose backing "
            "source documents or SQL evidence "
            "fixtures are mostly absent from "
            "the current evaluation evidence "
            "universe. The existing corpus is "
            "a Day 7 chunking fixture rather "
            "than a complete Golden60 corpus."
        ),
        "decision": {
            "change_golden_labels": False,
            "auto_remove_uncovered":
                False,
            "activate_reranker": False,
            "activate_top_k_policy": False,
            "activate_confidence_threshold":
                False,
            "next_action": (
                "Construct only verified "
                "backing evidence sources and "
                "re-run coverage before "
                "retrieval superiority claims."
            ),
        },
        "safety": {
            "production_provider_write":
                False,
            "external_embedding_api_calls":
                0,
            "golden_labels_modified":
                False,
        },
    }

    return result


def main() -> None:
    result = build_audit()

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print("DAY10_COVERAGE_AUDIT_OK")

    print(
        "GOLDEN_SHA256=",
        result["golden"]["sha256"],
    )

    print(
        "CORPUS_SHA256=",
        result[
            "current_corpus"
        ]["sha256"],
    )

    print(
        "ANSWERABLE=",
        result[
            "coverage"
        ]["answerable_total"],
    )

    print(
        "COVERED=",
        result["coverage"]["covered"],
    )

    print(
        "UNCOVERED=",
        result[
            "coverage"
        ]["uncovered"],
    )

    print(
        "VALIDATION=",
        result[
            "coverage"
        ]["validation"],
    )

    print(
        "TEST=",
        result[
            "coverage"
        ]["test"],
    )

    print(
        "OUTPUT=",
        OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()