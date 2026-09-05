from pathlib import Path

import yaml


CATALOG_PATH = Path("ai/retrieval/corpus_catalog.yaml")


def load_catalog() -> dict:
    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def test_corpus_catalog_has_required_sources() -> None:
    catalog = load_catalog()

    source_types = {
        source["source_type"]
        for source in catalog["sources"]
    }

    assert source_types == {
        "PRODUCT",
        "POLICY",
        "INVENTORY_SNAPSHOT",
        "INCOMING_STOCK",
        "ORDER_STATUS",
    }


def test_every_source_has_owner_freshness_visibility() -> None:
    catalog = load_catalog()

    for source in catalog["sources"]:
        assert source["owner"]
        assert source["freshness"]
        assert source["visibility"]


def test_live_operational_sources_use_sql_evidence() -> None:
    catalog = load_catalog()

    by_type = {
        source["source_type"]: source
        for source in catalog["sources"]
    }

    for source_type in {
        "INVENTORY_SNAPSHOT",
        "INCOMING_STOCK",
        "ORDER_STATUS",
    }:
        assert by_type[source_type]["retrieval_mode"] == "SQL_EVIDENCE"


def test_inventory_has_stale_definitive_answer_guard() -> None:
    catalog = load_catalog()

    inventory = next(
        source
        for source in catalog["sources"]
        if source["source_type"] == "INVENTORY_SNAPSHOT"
    )

    assert (
        "stale_snapshot_must_not_support_definitive_stock_answer"
        in inventory["restrictions"]
    )