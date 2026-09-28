"""Read-only C1 artifact audit; never imports or executes AI retrieval code.

Run from the repository: ai_venv\Scripts\python.exe -m scripts.check_corpus_restore
"""

import json
from collections import Counter
from dataclasses import asdict
from hashlib import sha256

from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.services import corpus_restore as cr


def main():
    handoff = json.loads(cr.HANDOFF_PATH.read_bytes())
    manifest = json.loads(cr.MANIFEST_PATH.read_bytes())
    snapshot = cr.SNAPSHOT_PATH.read_bytes()
    corpus = cr.CORPUS_PATH.read_bytes()
    chunks = cr._rows(snapshot)
    sources = cr._rows(corpus)
    restored = cr.restore_corpus(tenant_id="demo_store", environment="TEST")
    # Existing result artifact only. No DEV question/answer dataset is opened.
    result = json.loads((cr.ROOT / (
        "artifacts/experiments/OPS-RAG-01/r05_retrieval_result.json"
    )).read_bytes())
    source_index = {(s["source_id"], s["version"]): s for s in sources}
    chunk_index = {(c["source_id"], c["version"], c["chunk_id"]): c for c in chunks}
    evidence = None
    for row in result["rows"]:
        if row["method"] != handoff["selection"]["method"] or not row["executed"]:
            continue
        for citation in row["top5"]:
            key = (citation["source_id"], citation["version"])
            source = source_index.get(key)
            chunk = chunk_index.get((*key, citation["chunk_id"]))
            if source is None or chunk is None or source["source_type"] not in cr.ALLOWED_TYPES:
                continue
            if chunk["text"] == source["content"]:
                continue
            evidence = {
                "case_id": row["case_id"], "method": row["method"],
                "source_id": key[0], "version": key[1],
                "semantic_chunk_id": citation["chunk_id"],
                "semantic_excerpt_hash": cr._hash(chunk["text"]),
                "source_content_hash": cr._hash(source["content"]),
                "hash_origin": "computed from existing artifact UTF-8 text; result has no hashes",
                "source_version_exists": True, "semantic_chunk_exists": True,
                "c04_projection_exists": False, "mapping": None,
                "status": restored.status,
            }
            if restored.status == "READY":
                mapping = restored.resolve(
                    tenant_id="demo_store", source_id=key[0], version=key[1],
                    semantic_chunk_id=citation["chunk_id"],
                    semantic_excerpt_hash=evidence["semantic_excerpt_hash"],
                )
                evidence["mapping"] = asdict(mapping)
                evidence["c04_projection_exists"] = True
            break
        if evidence:
            break
    smoke = []
    for generation in (1, 2):
        app = create_app(Settings(_env_file=None, environment="TEST", database_url="sqlite://"))
        with TestClient(app) as client:
            for source_id, version in (
                ("product_demo_long_003", "v1"), ("policy_shipping_demo", "v2"),
                ("inventory_snapshot_demo_sku_001", "v1"),
                ("incoming_stock_demo_confirmed_001", "v1"),
            ):
                response = client.get("/api/v1/c04/lookup", params={
                    "source_id": source_id, "version": version,
                })
                body = response.json()
                smoke.append({"app_generation": generation, "http_status": response.status_code,
                              "tenant_id": body.get("tenant_id"), "data": body.get("data")})
    report = {
        "canonical_snapshot": str(cr.SNAPSHOT_PATH),
        "canonical_manifest": str(cr.MANIFEST_PATH),
        "snapshot_version": manifest["snapshot_version"],
        "snapshot_file_sha256": sha256(snapshot).hexdigest(),
        "manifest_snapshot_hash": manifest["snapshot_hash"],
        "corpus_sha256": sha256(corpus).hexdigest(),
        "selection": handoff["selection"],
        "documents": len(sources), "chunks": len(chunks),
        "source_type_counts": dict(Counter(s["source_type"] for s in sources)),
        "chunk_type_counts": dict(Counter(c["source_type"] for c in chunks)),
        "manifest_created_at": manifest.get("created_at"),
        "restore_status": restored.status, "restore_error": restored.error,
        "existing_dev_evidence_check": evidence,
        "file_reload_endpoint_smoke": smoke,
        "retrieval_executed": False,
    }
    expected_paths = json.loads((cr.ROOT / "contracts/snapshots/openapi_signature.json")
                               .read_bytes())["paths"]
    report["existing_openapi_path_drift"] = sorted(
        set(app.openapi()["paths"]) - set(expected_paths)
    )
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
