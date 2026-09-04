import json
import re
from difflib import SequenceMatcher
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]

FEWSHOT_PATH = (
    ROOT
    / "ai"
    / "prompts"
    / "inquiry"
    / "v2_fewshot.yaml"
)

GOLDEN_PATH = (
    ROOT
    / "ai"
    / "evaluation"
    / "datasets"
    / "golden_nlu_v0.1.json"
)


NEAR_DUPLICATE_THRESHOLD = 0.85


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[?!.,]", "", text)

    return text


def load_fewshot_examples():
    with FEWSHOT_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        prompt = yaml.safe_load(file)

    examples = prompt["examples"]

    return (
        examples["positive"]
        + examples["boundary"]
        + examples["abstain"]
    )


def load_golden_records():
    with GOLDEN_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)["records"]


def test_fewshot_examples_are_train_only():
    examples = load_fewshot_examples()

    assert examples

    for example in examples:
        assert example["source_split"] == "train"


def test_fewshot_example_count_is_allowed():
    examples = load_fewshot_examples()

    assert 5 <= len(examples) <= 8


def test_no_exact_validation_or_test_leakage():
    examples = load_fewshot_examples()
    golden = load_golden_records()

    protected_texts = {
        normalize_text(record["text"]): record["id"]
        for record in golden
        if record["split"] in {
            "validation",
            "test",
        }
    }

    for example in examples:
        normalized = normalize_text(
            example["input"]
        )

        assert normalized not in protected_texts, (
            f"exact leakage: "
            f"{example['example_id']} -> "
            f"{protected_texts.get(normalized)}"
        )


def test_no_near_duplicate_validation_or_test_leakage():
    examples = load_fewshot_examples()
    golden = load_golden_records()

    protected = [
        record
        for record in golden
        if record["split"] in {
            "validation",
            "test",
        }
    ]

    violations = []

    for example in examples:
        source = normalize_text(
            example["input"]
        )

        for record in protected:
            target = normalize_text(
                record["text"]
            )

            similarity = SequenceMatcher(
                None,
                source,
                target,
            ).ratio()

            if similarity >= NEAR_DUPLICATE_THRESHOLD:
                violations.append(
                    {
                        "fewshot_id":
                            example["example_id"],
                        "golden_id":
                            record["id"],
                        "similarity":
                            round(similarity, 4),
                    }
                )

    assert violations == []


def test_example_ids_are_unique():
    examples = load_fewshot_examples()

    ids = [
        example["example_id"]
        for example in examples
    ]

    assert len(ids) == len(set(ids))