from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
PROMPT_PATH = ROOT / "ai" / "prompts" / "_template" / "prompt.yaml"


def load_prompt():
    with PROMPT_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_prompt_template_exists():
    assert PROMPT_PATH.exists()


def test_prompt_required_sections():
    prompt = load_prompt()

    required = {
        "prompt_id",
        "version",
        "system",
        "instruction",
        "examples",
        "output_schema",
        "verification",
        "safety",
        "registry",
    }

    assert required.issubset(prompt.keys())


def test_prompt_version_is_defined():
    prompt = load_prompt()

    assert prompt["version"]
    assert prompt["registry"]["input_schema_version"]
    assert prompt["registry"]["output_schema_version"]


def test_prompt_safety_defaults():
    prompt = load_prompt()

    assert prompt["safety"]["autonomous_external_write"] is False
    assert prompt["safety"]["high_risk_route"] == "HUMAN_REVIEW"