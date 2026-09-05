import hashlib
import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class DedupeRecord:
    source_id: str
    version: str
    normalized_text: str
    source_hash: str
    text_hash: str


@dataclass(frozen=True)
class DedupeResult:
    kept: list[dict]
    removed: list[dict]
    duplicate_pairs: list[dict]


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def build_source_hash(
    source_id: str,
    version: str,
) -> str:
    return sha256_text(
        f"{source_id}:{version}"
    )


def build_text_hash(
    text: str,
) -> str:
    return sha256_text(
        normalize_text(text)
    )


def near_duplicate_score(
    left: str,
    right: str,
) -> float:
    return SequenceMatcher(
        None,
        normalize_text(left),
        normalize_text(right),
    ).ratio()


def same_version(
    left: dict,
    right: dict,
) -> bool:
    return (
        left["source_id"]
        == right["source_id"]
        and left["version"]
        == right["version"]
    )


def deduplicate_records(
    records: list[dict],
    *,
    near_duplicate_threshold: float = 0.92,
) -> DedupeResult:
    if not 0.0 <= near_duplicate_threshold <= 1.0:
        raise ValueError(
            "near_duplicate_threshold must be between 0 and 1"
        )

    kept: list[dict] = []
    removed: list[dict] = []
    duplicate_pairs: list[dict] = []

    for record in records:
        duplicate_of: dict | None = None
        duplicate_reason: str | None = None
        duplicate_score: float | None = None

        for existing in kept:
            # 버전이 다르면 절대로 중복 제거하지 않는다.
            if (
                record["source_id"]
                == existing["source_id"]
                and record["version"]
                != existing["version"]
            ):
                continue

            record_hash = build_text_hash(
                record["content"]
            )
            existing_hash = build_text_hash(
                existing["content"]
            )

            if record_hash == existing_hash:
                duplicate_of = existing
                duplicate_reason = (
                    "NORMALIZED_TEXT_HASH"
                )
                duplicate_score = 1.0
                break

            score = near_duplicate_score(
                record["content"],
                existing["content"],
            )

            if score >= near_duplicate_threshold:
                duplicate_of = existing
                duplicate_reason = (
                    "NEAR_DUPLICATE"
                )
                duplicate_score = score
                break

        if duplicate_of is None:
            kept.append(record)
            continue

        removed.append(record)

        duplicate_pairs.append(
            {
                "removed_source_id": (
                    record["source_id"]
                ),
                "removed_version": (
                    record["version"]
                ),
                "kept_source_id": (
                    duplicate_of["source_id"]
                ),
                "kept_version": (
                    duplicate_of["version"]
                ),
                "reason": duplicate_reason,
                "score": round(
                    duplicate_score or 0.0,
                    4,
                ),
            }
        )

    return DedupeResult(
        kept=kept,
        removed=removed,
        duplicate_pairs=duplicate_pairs,
    )