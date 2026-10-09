from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from backend.app.services.c17_neo4j_projection import (
    PROJECTION_VERSION,
    lookup_product_graph,
    lookup_product_impact_paths,
)


GraphStatus = Literal[
    "ANSWER",
    "NO_EDGE",
    "HOLD",
]


@dataclass(frozen=True)
class GraphRelationEvidence:
    evidence_id: str
    hop_count: int
    path: tuple[str, ...]
    relation_types: tuple[str, ...]
    projection_version: str


@dataclass(frozen=True)
class GraphRuntimeResult:
    status: GraphStatus
    conclusion: str
    key_facts: tuple[str, ...]
    evidence: tuple[
        GraphRelationEvidence, ...
    ]


def analyze_product_graph(
    neo4j_driver,
    *,
    tenant_id: UUID,
    product_id: UUID,
) -> GraphRuntimeResult:
    try:
        neighborhood = lookup_product_graph(
            neo4j_driver,
            tenant_id=tenant_id,
            product_id=product_id,
            limit=1,
        )

        paths = lookup_product_impact_paths(
            neo4j_driver,
            tenant_id=tenant_id,
            product_id=product_id,
            limit=10,
        )

    except ValueError:
        return GraphRuntimeResult(
            status="HOLD",
            conclusion=(
                "현재 대상은 검증된 Demo Graph "
                "조회 범위에 포함되지 않습니다."
            ),
            key_facts=(),
            evidence=(),
        )
    except Exception:
        return GraphRuntimeResult(
            status="HOLD",
            conclusion=(
                "Graph 관계 조회를 안전하게 "
                "완료하지 못했습니다."
            ),
            key_facts=(),
            evidence=(),
        )

    if not neighborhood:
        return GraphRuntimeResult(
            status="NO_EDGE",
            conclusion=(
                "대상 상품에 연결된 운영 관계가 "
                "확인되지 않았습니다."
            ),
            key_facts=(),
            evidence=(),
        )

    if not paths:
        return GraphRuntimeResult(
            status="NO_EDGE",
            conclusion=(
                "상품은 확인되었지만 입고에서 "
                "업무까지 이어지는 영향 경로는 "
                "확인되지 않았습니다."
            ),
            key_facts=(
                "확인 경로: "
                "Product→SKU→Incoming→Task",
            ),
            evidence=(),
        )

    evidence = []

    for index, row in enumerate(
        paths,
        start=1,
    ):
        product = row["product"]
        sku = row["sku"]
        incoming = row["incoming"]
        task = row["task"]

        evidence.append(
            GraphRelationEvidence(
                evidence_id=(
                    "graph-path:"
                    f"{PROJECTION_VERSION}:"
                    f"{product['id']}:"
                    f"{index}"
                ),
                hop_count=3,
                path=(
                    str(product["id"]),
                    str(sku["id"]),
                    str(incoming["id"]),
                    str(task["id"]),
                ),
                relation_types=(
                    "HAS_SKU",
                    "HAS_INCOMING",
                    "AFFECTS_TASK",
                ),
                projection_version=(
                    PROJECTION_VERSION
                ),
            )
        )

    return GraphRuntimeResult(
        status="ANSWER",
        conclusion=(
            "상품에서 SKU와 입고를 거쳐 "
            "업무로 이어지는 검증된 영향 "
            "경로를 확인했습니다."
        ),
        key_facts=(
            f"확인된 3-hop 경로: {len(paths)}개",
            "경로: "
            "Product→SKU→Incoming→Task",
        ),
        evidence=tuple(evidence),
    )