import json
from pathlib import Path


def test_day04_contract_report_is_explicit_about_ai_handoff() -> None:
    report = json.loads(
        Path("artifacts/integration/day04/contract_report.json").read_text()
    )

    assert report["breaking_differences"] == 0

    ai_response = report["contracts"]["ai_response"]

    assert ai_response["status"] == "VERIFIED"
    assert ai_response["version"] == "ai-response.v0.1"

    assert report["status"] == "PASS_WITH_INTEGRATION_FINDINGS"

def test_day04_contract_report_records_integration_findings() -> None:
    report = json.loads(
        Path("artifacts/integration/day04/contract_report.json").read_text()
    )

    findings = {
        finding["id"]: finding
        for finding in report["integration_findings"]
    }

    assert "D04-CONTRACT-001" in findings
    assert "D04-CONTRACT-002" in findings
    assert "D04-CONTRACT-003" in findings
    assert "D04-CONTRACT-004" in findings
    assert "D04-CONTRACT-005" in findings

    assert (
        findings["D04-CONTRACT-001"]["status"]
        == "RESOLVED_BY_BOUNDARY"
    )

    assert (
        findings["D04-CONTRACT-002"]["status"]
        == "OPEN_NON_BLOCKING"
    )

    assert (
        findings["D04-CONTRACT-003"]["status"]
        == "OPEN_NON_BLOCKING"
    )

    assert (
        findings["D04-CONTRACT-004"]["status"]
        == "RESOLVED_BY_IDEMPOTENCY"
    )

    assert (
        findings["D04-CONTRACT-005"]["status"]
        == "RESOLVED_BY_BOUNDARY"
    )
