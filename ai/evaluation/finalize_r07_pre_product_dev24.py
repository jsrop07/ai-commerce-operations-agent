import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

BASE = (
    ROOT
    / "artifacts"
    / "experiments"
    / "OPS-RAG-SCALE-01"
    / "private"
)

DRAFT = BASE / "actual_product_dev24_draft.jsonl"
REVIEW = BASE / "actual_product_dev24_review.csv"
FINAL = BASE / "actual_product_dev24.jsonl"
MANIFEST = BASE / "actual_product_dev24_manifest.json"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


draft_rows = [
    json.loads(line)
    for line in DRAFT.read_text(
        encoding="utf-8"
    ).splitlines()
    if line.strip()
]

with REVIEW.open(
    encoding="utf-8-sig",
    newline="",
) as f:
    review_rows = list(
        csv.DictReader(f)
    )

if len(draft_rows) != 24:
    raise RuntimeError(
        f"draft count != 24: {len(draft_rows)}"
    )

if len(review_rows) != 24:
    raise RuntimeError(
        f"review count != 24: {len(review_rows)}"
    )

review_by_id = {
    row["case_id"]: row
    for row in review_rows
}

final_rows = []

for case in draft_rows:
    review = review_by_id[
        case["case_id"]
    ]

    decision = review[
        "review_decision"
    ].strip()

    if decision not in {
        "APPROVE",
        "REVISE",
    }:
        raise RuntimeError(
            f"{case['case_id']} "
            f"not approved: {decision}"
        )

    if (
        review["evidence_correct"]
        .strip()
        .upper()
        != "TRUE"
    ):
        raise RuntimeError(
            f"{case['case_id']} "
            "evidence not approved"
        )

    if decision == "REVISE":
        revised = review[
            "reviewed_query"
        ].strip()

        if not revised:
            raise RuntimeError(
                f"{case['case_id']} "
                "missing reviewed_query"
            )

        case["query"] = revised

    reviewed_answerability = (
        review[
            "reviewed_answerability"
        ].strip()
    )

    if reviewed_answerability:
        case["answerability"] = (
            reviewed_answerability
        )

    hold_reason = review[
        "hold_reason"
    ].strip()

    case["hold_reason"] = (
        hold_reason or None
    )

    case["review_status"] = (
        "HUMAN_REVIEWED"
    )

    case["review_decision"] = decision

    case["semantic_duplicate"] = (
        review[
            "semantic_duplicate"
        ].strip().upper()
        == "TRUE"
    )

    final_rows.append(case)


with FINAL.open(
    "w",
    encoding="utf-8",
    newline="",
) as f:
    for row in final_rows:
        f.write(
            json.dumps(
                row,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n"
        )


manifest = json.loads(
    MANIFEST.read_text(
        encoding="utf-8"
    )
)

manifest[
    "status"
] = "HUMAN_REVIEWED"

manifest[
    "human_review_completed"
] = True

manifest[
    "human_review_method"
] = (
    "USER_CONFIRMED_24_CASES"
)

manifest[
    "approved_count"
] = sum(
    row["review_decision"]
    == "APPROVE"
    for row in review_rows
)

manifest[
    "revised_count"
] = sum(
    row["review_decision"]
    == "REVISE"
    for row in review_rows
)

manifest[
    "semantic_duplicate_count"
] = sum(
    row[
        "semantic_duplicate"
    ].strip().upper()
    == "TRUE"
    for row in review_rows
)

manifest[
    "review_file_sha256"
] = sha256_file(REVIEW)

manifest[
    "final_dev24_sha256"
] = sha256_file(FINAL)

MANIFEST.write_text(
    json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)


print("R07_PRE_DEV24_FINALIZED")
print("final_count=", len(final_rows))
print(
    "human_reviewed=",
    sum(
        row["review_status"]
        == "HUMAN_REVIEWED"
        for row in final_rows
    ),
)
print(
    "approved=",
    manifest["approved_count"],
)
print(
    "revised=",
    manifest["revised_count"],
)
print(
    "semantic_duplicates=",
    manifest[
        "semantic_duplicate_count"
    ],
)
print(
    "final_sha256=",
    manifest[
        "final_dev24_sha256"
    ],
)
print(
    "review_sha256=",
    manifest[
        "review_file_sha256"
    ],
)
print("FINAL12_USED=false")