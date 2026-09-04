from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]

ACTIVE_PATH = (
    ROOT
    / "ai"
    / "prompts"
    / "inquiry"
    / "ACTIVE"
)


HIGH_RISK = {
    "HIGH",
    "PROHIBITED",
}


@dataclass
class MockRuntimeCounters:
    external_model_calls: int = 0
    tool_calls: int = 0
    provider_calls: int = 0
    auto_send_count: int = 0


class MockAIRuntime:
    """
    Deterministic Day 4 integration runtime.

    This runtime performs no external model,
    tool, provider, or customer-send action.
    """

    def __init__(self) -> None:
        self.counters = MockRuntimeCounters()

        self._active = yaml.safe_load(
            ACTIVE_PATH.read_text(
                encoding="utf-8"
            )
        )

    @property
    def prompt_version(self) -> str:
        return str(
            self._active["selected"]["version"]
        )

    def _route_for_risk(
        self,
        risk: str,
    ) -> tuple[str, str]:
        normalized = risk.strip().upper()

        if normalized == "PROHIBITED":
            return (
                "POLICY_DENY",
                "PROHIBITED_ACTION_REQUIRES_HUMAN_OPERATION",
            )

        if normalized == "HIGH":
            return (
                "HUMAN_REVIEW",
                "HIGH_RISK_INQUIRY_REQUIRES_HUMAN_REVIEW",
            )

        if normalized == "MEDIUM":
            return (
                "HUMAN_REVIEW",
                "MEDIUM_RISK_DAY04_MOCK_REVIEW",
            )

        return (
            "RULE_SQL",
            "LOW_RISK_DETERMINISTIC_MOCK_ROUTE",
        )

    def run(
        self,
        *,
        request_id: str,
        trace_id: str,
        intent: str,
        risk: str,
        evidence_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        route, route_reason = (
            self._route_for_risk(risk)
        )

        warnings = [
            "MOCK_RUNTIME",
            "NO_EXTERNAL_MODEL_CALL",
            "NO_TOOL_CALL",
            "NO_PROVIDER_CALL",
            "NO_AUTO_SEND",
        ]

        return {
            "schema_version":
                "ai-response.v0.1",

            "request_id":
                request_id,

            "trace_id":
                trace_id,

            "task_type":
                "inquiry_classification",

            "intent":
                intent,

            "route":
                route,

            "route_reason":
                route_reason,

            "confidence":
                1.0,

            "evidence_ids":
                list(
                    evidence_ids or []
                ),

            "warnings":
                warnings,

            "model": {
                "model_run_id":
                    None,

                "model_id":
                    None,

                "prompt_version":
                    self.prompt_version,
            },

            "token": {
                "input": 0,
                "output": 0,
                "cache": 0,
            },

            "latency": {
                "total_ms": 0.0,
            },

            "cost": {
                "estimated": 0.0,
                "currency": "USD",
            },
        }