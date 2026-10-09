from uuid import uuid4

from backend.app.services.c15_synthetic_seed import TENANT_ID, generate_seed
from backend.app.services.c17_graph_runtime import analyze_product_graph


HERO_PRODUCT = next(
    row["id"]
    for row in generate_seed().products
    if row["product_code"] == "DEMO-P-0009"
)


class FakeDriver:
    pass


def test_graph_runtime_answer(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.c17_graph_runtime.lookup_product_graph",
        lambda *args, **kwargs: [
            {
                "product": {
                    "id": str(HERO_PRODUCT),
                }
            }
        ],
    )

    monkeypatch.setattr(
        "backend.app.services.c17_graph_runtime.lookup_product_impact_paths",
        lambda *args, **kwargs: [
            {
                "product": {
                    "id": str(HERO_PRODUCT),
                },
                "sku": {
                    "id": "sku-1",
                },
                "incoming": {
                    "id": "incoming-1",
                },
                "task": {
                    "id": "task-1",
                },
            }
        ],
    )

    result = analyze_product_graph(
        FakeDriver(),
        tenant_id=TENANT_ID,
        product_id=HERO_PRODUCT,
    )

    assert result.status == "ANSWER"
    assert len(result.evidence) == 1

    evidence = result.evidence[0]

    assert evidence.hop_count == 3
    assert evidence.path == (
        str(HERO_PRODUCT),
        "sku-1",
        "incoming-1",
        "task-1",
    )
    assert evidence.relation_types == (
        "HAS_SKU",
        "HAS_INCOMING",
        "AFFECTS_TASK",
    )


def test_graph_runtime_no_edge(monkeypatch):
    monkeypatch.setattr(
        "backend.app.services.c17_graph_runtime.lookup_product_graph",
        lambda *args, **kwargs: [
            {
                "product": {
                    "id": str(HERO_PRODUCT),
                }
            }
        ],
    )

    monkeypatch.setattr(
        "backend.app.services.c17_graph_runtime.lookup_product_impact_paths",
        lambda *args, **kwargs: [],
    )

    result = analyze_product_graph(
        FakeDriver(),
        tenant_id=TENANT_ID,
        product_id=HERO_PRODUCT,
    )

    assert result.status == "NO_EDGE"
    assert result.evidence == ()


def test_graph_runtime_invalid_product_holds():
    result = analyze_product_graph(
        FakeDriver(),
        tenant_id=TENANT_ID,
        product_id=uuid4(),
    )

    assert result.status == "HOLD"
    assert result.evidence == ()


def test_graph_runtime_graph_failure_holds(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("neo4j unavailable")

    monkeypatch.setattr(
        "backend.app.services.c17_graph_runtime.lookup_product_graph",
        fail,
    )

    result = analyze_product_graph(
        FakeDriver(),
        tenant_id=TENANT_ID,
        product_id=HERO_PRODUCT,
    )

    assert result.status == "HOLD"
    assert result.evidence == ()