from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "ai" / "evaluation" / "datasets" / "manifest.yaml"


def load_manifest():
    with MANIFEST_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_dataset_manifest_exists():
    assert MANIFEST_PATH.exists()


def test_required_dataset_groups_exist():
    datasets = load_manifest()["datasets"]

    required = {
        "golden_nlu",
        "golden_retrieval",
        "golden_graph",
        "memory_scenarios",
        "agent_scenarios",
        "private_business_validation",
    }

    assert required.issubset(datasets.keys())


def test_all_datasets_have_required_metadata():
    datasets = load_manifest()["datasets"]

    required_fields = {
        "purpose",
        "owner",
        "version",
        "expected_hash",
        "visibility",
        "contains_real_data",
        "pii_status",
        "split_strategy",
        "status",
    }

    for name, dataset in datasets.items():
        missing = required_fields - dataset.keys()
        assert not missing, f"{name}: missing {sorted(missing)}"


def test_publication_of_real_data_is_disabled():
    manifest = load_manifest()

    assert manifest["global_rules"]["real_data_publication_allowed"] is False


def test_train_validation_test_isolation_enabled():
    manifest = load_manifest()

    assert manifest["global_rules"]["train_validation_test_isolation"] is True
    assert manifest["global_rules"]["synthetic_test_answer_visibility"] is False