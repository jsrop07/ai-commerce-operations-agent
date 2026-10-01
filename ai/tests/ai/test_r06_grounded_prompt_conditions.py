from pathlib import Path

import yaml


BASIC_PATH = Path(
    "ai/prompts/grounded_explanation/basic.yaml"
)
CITATION_PATH = Path(
    "ai/prompts/grounded_explanation/citation.yaml"
)


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_two_prompt_conditions_exist() -> None:
    basic = _load(BASIC_PATH)
    citation = _load(CITATION_PATH)

    assert basic["condition"] == "BASIC"
    assert citation["condition"] == "CITATION"

    assert basic["output_requirements"]["citation_required"] is False
    assert citation["output_requirements"]["citation_required"] is True


def test_core_safety_instructions_match() -> None:
    basic = _load(BASIC_PATH)
    citation = _load(CITATION_PATH)

    required_rules = (
        "수치를 새로 계산하거나 변경하지 않는다.",
        "null 또는 알 수 없는 값을 0으로 바꾸지 않는다.",
        "제공된 근거가 지원하지 않는 내용을 추측하지 않는다.",
    )

    for rule in required_rules:
        assert rule in basic["system"]
        assert rule in citation["system"]


def test_only_citation_condition_requires_citation() -> None:
    basic = _load(BASIC_PATH)
    citation = _load(CITATION_PATH)

    assert "source_id" not in basic["system"]
    assert "source_id" in citation["system"]
