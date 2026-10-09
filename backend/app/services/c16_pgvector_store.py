"""C16 persistence for C15 synthetic PRODUCT chunks only.

The caller owns the transaction. This module never connects to a database on import.
The vector column is intentionally SQL-only until the project adopts a pgvector ORM type.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ai.evaluation.r09_graph_eval_contract import R09_EMBEDDING_CONFIG
from backend.app.models_v2.catalog import ProductV2
from backend.app.services.c15_synthetic_seed import TENANT_ID, generate_seed, identity

EMBEDDING = R09_EMBEDDING_CONFIG
SOURCE_TYPE = "PRODUCT"


@dataclass(frozen=True)
class ProductChunk:
    id: UUID
    tenant_id: UUID
    source_type: str
    source_id: str
    source_version: str
    chunk_no: int
    chunk_text: str
    content_hash: str
    metadata: dict
    product_id: UUID
    product_code: str
    product_name: str
    sale_price: Decimal


@dataclass(frozen=True)
class VectorHit:
    source_type: str
    source_id: str
    source_version: str
    chunk_no: int
    distance: float
    score: float

@dataclass(frozen=True)
class ReindexResult:
    updated: int
    unchanged: int
    missing: int

def _require_demo_tenant(tenant_id: UUID) -> None:
    if tenant_id != TENANT_ID:
        raise ValueError("C16_TENANT_NOT_C15_DEMO")


def _float32(value: object) -> float:
    if isinstance(value, (str, bytes, bool)):
        raise ValueError("C16_EMBEDDING_NONNUMERIC")
    try:
        number = float(value)
        number = struct.unpack("!f", struct.pack("!f", number))[0]
    except (OverflowError, struct.error) as exc:
        raise ValueError("C16_EMBEDDING_NONFINITE") from exc
    except (TypeError, ValueError) as exc:
        raise ValueError("C16_EMBEDDING_NONNUMERIC") from exc
    if not math.isfinite(number):
        raise ValueError("C16_EMBEDDING_NONFINITE")
    return number


def vector_literal(values: Sequence[object]) -> str:
    """Validate normalized 384-D input and serialize only float32 numbers."""
    if isinstance(values, (str, bytes)) or len(values) != EMBEDDING.dimension:
        raise ValueError("C16_EMBEDDING_DIMENSION")
    numbers = [_float32(value) for value in values]
    norm = math.sqrt(sum(value * value for value in numbers))
    if not 0.99 <= norm <= 1.01:
        raise ValueError("C16_EMBEDDING_NOT_NORMALIZED")
    return "[" + ",".join(format(value, ".9g") for value in numbers) + "]"


def _same_vector(stored: str | None, expected_literal: str) -> bool:
    if stored is None:
        return False
    try:
        existing = json.loads(stored)
        expected = json.loads(expected_literal)
        return len(existing) == len(expected) == EMBEDDING.dimension and all(
            struct.pack("!f", float(a)) == struct.pack("!f", float(b))
            for a, b in zip(existing, expected, strict=True)
        )
    except (TypeError, ValueError, OverflowError, struct.error):
        return False


def build_c15_product_chunks() -> list[ProductChunk]:
    """Use generated C15 catalog values; never read order or customer rows."""
    bundle = generate_seed()
    categories = {row["id"]: row["category_name"] for row in bundle.categories}
    membership: dict[UUID, list[str]] = {row["id"]: [] for row in bundle.products}
    for relation in bundle.product_categories:
        membership[relation["product_id"]].append(categories[relation["category_id"]])
    result = []
    for product in bundle.products:
        names = sorted(membership[product["id"]])
        content = (
            f"상품명: {product['product_name']}\n"
            f"상품 코드: {product['product_code']}\n"
            f"판매가(원): {product['sale_price']:.2f}\n"
            f"카테고리: {', '.join(names) if names else '미분류'}"
        )
        result.append(
            ProductChunk(
                id=identity("rag-chunk", f"{product['id']}:0"),
                tenant_id=TENANT_ID,
                source_type=SOURCE_TYPE,
                source_id=str(product["id"]),
                source_version=bundle.manifest["seed_version"],
                chunk_no=0,
                chunk_text=content,
                content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                metadata={
                    "data_mode": "SYNTHETIC_DEMO",
                    "product_code": product["product_code"],
                    "categories": names,
                    "as_of": bundle.manifest["as_of"],
                    "embedding_model": EMBEDDING.model,
                    "embedding_revision": EMBEDDING.revision,
                    "normalize_embeddings": EMBEDDING.normalized,
                    "dimension": EMBEDDING.dimension,
                },
                product_id=product["id"],
                product_code=product["product_code"],
                product_name=product["product_name"],
                sale_price=product["sale_price"],
            )
        )
    return result


def encode_fixed(texts: list[str]) -> Sequence[Sequence[float]]:
    """Small adapter for the existing SentenceTransformer encode pattern."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING.model, revision=EMBEDDING.revision, device="cpu")
    vectors = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    if len(vectors) != len(texts):
        raise ValueError("C16_EMBEDDING_COUNT")
    for vector in vectors:
        vector_literal(vector)
    return vectors


_EXISTING_SQL = text(
    "SELECT id, chunk_text, content_hash, embedding_model, embedding_version, "
    "metadata, is_current, CAST(embedding AS text) AS embedding_text "
    "FROM ai.rag_chunks WHERE tenant_id = :tenant_id AND source_type = :source_type "
    "AND source_id = :source_id AND source_version = :source_version AND chunk_no = :chunk_no"
)

_INSERT_SQL = text(
    "INSERT INTO ai.rag_chunks "
    "(id, tenant_id, source_type, source_id, source_version, chunk_no, chunk_text, "
    "content_hash, embedding_model, embedding_version, metadata, is_current, embedding) "
    "VALUES (:id, :tenant_id, :source_type, :source_id, :source_version, :chunk_no, "
    ":chunk_text, :content_hash, :embedding_model, :embedding_version, "
    "CAST(:metadata_json AS jsonb), true, CAST(:embedding AS vector))"
)

_UPDATE_SQL = text(
    "UPDATE ai.rag_chunks SET "
    "chunk_text = :chunk_text, "
    "content_hash = :content_hash, "
    "embedding_model = :embedding_model, "
    "embedding_version = :embedding_version, "
    "metadata = CAST(:metadata_json AS jsonb), "
    "embedding = CAST(:embedding AS vector) "
    "WHERE tenant_id = :tenant_id "
    "AND source_type = :source_type "
    "AND source_id = :source_id "
    "AND source_version = :source_version "
    "AND chunk_no = :chunk_no "
    "AND id = :id"
)

def persist_c15_products(
    session: Session,
    *,
    tenant_id: UUID,
    embed_texts: Callable[[list[str]], Sequence[Sequence[float]]] = encode_fixed,
) -> int:
    """Insert missing owned chunks; reject row drift. Caller must commit or roll back."""
    _require_demo_tenant(tenant_id)
    chunks = build_c15_product_chunks()
    products = {
        row.id: row
        for row in session.execute(
            select(
                ProductV2.id, ProductV2.product_code, ProductV2.product_name, ProductV2.sale_price
            ).where(
                ProductV2.tenant_id == tenant_id, ProductV2.id.in_([c.product_id for c in chunks])
            )
        ).all()
    }
    if len(products) != 150 or any(
        (row := products.get(chunk.product_id)) is None
        or row.product_code != chunk.product_code
        or row.product_name != chunk.product_name
        or row.sale_price != chunk.sale_price
        for chunk in chunks
    ):
        raise RuntimeError("C16_C15_CATALOG_MISMATCH")
    vectors = embed_texts([chunk.chunk_text for chunk in chunks])
    if len(vectors) != len(chunks):
        raise ValueError("C16_EMBEDDING_COUNT")
    inserted = 0
    for chunk, vector in zip(chunks, vectors, strict=True):
        literal = vector_literal(vector)
        key = dict(
            tenant_id=tenant_id,
            source_type=chunk.source_type,
            source_id=chunk.source_id,
            source_version=chunk.source_version,
            chunk_no=chunk.chunk_no,
        )
        old = session.execute(_EXISTING_SQL, key).mappings().one_or_none()
        if old is not None:
            if (
                old["id"] != chunk.id
                or old["chunk_text"] != chunk.chunk_text
                or old["content_hash"] != chunk.content_hash
                or old["embedding_model"] != EMBEDDING.model
                or old["embedding_version"] != EMBEDDING.revision
                or old["metadata"] != chunk.metadata
                or old["is_current"] is not True
                or not _same_vector(old["embedding_text"], literal)
            ):
                raise RuntimeError("C16_OWNED_CHUNK_DRIFT")
            continue
        session.execute(
            _INSERT_SQL,
            dict(
                key,
                id=chunk.id,
                chunk_text=chunk.chunk_text,
                content_hash=chunk.content_hash,
                embedding_model=EMBEDDING.model,
                embedding_version=EMBEDDING.revision,
                metadata_json=json.dumps(chunk.metadata, sort_keys=True),
                embedding=literal,
            ),
        )
        inserted += 1
    return inserted

def reindex_c15_products(
    session: Session,
    *,
    tenant_id: UUID,
    embed_texts: Callable[[list[str]], Sequence[Sequence[float]]] = encode_fixed,
) -> ReindexResult:
    """Update only existing owned C15 Product chunks.

    This is an explicit maintenance path for approved C15 display-content
    changes. It never inserts or deletes rows. Caller owns commit/rollback.
    """
    _require_demo_tenant(tenant_id)

    chunks = build_c15_product_chunks()

    products = {
        row.id: row
        for row in session.execute(
            select(
                ProductV2.id,
                ProductV2.product_code,
                ProductV2.product_name,
                ProductV2.sale_price,
            ).where(
                ProductV2.tenant_id == tenant_id,
                ProductV2.id.in_([chunk.product_id for chunk in chunks]),
            )
        ).all()
    }

    if len(products) != 150 or any(
        (row := products.get(chunk.product_id)) is None
        or row.product_code != chunk.product_code
        or row.product_name != chunk.product_name
        or row.sale_price != chunk.sale_price
        for chunk in chunks
    ):
        raise RuntimeError("C16_C15_CATALOG_MISMATCH")

    vectors = embed_texts([chunk.chunk_text for chunk in chunks])
    if len(vectors) != len(chunks):
        raise ValueError("C16_EMBEDDING_COUNT")

    updated = 0
    unchanged = 0
    missing = 0

    for chunk, vector in zip(chunks, vectors, strict=True):
        literal = vector_literal(vector)

        key = dict(
            tenant_id=tenant_id,
            source_type=chunk.source_type,
            source_id=chunk.source_id,
            source_version=chunk.source_version,
            chunk_no=chunk.chunk_no,
        )

        old = session.execute(_EXISTING_SQL, key).mappings().one_or_none()

        if old is None:
            missing += 1
            continue

        metadata = old["metadata"]

        if (
            old["id"] != chunk.id
            or old["is_current"] is not True
            or not isinstance(metadata, dict)
            or metadata.get("data_mode") != "SYNTHETIC_DEMO"
            or metadata.get("product_code") != chunk.product_code
        ):
            raise RuntimeError("C16_REINDEX_IDENTITY_MISMATCH")

        if (
            old["chunk_text"] == chunk.chunk_text
            and old["content_hash"] == chunk.content_hash
            and old["embedding_model"] == EMBEDDING.model
            and old["embedding_version"] == EMBEDDING.revision
            and old["metadata"] == chunk.metadata
            and _same_vector(old["embedding_text"], literal)
        ):
            unchanged += 1
            continue

        result = session.execute(
            _UPDATE_SQL,
            dict(
                key,
                id=chunk.id,
                chunk_text=chunk.chunk_text,
                content_hash=chunk.content_hash,
                embedding_model=EMBEDDING.model,
                embedding_version=EMBEDDING.revision,
                metadata_json=json.dumps(chunk.metadata, sort_keys=True),
                embedding=literal,
            ),
        )

        if result.rowcount != 1:
            raise RuntimeError("C16_REINDEX_UPDATE_MISMATCH")

        updated += 1

    return ReindexResult(
        updated=updated,
        unchanged=unchanged,
        missing=missing,
    )

_QUERY_SQL = text(
    "SELECT source_type, source_id, source_version, chunk_no, "
    "embedding <=> CAST(:query_vector AS vector) AS distance "
    "FROM ai.rag_chunks "
    "WHERE tenant_id = :tenant_id AND is_current = true "
    "AND source_type = 'PRODUCT' AND source_version = :source_version "
    "AND source_id = ANY(:source_ids) "
    "AND embedding IS NOT NULL "
    "ORDER BY embedding <=> CAST(:query_vector AS vector), id LIMIT :top_k"
)


def query_c15_products(
    session: Session, *, tenant_id: UUID, query_vector: Sequence[object], top_k: int
) -> list[VectorHit]:
    _require_demo_tenant(tenant_id)
    if type(top_k) is not int or not 1 <= top_k <= 50:
        raise ValueError("C16_TOP_K_INVALID")
    literal = vector_literal(query_vector)
    bundle = generate_seed()
    version = bundle.manifest["seed_version"]
    source_ids = [str(product["id"]) for product in bundle.products]
    rows = (
        session.execute(
            _QUERY_SQL,
            dict(
                tenant_id=tenant_id,
                query_vector=literal,
                source_version=version,
                source_ids=source_ids,
                top_k=top_k,
            ),
        )
        .mappings()
        .all()
    )
    return [
        VectorHit(
            source_type=row["source_type"],
            source_id=row["source_id"],
            source_version=row["source_version"],
            chunk_no=row["chunk_no"],
            distance=float(row["distance"]),
            score=1.0 - float(row["distance"]),
        )
        for row in rows
    ]
