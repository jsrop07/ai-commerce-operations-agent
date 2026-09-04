from backend.app.services.demo import (
    DEMO_SCENARIOS,
    SCENARIO_EXPECTATIONS,
    duplicate_offline_sale_fixture,
    scenario,
)


def test_six_deterministic_synthetic_scenarios() -> None:
    assert set(DEMO_SCENARIOS) == {
        "offline_sale",
        "reservation_shortage",
        "incoming_delay",
        "product_inquiry",
        "risk_inquiry",
        "duplicate_event",
    }
    assert set(SCENARIO_EXPECTATIONS) == set(DEMO_SCENARIOS)
    assert all(scenario(name).tenant_id == "demo_store" for name in DEMO_SCENARIOS)
    assert all(SCENARIO_EXPECTATIONS[name] for name in DEMO_SCENARIOS)


def test_scenarios_are_deterministic_and_return_isolated_inputs() -> None:
    for name in DEMO_SCENARIOS:
        assert scenario(name) == scenario(name)
    first = scenario("product_inquiry")
    assert first.payload["pii_status"] == "clean"
    assert first.occurred_at == first.ingested_at


def test_expected_results_match_synthetic_inputs() -> None:
    offline_sale = scenario("offline_sale")
    assert SCENARIO_EXPECTATIONS["offline_sale"]["inventory_delta"] == -offline_sale.payload[
        "quantity"
    ]

    reservation = scenario("reservation_shortage")
    shortage = (
        reservation.payload["reserved"]
        - reservation.payload["available"]
        - reservation.payload["confirmed_incoming"]
    )
    assert SCENARIO_EXPECTATIONS["reservation_shortage"]["shortage_quantity"] == shortage

    incoming_delay = scenario("incoming_delay")
    assert (
        SCENARIO_EXPECTATIONS["incoming_delay"]["delay_days"]
        == incoming_delay.payload["delay_days"]
    )


def test_duplicate_fixture_preserves_source_identity() -> None:
    first, second = duplicate_offline_sale_fixture()
    assert first.idempotency_key == second.idempotency_key
    assert first.event_id == second.event_id
    assert first.source_event_id == second.source_event_id
    assert SCENARIO_EXPECTATIONS["duplicate_event"]["processed_effect_count"] == 1
