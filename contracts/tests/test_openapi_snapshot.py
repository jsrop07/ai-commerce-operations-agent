import json
from pathlib import Path

from backend.app.core.config import Environment, Settings
from backend.app.main import create_app


def _field_signature(field: dict[str, object]) -> dict[str, object]:
    signature = {key: field[key] for key in ("type", "format", "default") if key in field}
    items = field.get("items")
    if isinstance(items, dict) and "type" in items:
        signature["items_type"] = items["type"]
    return signature


def test_openapi_signature_snapshot() -> None:
    schema = create_app(Settings(environment=Environment.TEST)).openapi()
    envelope_ref = schema["paths"]["/api/v1/insights"]["get"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]["$ref"]
    envelope = schema["components"]["schemas"][envelope_ref.rsplit("/", 1)[-1]]
    critical_fields = (
        "schema_version",
        "tenant_id",
        "request_id",
        "trace_id",
        "data",
        "evidence_ids",
        "warnings",
        "as_of",
    )
    actual = {
        "version": schema["info"]["version"],
        "paths": {
            path: sorted(methods)
            for path, methods in sorted(schema["paths"].items())
        },
        "required_event_fields": sorted(
            schema["components"]["schemas"]["CanonicalCommerceEvent"]["required"]
        ),
        "event_id_type": schema["components"]["schemas"]["CanonicalCommerceEvent"][
            "properties"
        ]["event_id"]["type"],
        "event_types": sorted(
            schema["components"]["schemas"]["EventType"]["enum"]
        ),
        "providers": sorted(
            schema["components"]["schemas"]["Provider"]["enum"]
        ),
        "api_envelope": {
            "required_fields": sorted(envelope["required"]),
            "critical_fields": {
                name: _field_signature(envelope["properties"][name])
                for name in critical_fields
            },
        },
    }
    expected = json.loads(Path("contracts/snapshots/openapi_signature.json").read_text())
    assert actual == expected
