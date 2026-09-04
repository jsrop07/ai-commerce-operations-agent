import hashlib
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]

ACTIVE_PATH = (
    ROOT
    / "ai"
    / "prompts"
    / "inquiry"
    / "ACTIVE"
)


def load_active():
    return yaml.safe_load(
        ACTIVE_PATH.read_text(
            encoding="utf-8"
        )
    )


def test_active_file_exists():
    assert ACTIVE_PATH.exists()


def test_active_is_day04_only():
    active = load_active()

    assert (
        active["status"]
        == "ADOPTED_FOR_DAY04_INTEGRATION_ONLY"
    )

    assert (
        active["final_production_decision"]
        is False
    )


def test_active_prompt_path_exists():
    active = load_active()

    prompt_path = (
        ROOT
        / active["selected"]["path"]
    )

    assert prompt_path.exists()


def test_active_prompt_hash_matches():
    active = load_active()

    prompt_path = (
        ROOT
        / active["selected"]["path"]
    )

    actual_hash = hashlib.sha256(
        prompt_path.read_bytes()
    ).hexdigest()

    assert (
        actual_hash
        == active["selected"]["sha256"]
    )


def test_active_prompt_identity_matches():
    active = load_active()

    prompt_path = (
        ROOT
        / active["selected"]["path"]
    )

    prompt = yaml.safe_load(
        prompt_path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        prompt["prompt_id"]
        == active["selected"]["prompt_id"]
    )

    assert (
        prompt["version"]
        == active["selected"]["version"]
    )


def test_active_references_prompt01():
    active = load_active()

    assert (
        active["experiment"]["experiment_id"]
        == "PROMPT-01"
    )

    result_path = (
        ROOT
        / active["experiment"][
            "result_path"
        ]
    )

    assert result_path.exists()