"""C17 projection contracts with in-memory PostgreSQL and Neo4j fakes."""

import re
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from backend.app.core.config import Settings
from backend.app.models_v2.catalog import ProductV2, ProductVariantV2
from backend.app.models_v2.operations import (
    IncomingShipmentV2,
    InventorySnapshotV2,
    ReservationV2,
    TaskIncomingDependencyV2,
    TaskV2,
)
from backend.app.services.c15_synthetic_seed import TENANT_ID, generate_seed
from backend.app.services.c17_neo4j_projection import (
    CONSTRAINTS,
    LABELS,
    NODE_FIELDS,
    PRODUCT_LOOKUP,
    PROJECTION_VERSION,
    RELATIONSHIP_TYPES,
    PgSnapshot,
    build_projection_plan,
    graph_key,
    load_pg_snapshot,
    lookup_product_graph,
    project_c17,
    run_c17_projection,
)

HERO_PRODUCT = UUID("dd5e08e7-a9a7-5a91-a34b-e9e0bf3b9e09")
HERO_SKU = UUID("df91f665-806e-5e21-a8e0-ac865542ef71")
HERO_INCOMING_IDS = {
    UUID("d95b3071-4683-5944-97a8-c15aa4073fb1"),
    UUID("5fb54b57-82fe-5ca7-9438-e0947095e030"),
}


def changed(row, **updates):
    return SimpleNamespace(**(vars(row) | updates))


def hero_snapshot():
    bundle = generate_seed()
    product = next(row for row in bundle.products if row["id"] == HERO_PRODUCT)
    assert product["product_name"] == "아침 시장"
    assert product["product_code"] == "DEMO-P-0009"
    sku = next(row for row in bundle.variants if row["id"] == HERO_SKU)
    assert sku["variant_code"] == "DEMO-SKU-0009-01"
    common = dict(tenant_id=TENANT_ID, product_id=HERO_PRODUCT, product_variant_id=HERO_SKU)
    inventory = SimpleNamespace(
        id=UUID("802a2965-f922-5837-be9a-d15408926ce5"),
        on_hand_quantity=1,
        reserved_quantity=0,
        data_as_of=None,
        source_system="SYNTHETIC_DEMO",
        data_quality_status="CONFIRMED",
        **common,
    )
    incoming_ids = (
        UUID("d95b3071-4683-5944-97a8-c15aa4073fb1"),
        UUID("5fb54b57-82fe-5ca7-9438-e0947095e030"),
    )
    incoming = tuple(
        SimpleNamespace(
            id=entity_id,
            expected_quantity=1,
            expected_arrival_at=None,
            incoming_status="CONFIRMED",
            confidence_status="CONFIRMED",
            source_system="SYNTHETIC_DEMO",
            external_reference=f"DEMO-INCOMING-HERO-{index:03d}",
            **common,
        )
        for index, entity_id in enumerate(incoming_ids, 1)
    )
    reservation = SimpleNamespace(
        id=UUID("635ffd14-0cfa-5033-bb45-04a58eec0271"),
        required_quantity=5,
        secured_quantity=1,
        promised_date=None,
        reservation_status="OPEN",
        source_quality_status="CONFIRMED",
        order_id=uuid4(),
        **common,
    )
    task = SimpleNamespace(
        id=UUID("bd436abf-81ad-556c-bf4e-8d363d5d0273"),
        tenant_id=TENANT_ID,
        product_id=HERO_PRODUCT,
        task_type="RESERVATION_SHORTAGE",
        task_title="Resolve shortage",
        task_status="PROPOSED",
        priority=80,
        due_at=None,
        source_reason="Shortage of two",
    )
    dependency = SimpleNamespace(
        tenant_id=TENANT_ID,
        incoming_shipment_id=incoming_ids[0],
        task_id=task.id,
    )
    return PgSnapshot(
        products=tuple(SimpleNamespace(**row) for row in bundle.products),
        skus=tuple(SimpleNamespace(**row) for row in bundle.variants),
        inventory=(inventory,),
        incoming=incoming,
        reservations=(reservation,),
        tasks=(task,),
        task_incoming_dependencies=(dependency,),
    )

class FakePgResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakePgSession:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.models = {
            ProductV2: snapshot.products,
            ProductVariantV2: snapshot.skus,
            InventorySnapshotV2: snapshot.inventory,
            IncomingShipmentV2: snapshot.incoming,
            ReservationV2: snapshot.reservations,
            TaskV2: snapshot.tasks,
            TaskIncomingDependencyV2: snapshot.task_incoming_dependencies,
        }
        self.queries = []

    def scalars(self, statement):
        self.queries.append(str(statement))
        model = statement.column_descriptions[0]["entity"]
        return FakePgResult(self.models[model])


class FakeGraphResult:
    def __init__(self, row=None, **counts):
        self.row = row
        self.counts = SimpleNamespace(**counts)

    def single(self):
        return self.row

    def consume(self):
        return SimpleNamespace(counters=self.counts)

    def __iter__(self):
        return iter([] if self.row is None else [self.row])


class FakeGraphSession:
    def __init__(self):
        self.nodes = {}
        self.edges = set()
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute_write(self, callback, *args):
        return callback(self, *args)

    def execute_read(self, callback, *args):
        return callback(self, *args)

    def run(self, cypher, **params):
        self.calls.append((cypher, params))
        if cypher.startswith("CREATE CONSTRAINT"):
            return FakeGraphResult()
        if cypher.startswith("MERGE (n:"):
            label = re.search(r"MERGE \(n:(\w+)", cypher).group(1)
            key = (label, params["graph_key"])
            created = int(key not in self.nodes)
            self.nodes[key] = params["properties"].copy()
            return FakeGraphResult(nodes_created=created, properties_set=len(params["properties"]))
        if "expected_source_keys" in params:
            source, rel_type, target = re.search(
                r"MATCH \(s:(\w+)\)-\[r:(\w+)\]->\(t:(\w+)", cypher
            ).groups()
            stale = {
                e
                for e in self.edges
                if e[0] == source
                and e[1] == rel_type
                and e[2] == target
                and e[4] == params["target_key"]
                and e[3] not in params["expected_source_keys"]
            }
            self.edges -= stale
            return FakeGraphResult()
        if "RETURN count(r) AS matched" in cypher:
            source, rel_type, target = re.search(
                r"MATCH \(s:(\w+).*\(t:(\w+).*MERGE \(s\)-\[r:(\w+)\]", cypher
            ).groups()
            source, target, rel_type = source, rel_type, target
            if (source, params["source_key"]) not in self.nodes or (
                target,
                params["target_key"],
            ) not in self.nodes:
                return FakeGraphResult(row={"matched": 0})
            key = (source, rel_type, target, params["source_key"], params["target_key"])
            created = int(key not in self.edges)
            self.edges.add(key)
            return FakeGraphResult(row={"matched": 1}, relationships_created=created)
        if "RETURN count(n) AS count" in cypher:
            label = re.search(r"MATCH \(n:(\w+)", cypher).group(1)
            return FakeGraphResult(
                row={
                    "count": sum(
                        props["tenant_id"] == params["tenant_id"]
                        and props["projection_version"] == params["version"]
                        for (node_label, _), props in self.nodes.items()
                        if node_label == label
                    )
                }
            )
        if "RETURN count(r) AS count" in cypher:
            rel_type = re.search(r"-\[r:(\w+)\]", cypher).group(1)
            return FakeGraphResult(row={"count": sum(e[1] == rel_type for e in self.edges)})
        if cypher == PRODUCT_LOOKUP:
            incoming = [
                props
                for (label, _), props in self.nodes.items()
                if label == "Incoming" and props["product_id"] == str(HERO_PRODUCT)
            ]
            return FakeGraphResult(row={"incoming": incoming})
        raise AssertionError(cypher)


class FakeDriver:
    def __init__(self):
        self.graph = FakeGraphSession()

    def session(self, *, database):
        assert database == "neo4j"
        return self.graph


def test_c17_plan_labels_edges_hero_and_sensitive_exclusions():
    snapshot = hero_snapshot()
    plan = build_projection_plan(snapshot)
    assert {node.label for node in plan.nodes} == set(LABELS)
    assert {edge.rel_type for edge in plan.edges} == set(RELATIONSHIP_TYPES)
    assert set(RELATIONSHIP_TYPES) == {
        "HAS_SKU",
        "HAS_INVENTORY",
        "HAS_INCOMING",
        "HAS_RESERVATION",
        "HAS_TASK",
        "AFFECTS_TASK",
    }
    assert len([n for n in plan.nodes if n.label == "Incoming"]) == 2
    incoming_keys = {n.graph_key for n in plan.nodes if n.label == "Incoming"}
    assert incoming_keys == {graph_key(TENANT_ID, entity_id) for entity_id in HERO_INCOMING_IDS}
    incoming_by_id = {
        n.properties["id"]: n.properties["external_reference"]
        for n in plan.nodes
        if n.label == "Incoming"
    }
    assert incoming_by_id == {
        "d95b3071-4683-5944-97a8-c15aa4073fb1": "DEMO-INCOMING-HERO-001",
        "5fb54b57-82fe-5ca7-9438-e0947095e030": "DEMO-INCOMING-HERO-002",
    }
    assert graph_key(TENANT_ID, HERO_PRODUCT) != graph_key(uuid4(), HERO_PRODUCT)
    assert all(node.properties["projection_version"] == PROJECTION_VERSION for node in plan.nodes)
    assert all("order_id" not in node.properties for node in plan.nodes)
    assert "order_id" not in NODE_FIELDS["Reservation"]
    assert "cafe24_product_no" not in NODE_FIELDS["Product"]
    assert "custom_product_code" not in NODE_FIELDS["Product"]
    assert "barcode" not in NODE_FIELDS["SKU"]
    assert not any(node.label in {"Order", "OrderItem", "Customer"} for node in plan.nodes)
    assert not any(
        edge.source_label == "SKU" and edge.target_label == "Task" for edge in plan.edges
    )
    assert len([e for e in plan.edges if e.rel_type == "HAS_INCOMING"]) == 4
    assert len(CONSTRAINTS) == 6 and all(
        "IF NOT EXISTS" in c and "IS UNIQUE" in c for c in CONSTRAINTS
    )


def test_c17_null_sku_and_broken_fk_fail_closed():
    snapshot = hero_snapshot()
    without_sku = changed(snapshot.inventory[0], product_variant_id=None)
    plan = build_projection_plan(replace(snapshot, inventory=(without_sku,)))
    inv_key = graph_key(TENANT_ID, without_sku.id)
    assert [e.source_label for e in plan.edges if e.target_key == inv_key] == ["Product"]
    broken = changed(snapshot.inventory[0], product_variant_id=uuid4())
    with pytest.raises(RuntimeError, match="SKU_FK"):
        build_projection_plan(replace(snapshot, inventory=(broken,)))
    with pytest.raises(ValueError, match="TENANT"):
        build_projection_plan(snapshot, tenant_id=uuid4())


def test_c17_fake_driver_projection_idempotence_update_and_read():
    snapshot = hero_snapshot()
    pg = FakePgSession(snapshot)
    driver = FakeDriver()
    first = project_c17(pg, driver)
    second = project_c17(pg, driver)
    assert first["node_counts"] == {
        "Product": 150,
        "SKU": 176,
        "Inventory": 1,
        "Incoming": 2,
        "Reservation": 1,
        "Task": 1,
    }
    assert first["relationship_counts"] == {
        "HAS_SKU": 176,
        "HAS_INVENTORY": 2,
        "HAS_INCOMING": 4,
        "HAS_RESERVATION": 2,
        "HAS_TASK": 1,
        "AFFECTS_TASK": 1,
    }
    assert first["nodes_created"] == 331
    assert first["relationships_created"] == 186
    assert second["nodes_created"] == 0 and second["relationships_created"] == 0
    assert second["projection_version"] == PROJECTION_VERSION
    assert len(pg.queries) == 14
    assert all("tenant_id" in query for query in pg.queries)
    changed_inventory = changed(snapshot.inventory[0], product_variant_id=None, on_hand_quantity=3)
    renamed_hero = changed(snapshot.products[8], product_name="아침 시장 특별판")
    pg.snapshot = replace(
        snapshot,
        products=(*snapshot.products[:8], renamed_hero, *snapshot.products[9:]),
        inventory=(changed_inventory,),
    )
    pg.models[ProductV2] = pg.snapshot.products
    pg.models[InventorySnapshotV2] = pg.snapshot.inventory
    third = project_c17(pg, driver)
    assert third["nodes_created"] == 0
    assert driver.graph.nodes[("Product", graph_key(TENANT_ID, HERO_PRODUCT))][
        "product_name"
    ] == "아침 시장 특별판"
    assert third["relationship_counts"]["HAS_INVENTORY"] == 1
    assert (
        driver.graph.nodes[("Inventory", graph_key(TENANT_ID, changed_inventory.id))][
            "on_hand_quantity"
        ]
        == 3
    )
    hit = lookup_product_graph(driver, tenant_id=TENANT_ID, product_id=HERO_PRODUCT)
    assert {row["id"] for row in hit[0]["incoming"]} == {str(x) for x in HERO_INCOMING_IDS}
    lookup_sql = driver.graph.calls[-1][0]
    assert "LIMIT $limit" in lookup_sql and "HAS_SKU" in lookup_sql
    assert not any(word in lookup_sql for word in ("MERGE", "CREATE", "DELETE", "SET "))
    with pytest.raises(ValueError, match="PRODUCT_NOT_C15"):
        lookup_product_graph(driver, tenant_id=TENANT_ID, product_id=uuid4())


def test_c17_pg_source_catalog_identity_guard():
    snapshot = hero_snapshot()
    pg = FakePgSession(snapshot)
    result = load_pg_snapshot(pg)
    assert len(result.products) == 150 and len(result.skus) == 176
    pg.models[ProductV2] = snapshot.products[:-1]
    with pytest.raises(RuntimeError, match="C15_CATALOG_MISMATCH"):
        load_pg_snapshot(pg)


def test_c17_settings_fail_closed_and_entrypoint_uses_separate_clients(monkeypatch):
    import neo4j

    import backend.app.services.c17_neo4j_projection as service

    class FakeEngine:
        def __init__(self):
            self.disposed = False

        def dispose(self):
            self.disposed = True

    class FakePgContext:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    class FakeNeoDriver:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    engine = FakeEngine()
    driver = FakeNeoDriver()
    calls = []
    monkeypatch.setattr(service, "build_v2_engine", lambda url: (calls.append("pg"), engine)[1])
    monkeypatch.setattr(service, "Session", lambda _: FakePgContext())
    monkeypatch.setattr(
        neo4j.GraphDatabase, "driver", lambda uri, auth: (calls.append("neo4j"), driver)[1]
    )
    monkeypatch.setattr(
        service, "project_c17", lambda pg_session, neo4j_driver, tenant_id: {"projected": True}
    )
    base = dict(
        _env_file=None,
        environment="DEMO",
        v2_tenant_id=TENANT_ID,
        postgres_v2_url="postgresql+psycopg://demo:secret@localhost:55433/commerce_ops_db",
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="test-only-secret",
    )
    assert run_c17_projection(settings=Settings(**base)) == {"projected": True}
    assert calls == ["pg", "neo4j"] and engine.disposed and driver.closed
    for overrides in (
        {"environment": "LOCAL"},
        {"postgres_v2_url": "postgresql+psycopg://demo:secret@localhost:55433/commerce_ops"},
        {"neo4j_uri": "bolt://remote.example:7687"},
    ):
        with pytest.raises(RuntimeError, match="C17_DEMO_CONFIGURATION_REQUIRED"):
            run_c17_projection(settings=Settings(**(base | overrides)))
    assert calls == ["pg", "neo4j"]

def test_c17_task_incoming_dependency_composite_key_duplicate_fails_closed():
    snapshot = hero_snapshot()
    dependency = snapshot.task_incoming_dependencies[0]

    duplicated = replace(
        snapshot,
        task_incoming_dependencies=(
            dependency,
            dependency,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="C17_DUPLICATE_TASK_INCOMING_DEPENDENCY",
    ):
        build_projection_plan(duplicated)