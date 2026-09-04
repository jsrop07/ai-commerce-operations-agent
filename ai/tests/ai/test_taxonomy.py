from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
TAXONOMY_PATH = ROOT / "ai" / "data" / "taxonomy.yaml"

REQUIRED_SECTIONS = {
    "intent",
    "entity",
    "risk",
    "product_relation",
    "anomaly",
}


def load_taxonomy():
    with TAXONOMY_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_taxonomy_exists():
    assert TAXONOMY_PATH.exists()


def test_required_sections_exist():
    taxonomy = load_taxonomy()

    assert taxonomy.get("schema_version") == "taxonomy.v0.1"
    assert REQUIRED_SECTIONS.issubset(taxonomy.keys())


def test_each_section_is_not_empty():
    taxonomy = load_taxonomy()

    for section in REQUIRED_SECTIONS:
        assert taxonomy[section], f"{section} must not be empty"


def test_no_duplicate_labels_within_section():
    taxonomy = load_taxonomy()

    for section in REQUIRED_SECTIONS:
        labels = [item["label"] for item in taxonomy[section]]

        assert len(labels) == len(set(labels)), (
            f"{section} contains duplicate labels"
        )


def test_no_duplicate_labels_across_sections():
    taxonomy = load_taxonomy()

    all_labels = []

    for section in REQUIRED_SECTIONS:
        for item in taxonomy[section]:
            all_labels.append((item["label"], section))

    seen = {}
    duplicates = []

    for label, section in all_labels:
        if label in seen:
            duplicates.append(
                {
                    "label": label,
                    "first_section": seen[label],
                    "second_section": section,
                }
            )
        else:
            seen[label] = section

    assert duplicates == []


def test_all_labels_have_descriptions():
    taxonomy = load_taxonomy()

    for section in REQUIRED_SECTIONS:
        for item in taxonomy[section]:
            description = item.get("description")

            assert isinstance(description, str)
            assert description.strip(), (
                f"{section}.{item.get('label')} has empty description"
            )


def test_all_labels_have_examples():
    taxonomy = load_taxonomy()

    for section in REQUIRED_SECTIONS:
        for item in taxonomy[section]:
            examples = item.get("examples")

            assert isinstance(examples, list)
            assert examples, (
                f"{section}.{item.get('label')} has no examples"
            )

            for example in examples:
                assert isinstance(example, str)
                assert example.strip()


def test_risk_labels_match_project_contract():
    taxonomy = load_taxonomy()

    labels = {item["label"] for item in taxonomy["risk"]}

    assert labels == {
        "LOW",
        "MEDIUM",
        "HIGH",
        "PROHIBITED",
    }


def test_product_relation_labels_match_contract():
    taxonomy = load_taxonomy()

    labels = {item["label"] for item in taxonomy["product_relation"]}

    assert labels == {
        "BASE_GAME_OF",
        "EXPANSION_OF",
        "CONTAINS",
        "ACCESSORY_FOR",
        "COMPATIBLE_WITH",
        "PROMO_FOR",
    }