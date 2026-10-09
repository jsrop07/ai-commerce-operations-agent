"""C16 contract tests. No PostgreSQL connection or model download."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.sql.elements import TextClause

from backend.app.services.c15_synthetic_seed import TENANT_ID, generate_seed
from backend.app.services.c16_pgvector_store import (
    EMBEDDING,
    build_c15_product_chunks,
    encode_fixed,
    persist_c15_products,
    query_c15_products,
    reindex_c15_products,
    vector_literal,
)

UNIT = [1.0] + [0.0] * 383

class FakeResult:
    def __init__(self, rows, rowcount=0):
        self.rows = rows
        self.rowcount = rowcount

    def all(self):
        return self.rows

    def mappings(self):
        return self

    def one_or_none(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self):
        self.products = generate_seed().products
        self.chunks = {}
        self.calls = []

    def execute(self, statement, params=None):
        self.calls.append((str(statement), params))
        if not isinstance(statement, TextClause):
            return FakeResult(
                [
                    SimpleNamespace(
                        id=p["id"],
                        product_code=p["product_code"],
                        product_name=p["product_name"],
                        sale_price=p["sale_price"],
                    )
                    for p in self.products
                ]
            )
        sql = str(statement)
        if sql.startswith("SELECT id, chunk_text"):
            key = (
                params["tenant_id"],
                params["source_type"],
                params["source_id"],
                params["source_version"],
                params["chunk_no"],
            )
            return FakeResult([self.chunks[key]] if key in self.chunks else [])
        if sql.startswith("INSERT INTO ai.rag_chunks"):
            key = (
                params["tenant_id"],
                params["source_type"],
                params["source_id"],
                params["source_version"],
                params["chunk_no"],
            )
            self.chunks[key] = dict(
                id=params["id"],
                chunk_text=params["chunk_text"],
                content_hash=params["content_hash"],
                embedding_model=params["embedding_model"],
                embedding_version=params["embedding_version"],
                metadata=json.loads(params["metadata_json"]),
                is_current=True,
                embedding_text=params["embedding"],
            )
            return FakeResult([])
        if sql.startswith("UPDATE ai.rag_chunks SET"):
            key = (
                params["tenant_id"],
                params["source_type"],
                params["source_id"],
                params["source_version"],
                params["chunk_no"],
            )
            old = self.chunks.get(key)
            if old is None or old["id"] != params["id"]:
                return FakeResult([], rowcount=0)

            old.update(
                chunk_text=params["chunk_text"],
                content_hash=params["content_hash"],
                embedding_model=params["embedding_model"],
                embedding_version=params["embedding_version"],
                metadata=json.loads(params["metadata_json"]),
                embedding_text=params["embedding"],
            )
            return FakeResult([], rowcount=1)
        if sql.startswith("SELECT source_type, source_id"):
            return FakeResult(
                [
                    dict(
                        source_type="PRODUCT",
                        source_id=str(self.products[0]["id"]),
                        source_version=generate_seed().manifest["seed_version"],
                        chunk_no=0,
                        distance=0.25,
                    )
                ]
            )
        raise AssertionError(sql)


def test_c16_vector_validation_and_safe_serialization():
    literal = vector_literal(UNIT)
    assert len(json.loads(literal)) == 384
    assert literal.startswith("[1,0,0,")
    with pytest.raises(ValueError, match="DIMENSION"):
        vector_literal(UNIT[:-1])
    with pytest.raises(ValueError, match="NONNUMERIC"):
        vector_literal(["0); DROP TABLE ai.rag_chunks;--"] + UNIT[1:])
    with pytest.raises(ValueError, match="NONFINITE"):
        vector_literal([float("nan")] + UNIT[1:])
    with pytest.raises(ValueError, match="NOT_NORMALIZED"):
        vector_literal([0.0] * 384)


def test_c16_only_c15_safe_products_and_fixed_metadata():
    chunks = build_c15_product_chunks()
    bundle = generate_seed()
    assert len(chunks) == 150
    assert all(
        c.chunk_text.startswith("상품명: ") and "\n카테고리: " in c.chunk_text for c in chunks
    )
    assert all(
        "Categories:" not in c.chunk_text and "Uncategorized" not in c.chunk_text
        for c in chunks
    )
    assert {c.source_id for c in chunks} == {str(p["id"]) for p in bundle.products}
    assert all(
        c.source_type == "PRODUCT" and c.chunk_no == 0 and c.tenant_id == TENANT_ID for c in chunks
    )
    assert all(c.metadata["data_mode"] == "SYNTHETIC_DEMO" for c in chunks)
    assert all(
        c.metadata["embedding_model"] == EMBEDDING.model
        and c.metadata["embedding_revision"] == EMBEDDING.revision
        and c.metadata["normalize_embeddings"] is True
        and c.metadata["dimension"] == 384
        for c in chunks
    )
    assert EMBEDDING.model == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    assert EMBEDDING.revision == "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
    assert all(
        not any(
            word in c.chunk_text.lower()
            for word in ("order item", "customer", "shipping address", "payment")
        )
        for c in chunks
    )
    hero = next(
        c for c in chunks
        if c.product_code == "DEMO-P-0009"
    )
    assert "상품명: 아침 시장" in hero.chunk_text


def test_c16_writer_tenant_identity_idempotence_and_drift():
    session = FakeSession()

    def encoder(texts):
        return [UNIT[:] for _ in texts]

    with pytest.raises(ValueError, match="TENANT"):
        persist_c15_products(session, tenant_id=uuid4(), embed_texts=encoder)
    assert session.calls == []
    assert persist_c15_products(session, tenant_id=TENANT_ID, embed_texts=encoder) == 150
    assert persist_c15_products(session, tenant_id=TENANT_ID, embed_texts=encoder) == 0
    assert len(session.chunks) == 150
    first = next(iter(session.chunks.values()))
    first["chunk_text"] = "drift"
    with pytest.raises(RuntimeError, match="C16_OWNED_CHUNK_DRIFT"):
        persist_c15_products(session, tenant_id=TENANT_ID, embed_texts=encoder)


def test_c16_query_cosine_sql_and_tenant_filter():
    session = FakeSession()
    with pytest.raises(ValueError, match="TENANT"):
        query_c15_products(session, tenant_id=uuid4(), query_vector=UNIT, top_k=5)
    with pytest.raises(ValueError, match="TOP_K"):
        query_c15_products(session, tenant_id=TENANT_ID, query_vector=UNIT, top_k=0)
    hits = query_c15_products(session, tenant_id=TENANT_ID, query_vector=UNIT, top_k=5)
    assert hits[0].distance == 0.25 and hits[0].score == 0.75
    sql, params = session.calls[-1]
    assert "<=>" in sql and "tenant_id = :tenant_id" in sql
    assert "is_current = true" in sql and "LIMIT :top_k" in sql
    assert "source_id = ANY(:source_ids)" in sql and len(params["source_ids"]) == 150
    assert params["tenant_id"] == TENANT_ID and params["top_k"] == 5


def test_c16_migration_contract_without_execution():
    path = (
        Path(__file__).resolve().parents[2] / "app/db/migrations_v2/versions/"
        "c16e20261006_add_rag_chunk_embedding.py"
    )
    spec = importlib.util.spec_from_file_location("c16_migration_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "c16e20261006"
    assert module.down_revision == "8dba0e0a9dbd"
    statements = []
    module.op = SimpleNamespace(execute=statements.append)
    module.upgrade()
    assert statements[0] == "CREATE EXTENSION IF NOT EXISTS vector"
    assert "embedding vector(384)" in statements[1]
    assert "USING hnsw" in statements[2] and "vector_cosine_ops" in statements[2]
    statements.clear()
    module.downgrade()
    assert len(statements) == 2 and "DROP COLUMN embedding" in statements[1]
    assert all("DROP EXTENSION" not in statement for statement in statements)


def test_c16_encoder_fixed_cpu_revision_and_normalization(monkeypatch):
    # Exercise the adapter without downloading a model.
    import sys

    captured = {}

    class FakeModel:
        def __init__(self, model, *, revision, device):
            captured.update(model=model, revision=revision, device=device)

        def encode(self, texts, **kwargs):
            captured.update(kwargs)
            return [UNIT[:] for _ in texts]

    monkeypatch.setitem(
        sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=FakeModel)
    )
    assert len(encode_fixed(["demo product"])[0]) == 384
    assert captured["model"] == EMBEDDING.model
    assert captured["revision"] == EMBEDDING.revision
    assert captured["device"] == "cpu"
    assert captured["normalize_embeddings"] is True

def test_c16_reindex_updates_owned_chunks_without_changing_identity():
    session = FakeSession()

    def encoder(texts):
        return [UNIT[:] for _ in texts]

    assert persist_c15_products(
        session,
        tenant_id=TENANT_ID,
        embed_texts=encoder,
    ) == 150

    original_keys = set(session.chunks)
    original_ids = {
        key: value["id"]
        for key, value in session.chunks.items()
    }

    # 승인된 표시내용 변경 이전 상태를 흉내 낸다.
    for row in session.chunks.values():
        row["chunk_text"] = "Product: old english name"
        row["content_hash"] = "old-hash"

    result = reindex_c15_products(
        session,
        tenant_id=TENANT_ID,
        embed_texts=encoder,
    )

    assert result.updated == 150
    assert result.unchanged == 0
    assert result.missing == 0

    assert set(session.chunks) == original_keys
    assert len(session.chunks) == 150

    for key, row in session.chunks.items():
        assert row["id"] == original_ids[key]
        assert row["chunk_text"].startswith("상품명: ")
        assert "\n카테고리: " in row["chunk_text"]


def test_c16_reindex_second_run_is_noop():
    session = FakeSession()

    def encoder(texts):
        return [UNIT[:] for _ in texts]

    assert persist_c15_products(
        session,
        tenant_id=TENANT_ID,
        embed_texts=encoder,
    ) == 150

    result = reindex_c15_products(
        session,
        tenant_id=TENANT_ID,
        embed_texts=encoder,
    )

    assert result.updated == 0
    assert result.unchanged == 150
    assert result.missing == 0
    assert len(session.chunks) == 150


def test_c16_reindex_rejects_wrong_tenant_and_owned_identity_drift():
    session = FakeSession()

    def encoder(texts):
        return [UNIT[:] for _ in texts]

    with pytest.raises(ValueError, match="TENANT"):
        reindex_c15_products(
            session,
            tenant_id=uuid4(),
            embed_texts=encoder,
        )

    assert persist_c15_products(
        session,
        tenant_id=TENANT_ID,
        embed_texts=encoder,
    ) == 150

    first = next(iter(session.chunks.values()))
    first["metadata"]["data_mode"] = "ACTUAL"

    with pytest.raises(
        RuntimeError,
        match="C16_REINDEX_IDENTITY_MISMATCH",
    ):
        reindex_c15_products(
            session,
            tenant_id=TENANT_ID,
            embed_texts=encoder,
        )