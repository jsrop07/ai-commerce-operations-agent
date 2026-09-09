from pathlib import Path

import pytest
import yaml

from backend.app.adapters.providers.base import (
    UnsupportedCapability,
)
from backend.app.adapters.providers.ecount.adapter import (
    EcountAdapter,
)
from backend.app.adapters.providers.toss_pos.adapter import (
    TossPosAdapter,
)


MAPPING_PATH = (
    Path(__file__).parents[3]
    / "contracts"
    / "provider_field_mapping.yaml"
)


def _manifest() -> dict[str, object]:
    return yaml.safe_load(
        MAPPING_PATH.read_text(
            encoding="utf-8"
        )
    )


def test_day08_toss_is_contract_only() -> None:
    provider = (
        _manifest()["providers"]["TOSS_POS"]
    )

    assert (
        provider["verification_level"][
            "incremental_orders"
        ]
        == "CONTRACT_ONLY"
    )

    assert (
        provider["historical_backfill_mode"][
            "sales"
        ]
        == "NOT_REQUIRED"
    )


def test_day08_ecount_actual_inventory_is_source_quality_blocked() -> None:
    provider = (
        _manifest()["providers"]["ECOUNT"]
    )

    assert (
        provider["source_quality"][
            "actual_inventory"
        ]
        == "SOURCE_QUALITY_BLOCKED"
    )

    assert (
        provider["incremental_mode"][
            "incoming"
        ]
        == "UNKNOWN_BLOCKED"
    )

    assert (
        provider["incremental_mode"][
            "sale"
        ]
        == "UNKNOWN_BLOCKED"
    )


def test_day08_ecount_inventory_cannot_reach_confirmed_effects() -> None:
    policy = (
        _manifest()["providers"]["ECOUNT"][
            "resources"
        ]["inventory_fixture"][
            "actual_source_policy"
        ]
    )

    assert policy["status"] == (
        "SOURCE_QUALITY_BLOCKED"
    )

    assert (
        policy["inventory_ledger_effect"]
        == "forbidden"
    )

    assert (
        policy["inventory_total_effect"]
        == "forbidden"
    )

    assert (
        policy["ai_confirmed_answer"]
        == "forbidden"
    )


def test_day08_fixture_sources_are_not_mislabelled_as_live() -> None:
    providers = _manifest()["providers"]

    for provider in providers.values():
        for resource in (
            provider.get(
                "resources",
                {},
            ).values()
        ):
            source_kind = str(
                resource.get(
                    "source_kind",
                    "",
                )
            )

            if "fixture" in source_kind.lower():
                assert source_kind not in {
                    "LIVE_READ",
                    "FILE_IMPORT",
                }


def test_day08_toss_live_inventory_read_is_not_enabled() -> None:
    adapter = TossPosAdapter()

    with pytest.raises(
        UnsupportedCapability
    ):
        adapter.read_inventory()


def test_day08_ecount_live_inventory_read_is_blocked() -> None:
    adapter = EcountAdapter()

    with pytest.raises(
        UnsupportedCapability
    ):
        adapter.read_inventory()