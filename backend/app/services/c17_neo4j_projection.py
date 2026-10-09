"""Tenant-scoped Neo4j projection of approved C15 synthetic relationships.

PostgreSQL remains authoritative. No database connection is opened on import.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session

from backend.app.core.config import Environment, Settings
from backend.app.db.session_v2 import build_v2_engine
from backend.app.models_v2.catalog import ProductV2, ProductVariantV2
from backend.app.models_v2.operations import (
    IncomingShipmentV2,
    InventorySnapshotV2,
    ReservationV2,
    TaskIncomingDependencyV2,
    TaskV2,
)
from backend.app.services.c15_synthetic_seed import TENANT_ID, generate_seed

PROJECTION_VERSION = "demo-c17-20261006-v1"
LABELS = ("Product", "SKU", "Inventory", "Incoming", "Reservation", "Task")
RELATIONSHIP_TYPES = (
    "HAS_SKU",
    "HAS_INVENTORY",
    "HAS_INCOMING",
    "HAS_RESERVATION",
    "HAS_TASK",
    "AFFECTS_TASK",
)
EDGE_SPECS = (
    ("Product", "HAS_SKU", "SKU"),
    ("Product", "HAS_INVENTORY", "Inventory"),
    ("SKU", "HAS_INVENTORY", "Inventory"),
    ("Product", "HAS_INCOMING", "Incoming"),
    ("SKU", "HAS_INCOMING", "Incoming"),
    ("Product", "HAS_RESERVATION", "Reservation"),
    ("SKU", "HAS_RESERVATION", "Reservation"),
    ("Product", "HAS_TASK", "Task"),
    ("Incoming", "AFFECTS_TASK", "Task"),
)

CONSTRAINTS = tuple(
    f"CREATE CONSTRAINT c17_{label.lower()}_graph_key IF NOT EXISTS "
    f"FOR (n:{label}) REQUIRE n.graph_key IS UNIQUE"
    for label in LABELS
)

# Fixed Cypher only. The caller supplies an identity and limit, never a query string.
PRODUCT_LOOKUP = """

MATCH (p:Product {graph_key: $product_key, tenant_id: $tenant_id})
RETURN p{.*} AS product,
       [(p)-[:HAS_SKU]->(s:SKU) | s{.*}] AS skus,
       [(p)-[:HAS_INVENTORY]->(i:Inventory) | i{.*}] AS inventory,
       [(p)-[:HAS_INCOMING]->(i:Incoming) | i{.*}] AS incoming,
       [(p)-[:HAS_RESERVATION]->(r:Reservation) | r{.*}] AS reservations,
       [(p)-[:HAS_TASK]->(t:Task) | t{.*}] AS tasks,
       [(p)-[:HAS_SKU]->(:SKU)-[:HAS_INVENTORY]->(i:Inventory) | i{.*}]
           AS sku_inventory,
       [(p)-[:HAS_SKU]->(:SKU)-[:HAS_INCOMING]->(i:Incoming) | i{.*}]
           AS sku_incoming,
       [(p)-[:HAS_SKU]->(:SKU)-[:HAS_RESERVATION]->(r:Reservation) | r{.*}]
           AS sku_reservations
LIMIT $limit
"""
PRODUCT_IMPACT_PATH_LOOKUP = """
MATCH
    (p:Product {
        graph_key: $product_key,
        tenant_id: $tenant_id
    })
    -[:HAS_SKU]->
    (s:SKU)
    -[:HAS_INCOMING]->
    (i:Incoming)
    -[:AFFECTS_TASK]->
    (t:Task)
RETURN
    p{.*} AS product,
    s{.*} AS sku,
    i{.*} AS incoming,
    t{.*} AS task
LIMIT $limit
"""

def lookup_product_impact_paths(
    neo4j_driver,
    *,
    tenant_id: UUID,
    product_id: UUID,
    limit: int = 10,
) -> list[dict]:
    """Read-only bounded Product→SKU→Incoming→Task lookup."""
    _require_tenant(tenant_id)

    allowed = {
        row["id"]
        for row in generate_seed().products
    }

    if product_id not in allowed:
        raise ValueError(
            "C17_PRODUCT_NOT_C15_DEMO"
        )

    if (
        type(limit) is not int
        or not 1 <= limit <= 10
    ):
        raise ValueError(
            "C17_LIMIT_INVALID"
        )

    with neo4j_driver.session(
        database="neo4j"
    ) as graph_session:
        return [
            dict(row)
            for row in graph_session.run(
                PRODUCT_IMPACT_PATH_LOOKUP,
                product_key=graph_key(
                    tenant_id,
                    product_id,
                ),
                tenant_id=str(tenant_id),
                limit=limit,
            )
        ]
@dataclass(frozen=True)
class PgSnapshot:
    products: tuple[Any, ...]
    skus: tuple[Any, ...]
    inventory: tuple[Any, ...]
    incoming: tuple[Any, ...]
    reservations: tuple[Any, ...]
    tasks: tuple[Any, ...]
    task_incoming_dependencies: tuple[Any, ...]


@dataclass(frozen=True)
class NodeRow:
    label: str
    graph_key: str
    properties: dict[str, Any]


@dataclass(frozen=True)
class EdgeRow:
    source_label: str
    rel_type: str
    target_label: str
    source_key: str
    target_key: str


@dataclass(frozen=True)
class ProjectionPlan:
    nodes: tuple[NodeRow, ...]
    edges: tuple[EdgeRow, ...]


def graph_key(tenant_id: UUID, entity_id: UUID) -> str:
    return f"{tenant_id}:{entity_id}"


def _require_tenant(tenant_id: UUID) -> None:
    if tenant_id != TENANT_ID:
        raise ValueError("C17_TENANT_NOT_C15_DEMO")


def _scalar(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _node(label: str, row: Any, tenant_id: UUID, fields: tuple[str, ...]) -> NodeRow:
    properties = {field: _scalar(getattr(row, field)) for field in fields}
    key = graph_key(tenant_id, row.id)
    properties.update(
        graph_key=key,
        id=str(row.id),
        tenant_id=str(tenant_id),
        projection_version=PROJECTION_VERSION,
    )
    return NodeRow(label, key, properties)


NODE_FIELDS = {
    "Product": (
        "product_name",
        "product_code",
        "sale_price",
        "display_status",
        "selling_status",
        "sold_out",
        "operational",
        "source_as_of",
    ),
    "SKU": ("product_id", "variant_code", "option_name", "variant_status"),
    "Inventory": (
        "product_id",
        "product_variant_id",
        "on_hand_quantity",
        "reserved_quantity",
        "data_as_of",
        "source_system",
        "data_quality_status",
    ),
    "Incoming": (
        "product_id",
        "product_variant_id",
        "expected_quantity",
        "expected_arrival_at",
        "incoming_status",
        "confidence_status",
        "source_system",
        "external_reference",
    ),
    "Reservation": (
        "product_id",
        "product_variant_id",
        "required_quantity",
        "secured_quantity",
        "promised_date",
        "reservation_status",
        "source_quality_status",
    ),
    "Task": (
        "product_id",
        "task_type",
        "task_title",
        "task_status",
        "priority",
        "due_at",
        "source_reason",
    ),
}


def load_pg_snapshot(pg_session: Session, *, tenant_id: UUID = TENANT_ID) -> PgSnapshot:
    """Read only rows linked to the deterministic C15 catalog in one PG session."""
    _require_tenant(tenant_id)
    bundle = generate_seed()
    ids = [row["id"] for row in bundle.products]

    def rows(model, product_column):
        return tuple(
            pg_session.scalars(
                select(model).where(model.tenant_id == tenant_id, product_column.in_(ids))
            ).all()
        )

    products = tuple(
        pg_session.scalars(
            select(ProductV2).where(ProductV2.tenant_id == tenant_id, ProductV2.id.in_(ids))
        ).all()
    )
    skus = rows(ProductVariantV2, ProductVariantV2.product_id)
    expected_products = {row["id"]: row["product_code"] for row in bundle.products}
    expected_skus = {row["id"]: (row["product_id"], row["variant_code"]) for row in bundle.variants}
    if (
        len(products) != len(expected_products)
        or {p.id: p.product_code for p in products} != expected_products
        or len(skus) != len(expected_skus)
        or {s.id: (s.product_id, s.variant_code) for s in skus} != expected_skus
    ):
        raise RuntimeError("C17_C15_CATALOG_MISMATCH")
    inventory = rows(
        InventorySnapshotV2,
        InventorySnapshotV2.product_id,
    )
    incoming = rows(
        IncomingShipmentV2,
        IncomingShipmentV2.product_id,
    )
    reservations = rows(
        ReservationV2,
        ReservationV2.product_id,
    )
    tasks = rows(
        TaskV2,
        TaskV2.product_id,
    )

    incoming_ids = [row.id for row in incoming]
    task_ids = [row.id for row in tasks]

    dependencies = tuple(
        pg_session.scalars(
            select(TaskIncomingDependencyV2).where(
                TaskIncomingDependencyV2.tenant_id
                == tenant_id,
                TaskIncomingDependencyV2.incoming_shipment_id.in_(
                    incoming_ids
                ),
                TaskIncomingDependencyV2.task_id.in_(
                    task_ids
                ),
            )
        ).all()
    )
    return PgSnapshot(
        products=products,
        skus=skus,
        inventory=inventory,
        incoming=incoming,
        reservations=reservations,
        tasks=tasks,
        task_incoming_dependencies=dependencies,
    )


def build_projection_plan(snapshot: PgSnapshot, *, tenant_id: UUID = TENANT_ID) -> ProjectionPlan:
    """Validate FKs before creating any graph writes."""
    _require_tenant(tenant_id)
    products = {row.id: row for row in snapshot.products}
    skus = {row.id: row for row in snapshot.skus}
    incoming = {
        row.id: row
        for row in snapshot.incoming
    }
    tasks = {
        row.id: row
        for row in snapshot.tasks
    }
    if len(products) != len(snapshot.products) or len(skus) != len(snapshot.skus):
        raise RuntimeError("C17_DUPLICATE_SOURCE_ID")
    for group in (
        snapshot.products,
        snapshot.skus,
        snapshot.inventory,
        snapshot.incoming,
        snapshot.reservations,
        snapshot.tasks,
    ):
        if len({row.id for row in group}) != len(group):
            raise RuntimeError("C17_DUPLICATE_SOURCE_ID")
        if any(row.tenant_id != tenant_id for row in group):
            raise RuntimeError("C17_SOURCE_TENANT_MISMATCH")
    dependency_keys = {
        (
            row.tenant_id,
            row.task_id,
            row.incoming_shipment_id,
        )
        for row in snapshot.task_incoming_dependencies
    }

    if len(dependency_keys) != len(
        snapshot.task_incoming_dependencies
    ):
        raise RuntimeError(
            "C17_DUPLICATE_TASK_INCOMING_DEPENDENCY"
        )

    if any(
        row.tenant_id != tenant_id
        for row in snapshot.task_incoming_dependencies
    ):
        raise RuntimeError(
            "C17_SOURCE_TENANT_MISMATCH"
        )
    nodes: list[NodeRow] = []
    edges: list[EdgeRow] = []
    groups = (
        ("Product", snapshot.products),
        ("SKU", snapshot.skus),
        ("Inventory", snapshot.inventory),
        ("Incoming", snapshot.incoming),
        ("Reservation", snapshot.reservations),
        ("Task", snapshot.tasks),
    )
    for label, group in groups:
        nodes.extend(_node(label, row, tenant_id, NODE_FIELDS[label]) for row in group)

    def edge(
        source_label: str, rel_type: str, target_label: str, source_id: UUID, target_id: UUID
    ) -> None:
        edges.append(
            EdgeRow(
                source_label,
                rel_type,
                target_label,
                graph_key(tenant_id, source_id),
                graph_key(tenant_id, target_id),
            )
        )

    for dependency in (
        snapshot.task_incoming_dependencies
    ):
        if (
            dependency.incoming_shipment_id
            not in incoming
            or dependency.task_id not in tasks
        ):
            raise RuntimeError(
                "C17_TASK_INCOMING_FK_MISSING"
            )

        edge(
            "Incoming",
            "AFFECTS_TASK",
            "Task",
            dependency.incoming_shipment_id,
            dependency.task_id,
        )

    for sku in snapshot.skus:
        if sku.product_id not in products:
            raise RuntimeError("C17_PRODUCT_FK_MISSING")
        edge("Product", "HAS_SKU", "SKU", sku.product_id, sku.id)
    for label, group, rel_type in (
        ("Inventory", snapshot.inventory, "HAS_INVENTORY"),
        ("Incoming", snapshot.incoming, "HAS_INCOMING"),
        ("Reservation", snapshot.reservations, "HAS_RESERVATION"),
        ("Task", snapshot.tasks, "HAS_TASK"),
    ):
        for row in group:
            if row.product_id not in products:
                raise RuntimeError("C17_PRODUCT_FK_MISSING")
            edge("Product", rel_type, label, row.product_id, row.id)
            if label != "Task" and row.product_variant_id is not None:
                sku = skus.get(row.product_variant_id)
                if sku is None or sku.product_id != row.product_id:
                    raise RuntimeError("C17_SKU_FK_MISSING_OR_CROSS_PRODUCT")
                edge("SKU", rel_type, label, sku.id, row.id)
    assert {e.rel_type for e in edges} <= set(RELATIONSHIP_TYPES)
    return ProjectionPlan(tuple(nodes), tuple(edges))


def _node_query(label: str) -> str:
    return f"MERGE (n:{label} {{graph_key: $graph_key}}) SET n = $properties"


def _edge_query(spec: tuple[str, str, str]) -> str:
    source, rel_type, target = spec
    return (
        f"MATCH (s:{source} {{graph_key: $source_key}}), "
        f"(t:{target} {{graph_key: $target_key}}) "
        f"MERGE (s)-[r:{rel_type}]->(t) RETURN count(r) AS matched"
    )


def _cleanup_query(spec: tuple[str, str, str]) -> str:
    source, rel_type, target = spec
    return (
        f"MATCH (s:{source})-[r:{rel_type}]->"
        f"(t:{target} {{graph_key: $target_key}}) "
        "WHERE NOT s.graph_key IN $expected_source_keys DELETE r"
    )


def _write_plan(tx, plan: ProjectionPlan) -> dict[str, int]:
    stats = {"nodes_created": 0, "relationships_created": 0, "properties_set": 0}

    def collect(result) -> None:
        counters = result.consume().counters
        for key in stats:
            stats[key] += getattr(counters, key, 0)

    for node in plan.nodes:
        collect(
            tx.run(_node_query(node.label), graph_key=node.graph_key, properties=node.properties)
        )
    expected: dict[tuple[str, str, str, str], list[str]] = {}
    for edge in plan.edges:
        key = (edge.source_label, edge.rel_type, edge.target_label, edge.target_key)
        expected.setdefault(key, []).append(edge.source_key)
    for spec in EDGE_SPECS:
        for node in plan.nodes:
            if node.label == spec[2]:
                keys = expected.get((*spec, node.graph_key), [])
                collect(
                    tx.run(
                        _cleanup_query(spec), target_key=node.graph_key, expected_source_keys=keys
                    )
                )
    for edge in plan.edges:
        result = tx.run(
            _edge_query((edge.source_label, edge.rel_type, edge.target_label)),
            source_key=edge.source_key,
            target_key=edge.target_key,
        )
        record = result.single()
        if record is None or record["matched"] != 1:
            raise RuntimeError("C17_GRAPH_EDGE_ENDPOINT_MISSING")
        collect(result)
    return stats


def _read_counts(tx, tenant_id: UUID) -> tuple[dict[str, int], dict[str, int]]:
    params = dict(tenant_id=str(tenant_id), version=PROJECTION_VERSION)
    node_counts = {}
    for label in LABELS:
        result = tx.run(
            f"MATCH (n:{label} {{tenant_id: $tenant_id, projection_version: $version}}) "
            "RETURN count(n) AS count",
            **params,
        )
        node_counts[label] = result.single()["count"]
    rel_counts = {}
    for rel_type in RELATIONSHIP_TYPES:
        result = tx.run(
            "MATCH (a {tenant_id: $tenant_id, projection_version: $version})"
            f"-[r:{rel_type}]->"
            "(b {tenant_id: $tenant_id, projection_version: $version}) "
            "RETURN count(r) AS count",
            **params,
        )
        rel_counts[rel_type] = result.single()["count"]
    return node_counts, rel_counts


def project_c17(pg_session: Session, neo4j_driver, *, tenant_id: UUID = TENANT_ID) -> dict:
    """Read PG, validate the full plan, then write a single Neo4j transaction."""
    _require_tenant(tenant_id)
    plan = build_projection_plan(
        load_pg_snapshot(pg_session, tenant_id=tenant_id), tenant_id=tenant_id
    )
    with neo4j_driver.session(database="neo4j") as graph_session:
        for constraint in CONSTRAINTS:
            graph_session.run(constraint).consume()
        changes = graph_session.execute_write(_write_plan, plan)
        node_counts, relationship_counts = graph_session.execute_read(_read_counts, tenant_id)
    return dict(
        projection_version=PROJECTION_VERSION,
        tenant_id=str(tenant_id),
        node_counts=node_counts,
        relationship_counts=relationship_counts,
        **changes,
    )


def lookup_product_graph(
    neo4j_driver, *, tenant_id: UUID, product_id: UUID, limit: int = 1
) -> list[dict]:
    """Read-only, bounded product/SKU/operations neighborhood lookup."""
    _require_tenant(tenant_id)
    allowed = {row["id"] for row in generate_seed().products}
    if product_id not in allowed:
        raise ValueError("C17_PRODUCT_NOT_C15_DEMO")
    if type(limit) is not int or not 1 <= limit <= 10:
        raise ValueError("C17_LIMIT_INVALID")
    with neo4j_driver.session(database="neo4j") as graph_session:
        return [
            dict(row)
            for row in graph_session.run(
                PRODUCT_LOOKUP,
                product_key=graph_key(tenant_id, product_id),
                tenant_id=str(tenant_id),
                limit=limit,
            )
        ]


def run_c17_projection(*, settings: Settings | None = None) -> dict:
    """Explicit CMD entrypoint; importing this module never runs the projection."""
    from neo4j import GraphDatabase

    cfg = settings or Settings()
    try:
        pg_url = make_url(cfg.postgres_v2_url) if cfg.postgres_v2_url else None
    except (ArgumentError, ValueError):
        pg_url = None
    if (
        cfg.environment != Environment.DEMO
        or cfg.v2_tenant_id != TENANT_ID
        or pg_url is None
        or pg_url.database != "commerce_ops_db"
        or pg_url.host != "localhost"
        or pg_url.port != 55433
        or cfg.neo4j_uri != "bolt://localhost:7687"
        or not cfg.neo4j_user
        or cfg.neo4j_password is None
        or not cfg.neo4j_password.get_secret_value()
    ):
        raise RuntimeError("C17_DEMO_CONFIGURATION_REQUIRED")
    engine = build_v2_engine(cfg.postgres_v2_url)
    driver = None
    try:
        driver = GraphDatabase.driver(
            cfg.neo4j_uri, auth=(cfg.neo4j_user, cfg.neo4j_password.get_secret_value())
        )
        with Session(engine) as pg_session:
            return project_c17(pg_session, driver, tenant_id=TENANT_ID)
    finally:
        if driver is not None:
            driver.close()
        engine.dispose()
