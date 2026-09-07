from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter_ns

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.models.catalog import SKU, Brand, Product
from backend.app.models.commerce import (
    InventoryLedger,
    InventorySnapshot,
)
from backend.app.services.inventory_ledger import InventoryLedgerService
from backend.app.services.inventory_projection import build_inventory_projection


@dataclass(frozen=True)
class InventoryBenchmarkResult:
    sku_count: int
    period_days: int
    attempted_events: int
    accepted_events: int
    duplicate_inputs: int
    duplicate_input_rate: float
    duplicate_effect_count: int
    projection_p50_ms: float
    projection_p95_ms: float
    total_elapsed_ms: float


@dataclass(frozen=True)
class InventoryDbBenchmarkResult:
    sku_count: int
    ledger_row_count: int
    snapshot_row_count: int
    projection_row_count: int
    projection_query_count: int
    projection_elapsed_ms: float
    db_backend: str
    verification_level: str


def _percentile(
    values: list[float],
    percentile: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    index = round((len(ordered) - 1) * percentile)
    return ordered[index]


def run_inventory_benchmark(
    *,
    sku_count: int = 2_000,
    period_days: int = 90,
) -> InventoryBenchmarkResult:
    if sku_count < 1:
        raise ValueError("sku_count must be >= 1")
    if period_days < 1:
        raise ValueError("period_days must be >= 1")

    ledger = InventoryLedgerService()

    # 19 unique events + 1 duplicate attempt per SKU.
    # 2,000 SKU -> 40,000 attempted events,
    # of which exactly 5% are duplicate input attempts.
    unique_events_per_sku = 19

    attempted_events = 0
    accepted_events = 0
    duplicate_inputs = sku_count
    duplicate_effect_count = 0

    delta_by_sku: dict[str, int] = {}

    base_time = datetime(
        2026,
        6,
        8,
        0,
        0,
        tzinfo=UTC,
    )

    total_started = perf_counter_ns()

    for sku_index in range(sku_count):
        sku_id = f"sku-bench-{sku_index:04d}"
        sku_delta = 0

        first_event: dict[str, object] | None = None

        for event_index in range(unique_events_per_sku):
            occurred_at = base_time + timedelta(
                days=min(
                    event_index * 5,
                    period_days - 1,
                )
            )

            # Deterministic mixture:
            # every 4th event is incoming stock, otherwise sale.
            if event_index % 4 == 0:
                delta = 3
                reason = "INCOMING_STOCK"
            else:
                delta = -1
                reason = "OFFLINE_SALE"

            business_key = f"bench:{sku_id}:{event_index}"
            source_event_id = f"bench-event:{sku_id}:{event_index}"

            payload = {
                "tenant_id": "benchmark-store",
                "sku_id": sku_id,
                "delta": delta,
                "reason": reason,
                "business_key": business_key,
                "source_event_id": source_event_id,
                "occurred_at": occurred_at,
            }

            if first_event is None:
                first_event = payload

            attempted_events += 1

            applied = ledger.append_once(**payload)

            if applied:
                accepted_events += 1
                sku_delta += delta

        assert first_event is not None

        # One deliberate duplicate per SKU.
        attempted_events += 1

        duplicate_applied = ledger.append_once(**first_event)

        if duplicate_applied:
            accepted_events += 1
            sku_delta += int(first_event["delta"])
            duplicate_effect_count += 1

        delta_by_sku[sku_id] = sku_delta

    projection_latencies_ms: list[float] = []

    for sku_index in range(sku_count):
        sku_id = f"sku-bench-{sku_index:04d}"

        started = perf_counter_ns()

        result = build_inventory_projection(
            tenant_id="benchmark-store",
            sku_id=sku_id,
            source_on_hand=100,
            ledger_delta=delta_by_sku[sku_id],
            reserved=sku_index % 4,
            confirmed_incoming=sku_index % 3,
            quality_status="CONFIRMED",
            ttl_seconds=300,
            age_seconds=60,
            risk_level="LOW",
            evidence=(f"benchmark-snapshot:{sku_id}",),
        )

        elapsed_ms = (perf_counter_ns() - started) / 1_000_000

        projection_latencies_ms.append(elapsed_ms)

        if result.expected_inventory is None:
            raise AssertionError("confirmed benchmark projection must have expected_inventory")

    total_elapsed_ms = (perf_counter_ns() - total_started) / 1_000_000

    duplicate_input_rate = duplicate_inputs / attempted_events

    # A duplicate effect would mean a duplicate input
    # incorrectly produced another ledger entry.
    # Count accepted deliberate replays independently of missing unique events.

    return InventoryBenchmarkResult(
        sku_count=sku_count,
        period_days=period_days,
        attempted_events=attempted_events,
        accepted_events=accepted_events,
        duplicate_inputs=duplicate_inputs,
        duplicate_input_rate=duplicate_input_rate,
        duplicate_effect_count=duplicate_effect_count,
        projection_p50_ms=_percentile(
            projection_latencies_ms,
            0.50,
        ),
        projection_p95_ms=_percentile(
            projection_latencies_ms,
            0.95,
        ),
        total_elapsed_ms=total_elapsed_ms,
    )


def run_inventory_db_benchmark(
    *,
    sku_count: int = 2_000,
) -> InventoryDbBenchmarkResult:
    if sku_count < 1:
        raise ValueError("sku_count must be >= 1")

    engine = create_engine("sqlite+pysqlite:///:memory:")

    with engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    tenant_id = "benchmark-store"
    as_of = datetime(
        2026,
        9,
        6,
        0,
        0,
        tzinfo=UTC,
    )

    ledger_row_count = 0

    with Session(engine) as session:
        brand = Brand(
            tenant_id=tenant_id,
            canonical_name="Benchmark Brand",
            aliases=[],
        )

        product = Product(
            tenant_id=tenant_id,
            name="Benchmark Product",
            brand=brand,
        )

        skus: list[SKU] = []

        for index in range(sku_count):
            skus.append(
                SKU(
                    tenant_id=tenant_id,
                    product=product,
                    canonical_code=(f"BENCH-SKU-{index:04d}"),
                    status="ACTIVE",
                )
            )

        session.add_all(skus)
        session.flush()

        snapshots: list[InventorySnapshot] = []
        ledger_rows: list[InventoryLedger] = []

        for index, sku in enumerate(skus):
            snapshots.append(
                InventorySnapshot(
                    tenant_id=tenant_id,
                    provider="SYNTHETIC",
                    sku_id=sku.id,
                    on_hand=100,
                    reserved=index % 4,
                    as_of=as_of,
                )
            )

            # SKU당 19개의 deterministic ledger row.
            for event_index in range(19):
                if event_index % 4 == 0:
                    delta = 3
                    reason = "INCOMING_STOCK"
                else:
                    delta = -1
                    reason = "OFFLINE_SALE"

                ledger_rows.append(
                    InventoryLedger(
                        tenant_id=tenant_id,
                        sku_id=sku.id,
                        delta=delta,
                        reason=reason,
                        source_event_id=(f"bench-db:{index}:{event_index}"),
                        occurred_at=(
                            as_of
                            - timedelta(
                                days=min(
                                    event_index * 5,
                                    89,
                                )
                            )
                        ),
                    )
                )

        ledger_row_count = len(ledger_rows)

        session.add_all(snapshots)
        session.add_all(ledger_rows)
        session.commit()

    query_count = 0

    def count_query(
        *_: object,
        **__: object,
    ) -> None:
        nonlocal query_count
        query_count += 1

    event.listen(
        engine,
        "before_cursor_execute",
        count_query,
    )

    started = perf_counter_ns()

    with Session(engine) as session:
        ledger_totals = (
            select(
                InventoryLedger.sku_id.label("sku_id"),
                func.sum(InventoryLedger.delta).label("ledger_delta"),
            )
            .where(InventoryLedger.tenant_id == tenant_id)
            .group_by(InventoryLedger.sku_id)
            .subquery()
        )

        statement = (
            select(
                InventorySnapshot.sku_id,
                InventorySnapshot.on_hand,
                InventorySnapshot.reserved,
                ledger_totals.c.ledger_delta,
            )
            .outerjoin(
                ledger_totals,
                ledger_totals.c.sku_id == InventorySnapshot.sku_id,
            )
            .where(InventorySnapshot.tenant_id == tenant_id)
        )

        rows = session.execute(statement).all()

    projection_elapsed_ms = (perf_counter_ns() - started) / 1_000_000

    event.remove(
        engine,
        "before_cursor_execute",
        count_query,
    )

    engine.dispose()

    return InventoryDbBenchmarkResult(
        sku_count=sku_count,
        ledger_row_count=ledger_row_count,
        snapshot_row_count=sku_count,
        projection_row_count=len(rows),
        projection_query_count=query_count,
        projection_elapsed_ms=projection_elapsed_ms,
        db_backend="sqlite_in_memory",
        verification_level="SYNTHETIC_BASELINE",
    )


def write_inventory_benchmark_manifest(
    *,
    path: str | Path = ("artifacts/integration/day07/inventory_benchmark.json"),
) -> Path:
    compute_result = run_inventory_benchmark(
        sku_count=2_000,
        period_days=90,
    )

    db_result = run_inventory_db_benchmark(
        sku_count=2_000,
    )

    manifest = {
        "benchmark_id": "D07-BE-05",
        "verification_level": ("SYNTHETIC_BASELINE"),
        "workload": {
            "sku_count": 2_000,
            "period_days": 90,
            "real_business_data_used": False,
        },
        "compute": asdict(compute_result),
        "database": asdict(db_result),
        "safety": {
            "external_write_count": 0,
            "production_schedule_enabled": False,
            "contains_pii": False,
            "contains_secret": False,
        },
        "notes": [
            ("Compute latency is an in-process synthetic calculation baseline."),
            (
                "Database measurement uses "
                "SQLite in-memory and must not "
                "be presented as PostgreSQL "
                "production performance."
            ),
        ],
    }

    output_path = Path(path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    return output_path
