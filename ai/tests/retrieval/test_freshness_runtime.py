from __future__ import annotations

from datetime import datetime, timezone

from ai.retrieval.freshness import (
    FreshnessState,
    build_version_catalog,
    evaluate_freshness,
    load_freshness_policy,
)


def test_version_catalog_preserves_multiple_versions() -> None:
    rows = [
        {
            "source_id": "policy_shipping_demo",
            "version": "v1",
        },
        {
            "source_id": "policy_shipping_demo",
            "version": "v2",
        },
    ]

    catalog = build_version_catalog(
        rows
    )

    assert catalog[
        "policy_shipping_demo"
    ] == [
        "v1",
        "v2",
    ]


def test_old_policy_version_is_stale() -> None:
    policy = load_freshness_policy()

    catalog = {
        "policy_shipping_demo": [
            "v1",
            "v2",
        ]
    }

    result = evaluate_freshness(
        source_type="POLICY",
        source_id="policy_shipping_demo",
        version="v1",
        metadata={},
        policy=policy,
        version_catalog=catalog,
    )

    assert (
        result.state
        == FreshnessState.STALE
    )

    assert (
        "v2"
        in result.reason
    )


def test_latest_policy_version_is_fresh() -> None:
    policy = load_freshness_policy()

    result = evaluate_freshness(
        source_type="POLICY",
        source_id="policy_shipping_demo",
        version="v2",
        metadata={},
        policy=policy,
        version_catalog={
            "policy_shipping_demo": [
                "v1",
                "v2",
            ]
        },
    )

    assert (
        result.state
        == FreshnessState.FRESH
    )


def test_single_product_version_is_fresh() -> None:
    policy = load_freshness_policy()

    result = evaluate_freshness(
        source_type="PRODUCT",
        source_id="product_demo_001",
        version="v1",
        metadata={},
        policy=policy,
        version_catalog={
            "product_demo_001": [
                "v1"
            ]
        },
    )

    assert (
        result.state
        == FreshnessState.FRESH
    )


def test_unknown_version_format_is_not_guessed() -> None:
    policy = load_freshness_policy()

    result = evaluate_freshness(
        source_type="PRODUCT",
        source_id="product_x",
        version="release-a",
        metadata={},
        policy=policy,
        version_catalog={
            "product_x": [
                "release-a",
                "release-b",
            ]
        },
    )

    assert (
        result.state
        == FreshnessState.MISSING
    )


def test_inventory_missing_as_of_is_stale() -> None:
    policy = load_freshness_policy()

    result = evaluate_freshness(
        source_type=(
            "INVENTORY_SNAPSHOT"
        ),
        source_id="inventory_1",
        version="v1",
        metadata={},
        policy=policy,
        version_catalog={},
        now=datetime(
            2026,
            9,
            7,
            5,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert (
        result.state
        == FreshnessState.STALE
    )

    assert (
        result.reason
        == "as_of_missing"
    )


def test_inventory_inside_ttl_is_fresh() -> None:
    policy = load_freshness_policy()

    result = evaluate_freshness(
        source_type=(
            "INVENTORY_SNAPSHOT"
        ),
        source_id="inventory_1",
        version="v1",
        metadata={
            "as_of": (
                "2026-09-07T04:58:00+00:00"
            )
        },
        policy=policy,
        version_catalog={},
        now=datetime(
            2026,
            9,
            7,
            5,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert (
        result.state
        == FreshnessState.FRESH
    )


def test_inventory_outside_ttl_is_stale() -> None:
    policy = load_freshness_policy()

    result = evaluate_freshness(
        source_type=(
            "INVENTORY_SNAPSHOT"
        ),
        source_id="inventory_1",
        version="v1",
        metadata={
            "as_of": (
                "2026-09-07T04:50:00+00:00"
            )
        },
        policy=policy,
        version_catalog={},
        now=datetime(
            2026,
            9,
            7,
            5,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert (
        result.state
        == FreshnessState.STALE
    )


def test_undefined_faq_policy_is_not_assumed_fresh() -> None:
    policy = load_freshness_policy()

    result = evaluate_freshness(
        source_type="FAQ",
        source_id="faq_demo",
        version="v1",
        metadata={},
        policy=policy,
        version_catalog={
            "faq_demo": [
                "v1"
            ]
        },
    )

    assert (
        result.state
        == FreshnessState.POLICY_UNDEFINED
    )

    assert (
        result.definitive_answer_allowed
        is False
    )