import hashlib
from dataclasses import asdict, dataclass
from typing import Any


LIVE_SOURCE_TYPES = {
    "INVENTORY_SNAPSHOT",
    "INCOMING_STOCK",
    "ORDER_STATUS",
}


@dataclass(frozen=True)
class Citation:
    source_id: str
    title: str
    record_id: str
    as_of: str | None
    field_or_path: str
    excerpt_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CitationDecision:
    decision: str
    citations: tuple[Citation, ...]
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "citations": [
                citation.to_dict()
                for citation in self.citations
            ],
            "reason": self.reason,
        }


def build_excerpt_hash(excerpt: str) -> str:
    normalized = " ".join(excerpt.split())

    digest = hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()

    return f"sha256:{digest}"


def build_citation(evidence: dict[str, Any]) -> Citation:
    required = {
        "source_id",
        "title",
        "record_id",
        "source_type",
        "field_or_path",
        "excerpt",
    }

    missing = sorted(
        field
        for field in required
        if not evidence.get(field)
    )

    if missing:
        raise ValueError(
            "missing citation evidence fields: "
            + ", ".join(missing)
        )

    source_type = evidence["source_type"]
    as_of = evidence.get("as_of")

    if source_type in LIVE_SOURCE_TYPES and not as_of:
        raise ValueError(
            f"{source_type} citation requires as_of"
        )

    return Citation(
        source_id=evidence["source_id"],
        title=evidence["title"],
        record_id=evidence["record_id"],
        as_of=as_of,
        field_or_path=evidence["field_or_path"],
        excerpt_hash=build_excerpt_hash(
            evidence["excerpt"]
        ),
    )


def citation_or_abstain(
    evidence_items: list[dict[str, Any]],
) -> CitationDecision:
    if not evidence_items:
        return CitationDecision(
            decision="ABSTAIN",
            citations=(),
            reason="INSUFFICIENT_EVIDENCE",
        )

    citations: list[Citation] = []

    try:
        for evidence in evidence_items:
            citations.append(build_citation(evidence))
    except ValueError:
        return CitationDecision(
            decision="ABSTAIN",
            citations=(),
            reason="INVALID_EVIDENCE",
        )

    if not citations:
        return CitationDecision(
            decision="ABSTAIN",
            citations=(),
            reason="INSUFFICIENT_EVIDENCE",
        )

    return CitationDecision(
        decision="ANSWER",
        citations=tuple(citations),
        reason=None,
    )