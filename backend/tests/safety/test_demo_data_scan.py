import re
from pathlib import Path

SCAN_ROOTS = [Path("backend"), Path("contracts"), Path("artifacts/integration/day04")]
EXCLUDED_NAMES = {"test_demo_data_scan.py"}
PATTERNS = {
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "korean_phone": re.compile(r"\b01[016789]-?\d{3,4}-?\d{4}\b"),
    "credential_assignment": re.compile(
        r"(?i)(api[_-]?key|secret|access[_-]?token|password)\s*[=:]\s*['\"][^'\"]{8,}"
    ),
}


def test_no_apparent_raw_pii_or_secret_in_c1_artifacts() -> None:
    findings: list[str] = []
    for root in SCAN_ROOTS:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".json", ".csv"}:
                continue
            if path.name in EXCLUDED_NAMES:
                continue
            text = path.read_text(encoding="utf-8")
            for name, pattern in PATTERNS.items():
                if pattern.search(text):
                    findings.append(f"{path}:{name}")
    assert findings == []
