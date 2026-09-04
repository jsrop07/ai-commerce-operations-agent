from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
CATALOG_PATH = ROOT / "ai" / "router" / "task_catalog.yaml"


def load_catalog():
    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_task_catalog_exists():
    assert CATALOG_PATH.exists()


def test_required_tasks_exist():
    catalog = load_catalog()
    required = {
        "inventory_calculation",
        "reservation_shortage",
        "schedule_conflict",
        "inquiry_classification",
        "grounded_answer_draft",
        "complex_operations_judgment",
        "refund_cancel_price_pii",
    }
    assert required.issubset(catalog["tasks"].keys())


def test_all_tasks_have_primary_route():
    catalog = load_catalog()

    for task_name, task in catalog["tasks"].items():
        assert task.get("primary_route"), task_name
        assert task.get("large_model_not_used_reason"), task_name


def test_deterministic_tasks_do_not_use_llm():
    catalog = load_catalog()

    for task_name in ("inventory_calculation", "reservation_shortage"):
        task = catalog["tasks"][task_name]
        assert task["primary_route"] == "RULE_SQL"
        assert task["model_required"] is False
        assert task["large_model_allowed"] is False


def test_prohibited_actions_are_policy_denied():
    task = load_catalog()["tasks"]["refund_cancel_price_pii"]

    assert task["primary_route"] == "POLICY_DENY"
    assert task["risk_level"] == "PROHIBITED"
    assert task["large_model_allowed"] is False
    assert task["human_required"] is True