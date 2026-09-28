"""Local files only: no retrieval imports, network calls or database connections."""

import json
from collections import Counter
from copy import deepcopy
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.services import corpus_restore as cr
from backend.app.services.c04_lookup import LookupFailure


def jsonl(rows):
    return ("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True)
                      for row in rows) + "\n").encode()


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    source = {
        "tenant_id": "demo_store", "source_id": "fixture_product", "version": "v1",
        "source_type": "PRODUCT", "title": "Synthetic fixture",
        "as_of": "2026-09-26T04:00:00Z", "content": "First sentence. Second sentence.",
        "pii_status": "CLEAN", "data_mode": "SYNTHETIC_DEMO", "visibility": "DEMO_PUBLIC",
    }
    chunks = [{
        "schema_version": "retrieval-chunk-snapshot.v1",
        "chunk_id": f"fixture_product:v1:semantic:{i}", "chunk_index": i,
        "source_id": source["source_id"], "version": "v1", "source_type": "PRODUCT",
        "text": text, "token_count": 3, "sentence_start": i, "sentence_end": i + 1,
        "metadata": {"title": source["title"]},
        "tenant_id": "demo_store", "data_mode": "SYNTHETIC_DEMO",
        "as_of": source["as_of"],
    } for i, text in enumerate(["First sentence.", "Second sentence."])]
    handoff = {
        "handoff_id": "C05-R05-RETRIEVAL",
        "selection": {"method": "fixture-method", "status": "fixture-status"},
        "dataset": {"snapshot_path": cr.BASE_SNAPSHOT_REL, "corpus_path": cr.CORPUS_REL,
                    "snapshot_chunks": 2, "corpus_records": 1, "snapshot_documents": 1},
    }
    manifest = {
        "schema_version": "retrieval-snapshot-manifest.v1",
        "snapshot_version": cr.SNAPSHOT_VERSION, "chunking": {"chunk_count": 2},
        "corpus": {"path": cr.CORPUS_REL, "record_count": 1, "unique_source_count": 1},
        "metadata_enrichment": {"base_snapshot_path": cr.BASE_SNAPSHOT_REL,
                                "tenant_id": "demo_store"},
    }
    paths = {}
    for name in ("HANDOFF", "MANIFEST", "SNAPSHOT", "CORPUS"):
        paths[name] = tmp_path / name
        monkeypatch.setattr(cr, name + "_PATH", paths[name])

    def write():
        corpus, snapshot = jsonl([source]), jsonl(chunks)
        handoff["dataset"]["snapshot_sha256"] = sha256(snapshot).hexdigest()
        handoff["dataset"]["corpus_sha256"] = sha256(corpus).hexdigest()
        manifest["snapshot_hash"] = sha256(snapshot).hexdigest()
        manifest["snapshot_file_sha256"] = sha256(snapshot).hexdigest()
        manifest["metadata_enrichment"]["source_type_counts"] = dict(
            Counter(c["source_type"] for c in chunks)
        )
        manifest["corpus"]["sha256"] = sha256(corpus).hexdigest()
        paths["HANDOFF"].write_text(json.dumps(handoff), encoding="utf-8")
        paths["MANIFEST"].write_text(json.dumps(manifest), encoding="utf-8")
        paths["CORPUS"].write_bytes(corpus)
        paths["SNAPSHOT"].write_bytes(snapshot)

    write()
    return source, chunks, handoff, manifest, paths, write


def restore():
    return cr.restore_corpus(tenant_id="demo_store", environment="TEST")


def assert_blocked(result, code):
    assert result.status in {"UNAVAILABLE", "BLOCKED_BY_METADATA"}
    assert result.error == code
    assert not result.mappings
    with pytest.raises(LookupFailure, match="C04_REGISTRY_UNAVAILABLE"):
        result.lookup_service.lookup(tenant_id="demo_store", source_id="fixture_product",
                                     version="v1")
    with pytest.raises(LookupFailure, match="C04_REGISTRY_UNAVAILABLE"):
        result.resolve(tenant_id="demo_store", source_id="fixture_product", version="v1",
                       semantic_chunk_id="missing", semantic_excerpt_hash="missing")


def test_complete_restore_and_mapping_preserve_distinct_hashes(bundle):
    result = restore()
    assert result.status == "READY"
    assert result.selection_method == "fixture-method"
    assert result.selection_status == "fixture-status"
    semantic_hash = cr._hash(bundle[1][0]["text"])
    mapping = result.resolve(tenant_id="demo_store", source_id="fixture_product", version="v1",
                             semantic_chunk_id="fixture_product:v1:semantic:0",
                             semantic_excerpt_hash=semantic_hash)
    exact = result.lookup_service.lookup(tenant_id="demo_store", source_id=mapping.source_id,
                                         version=mapping.version, chunk_id=mapping.c04_chunk_id)
    assert exact.excerpt == bundle[0]["content"]
    assert mapping.semantic_excerpt_hash == semantic_hash
    assert mapping.c04_excerpt_hash == exact.excerpt_hash
    assert mapping.semantic_excerpt_hash != mapping.c04_excerpt_hash
    assert mapping.semantic_chunk_id == "fixture_product:v1:semantic:0"
    assert mapping.c04_chunk_id == "fixture_product:v1:c04:0"


@pytest.mark.parametrize("changes", [
    {"semantic_chunk_id": "fixture_product:v1:semantic:99"},
    {"semantic_excerpt_hash": "sha256:incorrect"}, {"tenant_id": "other"},
    {"source_id": "missing"}, {"version": "v2"},
])
def test_mapping_missing_never_fabricates_key(bundle, changes):
    args = dict(tenant_id="demo_store", source_id="fixture_product", version="v1",
                semantic_chunk_id="fixture_product:v1:semantic:0",
                semantic_excerpt_hash=cr._hash(bundle[1][0]["text"]))
    args.update(changes)
    with pytest.raises(LookupFailure, match="C04_MAPPING_NOT_FOUND"):
        restore().resolve(**args)


def test_restart_reads_same_exact_projection(bundle):
    settings = Settings(_env_file=None, environment="TEST", database_url="sqlite://")
    results = []
    for _ in range(2):
        app = create_app(settings)
        response = TestClient(app).get("/api/v1/c04/lookup", params={
            "source_id": "fixture_product", "version": "v1",
        })
        assert response.status_code == 200
        results.append(response.json()["data"])
        assert app.state.c04_corpus_restore.status == "READY"
    assert results[0] == results[1]


@pytest.mark.parametrize("kind", ["HANDOFF", "MANIFEST", "SNAPSHOT", "CORPUS"])
def test_missing_file(bundle, kind):
    bundle[4][kind].unlink()
    label = "SOURCE" if kind == "CORPUS" else kind
    assert_blocked(restore(), f"CORPUS_{label}_UNAVAILABLE")


def test_snapshot_hash_mismatch(bundle):
    bundle[4]["SNAPSHOT"].write_bytes(b"tampered")
    assert_blocked(restore(), "CORPUS_SNAPSHOT_HASH_MISMATCH")


def test_invalid_snapshot_json_even_with_matching_file_hash(bundle):
    bad = b'{"broken":\n'
    bundle[4]["SNAPSHOT"].write_bytes(bad)
    bundle[3]["snapshot_file_sha256"] = sha256(bad).hexdigest()
    bundle[4]["MANIFEST"].write_text(json.dumps(bundle[3]))
    assert_blocked(restore(), "CORPUS_JSON_INVALID")


@pytest.mark.parametrize("kind", ["MANIFEST", "HANDOFF", "CORPUS"])
def test_corrupt_other_inputs(bundle, kind):
    bundle[4][kind].write_bytes(b"invalid-json")
    assert_blocked(restore(), "CORPUS_SOURCE_HASH_MISMATCH" if kind == "CORPUS"
                   else "CORPUS_JSON_INVALID")


@pytest.mark.parametrize("source_type", [
    "ORDER_STATUS", "order", "order_line", "customer", "shipping", "payment", "inquiry",
])
def test_forbidden_source_type(bundle, source_type):
    bundle[0]["source_type"] = source_type
    bundle[5]()
    assert_blocked(restore(), "CORPUS_SOURCE_TYPE_BLOCKED")


@pytest.mark.parametrize("changes", [
    {"content": "reservation_id=secret"}, {"content": 'customer: secret'},
    {"fields": {"affected_order_ids": ["secret"]}},
    {"feedback": "free memo"}, {"content": "feedback: free memo"},
    {"paragraphs": [{"text": "payment_id=secret"}]},
])
def test_sensitive_references_even_with_clean(bundle, changes):
    bundle[0].update(changes)
    bundle[5]()
    assert_blocked(restore(), "CORPUS_SENSITIVE_REFERENCE")


def test_sensitive_chunk_metadata(bundle):
    bundle[1][0]["metadata"]["reservation_id"] = "secret"
    bundle[5]()
    assert_blocked(restore(), "CORPUS_SENSITIVE_REFERENCE")


def test_tenant_mismatch(bundle):
    bundle[0]["tenant_id"] = "foreign"
    bundle[5]()
    assert_blocked(restore(), "CORPUS_TENANT_MISMATCH")


@pytest.mark.parametrize("field", [
    "data_mode", "visibility", "version", "title", "pii_status",
])
@pytest.mark.parametrize("null", [True, False])
def test_required_metadata_not_inferred(bundle, field, null):
    if null:
        bundle[0][field] = None
    else:
        del bundle[0][field]
    bundle[5]()
    result = restore()
    assert_blocked(result, "SOURCE_METADATA_INCOMPLETE")
    assert result.status == "BLOCKED_BY_METADATA"


@pytest.mark.parametrize("field", ["schema_version", "snapshot_version"])
def test_unsupported_manifest(bundle, field):
    bundle[3][field] = "unsupported"
    bundle[5]()
    assert_blocked(restore(), "CORPUS_SCHEMA_UNSUPPORTED")


def test_unsupported_chunk_schema(bundle):
    bundle[1][0]["schema_version"] = "unsupported"
    bundle[5]()
    assert_blocked(restore(), "CORPUS_SCHEMA_UNSUPPORTED")


def test_manifest_hash_mismatch(bundle):
    bundle[3]["snapshot_hash"] = "incorrect"
    bundle[4]["MANIFEST"].write_text(json.dumps(bundle[3]))
    assert_blocked(restore(), "CORPUS_MANIFEST_HASH_MISMATCH")


def test_manifest_count_mismatch(bundle):
    bundle[3]["chunking"]["chunk_count"] = 99
    bundle[5]()
    assert_blocked(restore(), "CORPUS_COUNT_MISMATCH")


def test_no_http_or_artifact_path_selection(bundle):
    bundle[2]["dataset"]["snapshot_path"] = "https://example.invalid/unsafe"
    bundle[5]()
    assert_blocked(restore(), "CORPUS_PATH_NOT_ALLOWLISTED")


def test_duplicate_mapping_and_projection_mismatch(bundle):
    original = deepcopy(bundle[1])
    bundle[1][1] = deepcopy(bundle[1][0])
    bundle[5]()
    assert_blocked(restore(), "CORPUS_DUPLICATE_IDENTITY")
    bundle[1][:] = original
    bundle[1][1]["text"] = "Unrelated text."
    bundle[5]()
    assert_blocked(restore(), "CORPUS_PROJECTION_MISMATCH")


def test_restore_is_atomic_and_http_unavailable_after_corruption(bundle):
    assert restore().status == "READY"
    bundle[1][-1]["text"] = "reservation_id=blocked"
    bundle[5]()
    app = create_app(Settings(_env_file=None, environment="TEST", database_url="sqlite://"))
    assert_blocked(app.state.c04_corpus_restore, "CORPUS_SENSITIVE_REFERENCE")
    assert TestClient(app).get("/api/v1/c04/lookup", params={
        "source_id": "fixture_product", "version": "v1",
    }).json() == {"detail": "C04_REGISTRY_UNAVAILABLE"}


def test_production_never_reads_corpus(monkeypatch):
    def forbidden(*args):
        pytest.fail("Production must not read corpus artifacts")
    monkeypatch.setattr(cr, "_read", forbidden)
    result = cr.restore_corpus(tenant_id="demo_store", environment="PRODUCTION_READ")
    assert result.status == "DISABLED"


def test_canonical_artifacts_restore():
    manifest = json.loads(cr.MANIFEST_PATH.read_bytes())
    assert manifest["snapshot_hash"] == (
        "dcc7c19fc4adf7539b42a289f7f2a76a1ac689335aa84709c24a6ad183f79849"
    )
    assert sha256(cr.SNAPSHOT_PATH.read_bytes()).hexdigest() == (
        "ca5df959ad8e4e9fc12624863cb3847b8c463ca7b822a58a9df93a20a3d7f198"
    )
    result = restore()
    assert result.status == "READY"
    assert len(result.mappings) == 15
    assert len({(m.source_id, m.version) for m in result.mappings.values()}) == 8


@pytest.mark.parametrize("field", ["tenant_id", "data_mode", "version", "as_of"])
def test_missing_enriched_metadata(bundle, field):
    del bundle[1][0][field]
    bundle[5]()
    assert_blocked(restore(), "SOURCE_METADATA_INCOMPLETE")


@pytest.mark.parametrize("source_type", sorted(cr.ALLOWED_TYPES))
def test_source_specific_null_as_of(bundle, source_type):
    bundle[0].update(source_type=source_type, as_of=None)
    for chunk in bundle[1]:
        chunk.update(source_type=source_type, as_of=None)
    bundle[5]()
    result = restore()
    if source_type in cr.LIVE_TTL_SECONDS:
        assert_blocked(result, "SOURCE_METADATA_INCOMPLETE")
    else:
        assert result.status == "READY"
        lookup = result.lookup_service.lookup(
            tenant_id="demo_store", source_id="fixture_product", version="v1",
        )
        assert lookup.as_of is None and lookup.stale is False


@pytest.mark.parametrize("field,value", [
    ("tenant_id", "foreign"), ("data_mode", "PRODUCTION"),
    ("as_of", "2026-09-25T00:00:00Z"),
])
def test_chunk_provenance_conflict(bundle, field, value):
    bundle[1][1][field] = value
    bundle[5]()
    assert_blocked(restore(), "CORPUS_TENANT_MISMATCH" if field == "tenant_id"
                   else "CORPUS_METADATA_MISMATCH")


def test_actual_restart_readback_and_dev_mapping(monkeypatch):
    reads = []
    real_read = cr._read

    def tracked_read(path, kind):
        reads.append(kind)
        return real_read(path, kind)

    monkeypatch.setattr(cr, "_read", tracked_read)
    settings = Settings(_env_file=None, environment="TEST", database_url="sqlite://")
    apps = [create_app(settings), create_app(settings)]
    assert apps[0].state.c04_lookup_service is not apps[1].state.c04_lookup_service
    assert Counter(reads) == {"HANDOFF": 2, "MANIFEST": 2, "SNAPSHOT": 2, "SOURCE": 2}
    sources = [
        ("product_demo_long_003", "v1", "PRODUCT", None),
        ("policy_shipping_demo", "v2", "POLICY", None),
        ("inventory_snapshot_demo_sku_001", "v1", "INVENTORY_SNAPSHOT",
         "2026-09-26T04:00:00Z"),
        ("incoming_stock_demo_confirmed_001", "v1", "INCOMING_STOCK",
         "2026-09-26T04:00:00Z"),
    ]
    for source_id, version, source_type, as_of in sources:
        responses = []
        for app in apps:
            response = TestClient(app).get("/api/v1/c04/lookup", params={
                "source_id": source_id, "version": version, "tenant_id": "foreign",
            }, headers={"X-Tenant-ID": "foreign"})
            assert response.status_code == 200
            body = response.json()
            assert body["tenant_id"] == "demo_store"
            data = body["data"]
            assert data["source_id"] == source_id and data["version"] == version
            assert data["source_type"] == source_type
            assert data["data_mode"] == "SYNTHETIC_DEMO"
            assert data["as_of"] == body["as_of"] == as_of
            assert data["chunk_id"] == f"{source_id}:{version}:c04:0"
            assert data["excerpt_hash"] == cr._hash(data["excerpt"])
            assert data["stale"] is (as_of is not None)
            responses.append(data)
        assert responses[0] == responses[1]
    artifact = json.loads((cr.ROOT / (
        "artifacts/experiments/OPS-RAG-01/r05_retrieval_result.json"
    )).read_bytes())
    row = next(row for row in artifact["rows"] if row["case_id"] == "GE-D-001"
               and row["method"] == apps[0].state.c04_corpus_restore.selection_method)
    citation = next(c for c in row["top5"] if c["source_id"] == "product_demo_long_003")
    chunk = next(c for c in cr._rows(cr.SNAPSHOT_PATH.read_bytes())
                 if c["chunk_id"] == citation["chunk_id"])
    mapping = apps[0].state.c04_corpus_restore.resolve(
        tenant_id="demo_store", source_id=citation["source_id"], version=citation["version"],
        semantic_chunk_id=citation["chunk_id"], semantic_excerpt_hash=cr._hash(chunk["text"]),
    )
    assert mapping.semantic_excerpt == chunk["text"]
    assert mapping.semantic_excerpt_hash == cr._hash(mapping.semantic_excerpt)
    assert mapping.c04_excerpt_hash == cr._hash(mapping.c04_excerpt)
    assert mapping.semantic_chunk_id != mapping.c04_chunk_id
    assert mapping.semantic_excerpt_hash != mapping.c04_excerpt_hash
