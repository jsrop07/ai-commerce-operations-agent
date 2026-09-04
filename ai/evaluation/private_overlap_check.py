import argparse
import json
import os
from pathlib import Path

from ai.data.synthetic.generator import (
    find_private_fingerprint_overlap,
)


def load_json(path: Path):
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--synthetic",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--private",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--report",
        type=Path,
        required=True,
    )

    args = parser.parse_args()

    secret_key = os.environ.get(
        "PRIVATE_OVERLAP_HMAC_KEY"
    )

    if not secret_key:
        print(
            "PRIVATE_OVERLAP_BLOCKED "
            "reason=PRIVATE_OVERLAP_HMAC_KEY_MISSING"
        )
        return 2

    synthetic = load_json(
        args.synthetic
    )

    private_payload = load_json(
        args.private
    )

    if (
        private_payload.get("pii_status")
        != "SANITIZED"
    ):
        print(
            "PRIVATE_OVERLAP_BLOCKED "
            "reason=PRIVATE_CORPUS_NOT_SANITIZED"
        )
        return 2

    unique_strings = private_payload.get(
        "unique_strings",
        [],
    )

    overlaps = find_private_fingerprint_overlap(
        synthetic,
        unique_strings,
        secret_key,
    )

    report = {
        "schema_version":
            "private-overlap-report.v0.1",
        "private_corpus_pii_status":
            "SANITIZED",
        "private_unique_string_count":
            len(unique_strings),
        "overlap_count":
            len(overlaps),
        "overlap_fingerprints":
            overlaps,
        "raw_private_strings_written":
            False,
    }

    args.report.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with args.report.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            report,
            file,
            ensure_ascii=False,
            indent=2,
        )

    if overlaps:
        print(
            "PRIVATE_OVERLAP_FAILED "
            f"count={len(overlaps)}"
        )
        return 1

    print(
        "PRIVATE_OVERLAP_OK "
        f"private_strings={len(unique_strings)} "
        "overlap=0"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())