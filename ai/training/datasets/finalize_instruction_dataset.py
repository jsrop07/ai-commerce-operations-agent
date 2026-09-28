from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


SAFE_PATH = Path(
    "artifacts/experiments/day11/external_safe_candidates.jsonl"
)

PILOT_TRUTH_PATH = Path(
    "artifacts/experiments/day11/pilot_20_reviewed_truth.csv"
)

OUTPUT_DIR = Path(
    "artifacts/experiments/day11/instruction_dataset"
)

MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
REVIEWED_PATH = OUTPUT_DIR / "reviewed_pilot.jsonl"


MIN_TOTAL_PER_CLASS = 10
MIN_TRAIN_PER_CLASS = 8
MIN_VALID_PER_CLASS = 2


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]


def load_truth(path: Path) -> list[dict]:
    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        return list(csv.DictReader(f))


def to_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def main() -> int:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    safe_rows = load_jsonl(SAFE_PATH)
    truth_rows = load_truth(PILOT_TRUTH_PATH)

    safe_by_id = {
        row["record_id"]: row
        for row in safe_rows
    }

    reviewed = []

    for truth in truth_rows:
        record_id = truth["record_id"]

        if record_id not in safe_by_id:
            raise ValueError(
                f"{record_id} is not in safe pool"
            )

        reviewed.append(
            {
                "record_id": record_id,
                "group_id": safe_by_id[
                    record_id
                ]["group_id"],
                "input_text": safe_by_id[
                    record_id
                ]["input_text"],
                "eligible_for_nlu": to_bool(
                    truth["eligible_for_nlu"]
                ),
                "exclusion_reason": (
                    truth["exclusion_reason"]
                    or None
                ),
                "intent": (
                    truth["intent"]
                    or None
                ),
                "entities_json": (
                    truth["entities_json"]
                    or ""
                ),
                "risk": truth["risk"],
                "human_review_required": to_bool(
                    truth[
                        "human_review_required"
                    ]
                ),
                "review_status": "REVIEWED",
                "reviewer": truth["reviewer"],
                "reviewed_at": truth[
                    "reviewed_at"
                ],
                "label_version": truth[
                    "label_version"
                ],
            }
        )

    REVIEWED_PATH.write_text(
        "\n".join(
            json.dumps(
                row,
                ensure_ascii=False,
            )
            for row in reviewed
        )
        + "\n",
        encoding="utf-8",
    )

    eligible = [
        row
        for row in reviewed
        if row["eligible_for_nlu"]
    ]

    intent_counts = Counter(
        row["intent"]
        for row in eligible
    )

    insufficient = {
        intent: count
        for intent, count in intent_counts.items()
        if count < MIN_TOTAL_PER_CLASS
    }

    manifest = {
        "schema_version": (
            "day11-instruction-dataset.v1"
        ),
        "safe_candidate_count": len(
            safe_rows
        ),
        "reviewed_pilot_count": len(
            reviewed
        ),
        "eligible_reviewed_count": len(
            eligible
        ),
        "intent_support": dict(
            sorted(intent_counts.items())
        ),
        "minimum_support_policy": {
            "total_per_class": (
                MIN_TOTAL_PER_CLASS
            ),
            "train_per_class": (
                MIN_TRAIN_PER_CLASS
            ),
            "validation_per_class": (
                MIN_VALID_PER_CLASS
            ),
        },
        "insufficient_classes": (
            insufficient
        ),
        "train_split_created": False,
        "validation_split_created": False,
        "test_accessed": False,
        "real_qlora_ready": False,
        "status": (
            "BLOCKED_MORE_REVIEW_REQUIRED"
        ),
        "hashes": {
            "safe_candidates_sha256": (
                sha256_file(SAFE_PATH)
            ),
            "reviewed_pilot_sha256": (
                sha256_file(REVIEWED_PATH)
            ),
        },
    }

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"SAFE_CANDIDATES={len(safe_rows)}"
    )
    print(
        f"REVIEWED_PILOT={len(reviewed)}"
    )
    print(
        f"ELIGIBLE_REVIEWED={len(eligible)}"
    )
    print(
        f"INTENT_SUPPORT={dict(intent_counts)}"
    )
    print(
        "REAL_QLORA_READY=False"
    )
    print(
        "STATUS=BLOCKED_MORE_REVIEW_REQUIRED"
    )
    print(f"MANIFEST={MANIFEST_PATH}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())