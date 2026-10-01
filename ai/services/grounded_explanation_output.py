from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExplanationStatus(str, Enum):
    ANSWER = "ANSWER"
    HOLD = "HOLD"


@dataclass(frozen=True)
class ClaimCitation:
    source_id: str
    version: str


@dataclass(frozen=True)
class NumericFact:
    field: str
    value: int
    unit: str = "count"


@dataclass(frozen=True)
class GroundedExplanationOutput:
    status: ExplanationStatus
    conclusion: str
    used_facts: tuple[str, ...]
    citations: tuple[ClaimCitation, ...]
    next_check: str | None
    used_numeric_facts: tuple[NumericFact, ...] = ()

    def __post_init__(self) -> None:
        if not self.conclusion.strip():
            raise ValueError("conclusion must not be empty")
        if self.status == ExplanationStatus.HOLD and (self.used_facts or self.used_numeric_facts):
            raise ValueError("HOLD must not present used facts as an answer")
