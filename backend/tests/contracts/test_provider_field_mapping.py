from pathlib import Path

import yaml

MANIFEST_PATH = Path(__file__).parents[3] / "contracts" / "provider_field_mapping.yaml"
REQUIRED_MAPPING_FIELDS = {
    "source_path",
    "target",
    "transform",
    "nullable",
    "unknown_policy",
}


def _manifest() -> dict[str, object]:
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_has_version_and_all_day6_providers() -> None:
    manifest = _manifest()

    assert manifest["schema_version"] == "provider-field-mapping.v1"
    assert set(manifest["providers"]) == {"CAFE24", "TOSS_POS", "ECOUNT"}


def test_every_explicit_mapping_has_required_contract_fields() -> None:
    manifest = _manifest()

    checked = 0
    for provider in manifest["providers"].values():
        for resource in provider.get("resources", {}).values():
            for mapping in resource.get("mappings", []):
                assert REQUIRED_MAPPING_FIELDS <= mapping.keys()
                checked += 1

    assert checked > 0


def test_global_identity_and_unknown_policies_are_fail_closed() -> None:
    policy = _manifest()["global_policy"]

    assert policy["ambiguous_auto_merge"] is False
    assert policy["unknown_value_policy"] == "preserve"
    assert policy["pii_raw_to_canonical"] is False
    assert policy["raw_secret_to_canonical"] is False
    assert policy["production_write"] == "disabled"


def test_provider_modes_verification_and_source_quality_are_explicit() -> None:
    providers = _manifest()["providers"]
    toss = providers["TOSS_POS"]
    ecount = providers["ECOUNT"]

    assert toss["incremental_mode"]["orders"] == "API_POLL"
    assert toss["verification_level"]["incremental_orders"] == "CONTRACT_ONLY"
    assert toss["historical_backfill_mode"]["sales"] == "NOT_REQUIRED"
    assert ecount["source_quality"]["actual_inventory"] == "SOURCE_QUALITY_BLOCKED"
    assert ecount["incremental_mode"]["incoming"] == "UNKNOWN_BLOCKED"
    assert ecount["incremental_mode"]["sale"] == "UNKNOWN_BLOCKED"


def test_cafe24_backfill_checkpoint_and_api_checkpoint_are_independent() -> None:
    cafe24 = _manifest()["providers"]["CAFE24"]
    checkpoint = cafe24["checkpoint"]

    assert cafe24["historical_backfill_mode"]["products"] == "MANUAL_PROTECTED_IMPORT"
    assert cafe24["incremental_mode"]["products"] == "API_POLL"
    assert checkpoint["historical"] is not checkpoint["incremental"]
    assert checkpoint["historical"]["identity"] != checkpoint["incremental"]["identity"]
    assert checkpoint["historical"]["commit_rule"] == "after_canonical_commit"
    assert checkpoint["incremental"]["commit_rule"] == "after_canonical_commit"

    cutover = cafe24["cutover"]
    assert cutover["required"] is True
    assert "cutover_at or provider watermark" in cutover["rule"]
    assert "one effect only" in cutover["rule"]


def test_cafe24_manifest_header_coverage_is_complete_and_unambiguous() -> None:
    product_export = _manifest()["providers"]["CAFE24"]["resources"]["product_export"]
    mapped_headers = [mapping["source_path"] for mapping in product_export["mappings"]]
    preserved_headers = product_export["preserve_unknown_fields"]
    documented_headers = mapped_headers + preserved_headers

    assert product_export["unknown_column_policy"] == "preserve_metadata_unknown"
    assert len(mapped_headers) == 27
    assert len(preserved_headers) == 61
    assert len(documented_headers) == 88
    assert len(set(documented_headers)) == len(documented_headers)
    assert set(mapped_headers).isdisjoint(preserved_headers)


def test_fixture_resources_are_not_labelled_as_live_or_file_import() -> None:
    providers = _manifest()["providers"]
    fixture_kinds: list[str] = []

    for provider in providers.values():
        for resource in provider.get("resources", {}).values():
            source_kind = str(resource.get("source_kind", ""))
            if "fixture" in source_kind.lower():
                fixture_kinds.append(source_kind)

    assert fixture_kinds == ["official_contract_fixture", "synthetic_contract_fixture"]
    assert all(kind not in {"LIVE_READ", "FILE_IMPORT"} for kind in fixture_kinds)


def test_ecount_actual_inventory_cannot_reach_canonical_effects() -> None:
    policy = _manifest()["providers"]["ECOUNT"]["resources"]["inventory_fixture"][
        "actual_source_policy"
    ]

    assert policy == {
        "status": "SOURCE_QUALITY_BLOCKED",
        "inventory_ledger_effect": "forbidden",
        "inventory_total_effect": "forbidden",
        "ai_confirmed_answer": "forbidden",
    }
