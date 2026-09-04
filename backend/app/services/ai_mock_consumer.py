"""Backend boundary for the deterministic Day 4 AI Mock Runtime."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from ai.services.mock_runtime import MockAIRuntime

ROOT = Path(__file__).resolve().parents[3]

AI_RESPONSE_SCHEMA_PATH = (
    ROOT
    / "contracts"
    / "ai_response.schema.json"
)


class AIMockConsumer:
    """Validate AI-track Mock responses before Backend consumes them."""

    def __init__(self) -> None:
        self.runtime = MockAIRuntime()
        self.schema = json.loads(
            AI_RESPONSE_SCHEMA_PATH.read_text(
                encoding="utf-8"
            )
        )

    def classify_inquiry(
        self,
        *,
        request_id: str,
        trace_id: str,
        intent: str,
        risk: str,
        evidence_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        response = self.runtime.run(
            request_id=request_id,
            trace_id=trace_id,
            intent=intent,
            risk=risk,
            evidence_ids=evidence_ids,
        )

        jsonschema.validate(
            instance=response,
            schema=self.schema,
        )

        if response["request_id"] != request_id or response["trace_id"] != trace_id:
            raise ValueError("AI response request/trace ID mismatch")

        return response
