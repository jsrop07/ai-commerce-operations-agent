import json

import pytest
from pydantic import ValidationError

from backend.app.services.demo import DEMO_SCENARIOS
from contracts.events import CanonicalCommerceEvent


def test_valid_event() -> None:
    event = CanonicalCommerceEvent.model_validate(DEMO_SCENARIOS["offline_sale"])
    assert event.source_event_id == "synthetic-02"
    assert event.payload["quantity"] == 1


@pytest.mark.parametrize("missing", ["tenant_id", "source_event_id", "payload"])
def test_required_field_missing(missing: str) -> None:
    value = dict(DEMO_SCENARIOS["offline_sale"])
    value.pop(missing)
    with pytest.raises(ValidationError):
        CanonicalCommerceEvent.model_validate(value)


def test_invalid_enum_and_naive_timestamp() -> None:
    value = dict(
        DEMO_SCENARIOS["offline_sale"], source="GUESSED", occurred_at="2026-01-01T00:00:00"
    )
    with pytest.raises(ValidationError):
        CanonicalCommerceEvent.model_validate(value)


def test_duplicate_json_key_rejected() -> None:
    raw = json.dumps(DEMO_SCENARIOS["offline_sale"])
    duplicate = raw[:-1] + ', "tenant_id": "second"}'
    with pytest.raises(ValueError, match="duplicate JSON key"):
        CanonicalCommerceEvent.model_validate_json_unique(duplicate)
