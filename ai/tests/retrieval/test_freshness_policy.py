from pathlib import Path

import yaml


POLICY_PATH = Path("ai/retrieval/freshness.yaml")


def load_policy() -> dict:
    with POLICY_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_all_catalog_sources_have_freshness_policy() -> None:
    policy = load_policy()

    assert set(policy["sources"]) == {
        "PRODUCT",
        "POLICY",
        "INVENTORY_SNAPSHOT",
        "INCOMING_STOCK",
        "ORDER_STATUS",
    }


def test_live_sources_have_positive_ttl() -> None:
    policy = load_policy()

    for source_type in {
        "INVENTORY_SNAPSHOT",
        "INCOMING_STOCK",
        "ORDER_STATUS",
    }:
        source = policy["sources"][source_type]

        assert source["freshness_mode"] == "TTL"
        assert isinstance(source["ttl_seconds"], int)
        assert source["ttl_seconds"] > 0
        assert source["required_time_field"] == "as_of"


def test_inventory_stale_data_cannot_support_definitive_answer() -> None:
    policy = load_policy()

    inventory = policy["sources"]["INVENTORY_SNAPSHOT"]

    assert inventory["definitive_answer_allowed_when_stale"] is False
    assert inventory["fallback"] == "HUMAN_REVIEW"
    assert inventory["refresh_preferred"] is True


def test_missing_as_of_is_stale_for_live_sources() -> None:
    policy = load_policy()

    for source_type in {
        "INVENTORY_SNAPSHOT",
        "INCOMING_STOCK",
        "ORDER_STATUS",
    }:
        source = policy["sources"][source_type]

        assert "as_of_missing" in source["stale_when"]


def test_versioned_sources_do_not_use_live_ttl() -> None:
    policy = load_policy()

    for source_type in {"PRODUCT", "POLICY"}:
        source = policy["sources"][source_type]

        assert source["freshness_mode"] == "VERSIONED"
        assert source["ttl_seconds"] is None


def test_initial_ttl_is_not_claimed_as_production_sla() -> None:
    policy = load_policy()

    basis = policy["policy_basis"]

    assert basis["ttl_values_are"] == "DEMO_EVAL_INITIAL"
    assert basis["production_sla_confirmed"] is False