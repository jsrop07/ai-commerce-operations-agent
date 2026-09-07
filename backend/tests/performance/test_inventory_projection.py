import json

from backend.app.services.inventory_benchmark import (
    run_inventory_benchmark,
    run_inventory_db_benchmark,
    write_inventory_benchmark_manifest,
)


def test_inventory_projection_2000_sku_90_day_baseline() -> None:
    result = run_inventory_benchmark(
        sku_count=2_000,
        period_days=90,
    )

    assert result.sku_count == 2_000
    assert result.period_days == 90

    # 19 unique + 1 deliberate duplicate
    # for each of 2,000 SKUs.
    assert result.attempted_events == 40_000
    assert result.accepted_events == 38_000
    assert result.duplicate_inputs == 2_000

    assert result.duplicate_input_rate == 0.05

    # Duplicate inputs must not produce ledger effects.
    assert result.duplicate_effect_count == 0

    assert result.projection_p50_ms >= 0
    assert result.projection_p95_ms >= 0
    assert result.projection_p95_ms >= result.projection_p50_ms

    assert result.total_elapsed_ms > 0


def test_small_benchmark_is_deterministic_in_counts() -> None:
    result = run_inventory_benchmark(
        sku_count=10,
        period_days=90,
    )

    assert result.attempted_events == 200
    assert result.accepted_events == 190
    assert result.duplicate_inputs == 10
    assert result.duplicate_input_rate == 0.05
    assert result.duplicate_effect_count == 0


def test_inventory_db_2000_sku_baseline() -> None:
    result = run_inventory_db_benchmark(
        sku_count=2_000,
    )

    assert result.sku_count == 2_000
    assert result.snapshot_row_count == 2_000
    assert result.ledger_row_count == 38_000
    assert result.projection_row_count == 2_000

    # Projection 조회가 SKU별 N+1이 되어서는 안 된다.
    assert result.projection_query_count <= 2

    assert result.projection_elapsed_ms > 0

    assert result.db_backend == "sqlite_in_memory"
    assert result.verification_level == "SYNTHETIC_BASELINE"


def test_benchmark_manifest_records_safety_and_scope(
    tmp_path,
) -> None:
    output = tmp_path / "inventory_benchmark.json"

    written = write_inventory_benchmark_manifest(
        path=output,
    )

    assert written == output
    assert written.exists()

    data = json.loads(written.read_text(encoding="utf-8"))

    assert data["benchmark_id"] == "D07-BE-05"

    assert data["verification_level"] == "SYNTHETIC_BASELINE"

    assert data["workload"]["sku_count"] == 2_000
    assert data["workload"]["period_days"] == 90

    assert data["workload"]["real_business_data_used"] is False

    assert data["compute"]["duplicate_effect_count"] == 0

    assert data["database"]["projection_row_count"] == 2_000

    assert data["database"]["projection_query_count"] <= 2

    assert data["safety"]["external_write_count"] == 0

    assert data["safety"]["production_schedule_enabled"] is False
