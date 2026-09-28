"""Fixed, local R05 artifact restore. No retrieval, provider access or DB writes.

The enriched snapshot supplies tenant/data mode/as_of; the hash-linked corpus
supplies full text and safety attestations. Missing metadata is never inferred.
Publication is atomic: an invalid record makes the entire registry unavailable.
"""

import json
import logging
import re
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType

from backend.app.services.c04_lookup import (
    LIVE_TTL_SECONDS,
    SENSITIVE_REFERENCE,
    C04LookupService,
    LookupFailure,
    SafeDocument,
)

ROOT = Path(__file__).resolve().parents[3]
HANDOFF_PATH = ROOT / "artifacts/handoff/c05_r05_retrieval_handoff.json"
BASE_SNAPSHOT_REL = "artifacts/experiments/OPS-RAG-01/r05_grounded_snapshot_v2.jsonl"
SNAPSHOT_REL = "artifacts/experiments/OPS-RAG-01/r05_grounded_snapshot_v3_metadata.jsonl"
CORPUS_REL = "ai/evaluation/datasets/grounded_corpus.jsonl"
MANIFEST_PATH = ROOT / (
    "artifacts/experiments/OPS-RAG-01/r05_grounded_snapshot_manifest_v3_metadata.json"
)
SNAPSHOT_PATH = ROOT / SNAPSHOT_REL
CORPUS_PATH = ROOT / CORPUS_REL
SNAPSHOT_VERSION = "r05-grounded-semantic-v3-metadata"
ALLOWED_TYPES = {"PRODUCT", "POLICY", "INVENTORY_SNAPSHOT", "INCOMING_STOCK"}
FORBIDDEN_KEYS = {
    "order_status", "order", "order_line", "customer", "shipping", "payment",
    "inquiry", "affected_order_ids", "reservation_id", "feedback", "free_memo",
}
CHUNK_KEYS = {
    "schema_version", "chunk_id", "chunk_index", "source_id", "source_type",
    "version", "text", "token_count", "sentence_start", "sentence_end", "metadata",
    "tenant_id", "data_mode", "as_of",
}
CORPUS_KEYS = set(SafeDocument.model_fields) | {"fields", "paragraphs"}


class CorpusRestoreFailure(ValueError):
    """Safe diagnostic code only; never include record bodies in logs."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CorpusRestoreFailure(code)


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "CORPUS_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _json(data: bytes):
    try:
        return json.loads(data, object_pairs_hook=_object,
                          parse_constant=lambda _: _require(False, "CORPUS_JSON_INVALID"))
    except (ValueError, UnicodeError) as exc:
        raise CorpusRestoreFailure("CORPUS_JSON_INVALID") from exc


def _read(path: Path, kind: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CorpusRestoreFailure(f"CORPUS_{kind}_UNAVAILABLE") from exc


def _rows(data: bytes) -> list[dict]:
    rows = [_json(line) for line in data.splitlines() if line.strip()]
    _require(bool(rows) and all(isinstance(row, dict) for row in rows),
             "CORPUS_RECORD_INVALID")
    return rows


def _safety(value) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _require(key.lower() not in FORBIDDEN_KEYS, "CORPUS_SENSITIVE_REFERENCE")
            _safety(key)
            _safety(item)
    elif isinstance(value, list):
        for item in value:
            _safety(item)
    elif isinstance(value, str):
        _require(not SENSITIVE_REFERENCE.search(value), "CORPUS_SENSITIVE_REFERENCE")
        _require(not re.search(r"\bfeedback\b\s*[:=]", value, re.I),
                 "CORPUS_SENSITIVE_REFERENCE")


def _hash(text: str) -> str:
    return "sha256:" + sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CitationMapping:
    source_id: str
    version: str
    semantic_chunk_id: str
    semantic_excerpt_hash: str
    c04_chunk_id: str
    c04_excerpt_hash: str
    semantic_excerpt: str
    c04_excerpt: str


@dataclass(frozen=True)
class RestoredCorpus:
    lookup_service: C04LookupService
    mappings: Mapping[tuple[str, str, str, str], CitationMapping]
    status: str
    error: str | None = None
    selection_method: str | None = None
    selection_status: str | None = None
    # Validated immutable rows for runtime construction; never re-read unverified files.
    search_rows: tuple[Mapping, ...] = ()

    def resolve(
        self, *, tenant_id: str, source_id: str, version: str,
        semantic_chunk_id: str, semantic_excerpt_hash: str,
    ) -> CitationMapping:
        if self.status != "READY":
            raise LookupFailure(503, "C04_REGISTRY_UNAVAILABLE")
        mapping = self.mappings.get((tenant_id, source_id, version, semantic_chunk_id))
        if mapping is None or mapping.semantic_excerpt_hash != semantic_excerpt_hash:
            raise LookupFailure(404, "C04_MAPPING_NOT_FOUND")
        return mapping


def _validate_bundle(
    *, handoff: dict, manifest: dict, snapshot_bytes: bytes, corpus_bytes: bytes,
    tenant_id: str,
) -> RestoredCorpus:
    """Pure validator; runtime callers cannot supply paths."""
    _require(handoff["handoff_id"] == "C05-R05-RETRIEVAL", "CORPUS_HANDOFF_INVALID")
    dataset = handoff["dataset"]
    selection = handoff["selection"]
    _require(all(isinstance(selection[key], str) and selection[key]
                 for key in ("method", "status")), "CORPUS_SELECTION_INVALID")
    enrichment = manifest["metadata_enrichment"]
    _require(dataset["snapshot_path"].replace("\\", "/") == BASE_SNAPSHOT_REL
             == enrichment["base_snapshot_path"].replace("\\", "/")
             and dataset["corpus_path"].replace("\\", "/") == CORPUS_REL
             and manifest["corpus"]["path"].replace("\\", "/") == CORPUS_REL,
             "CORPUS_PATH_NOT_ALLOWLISTED")
    _require(manifest["schema_version"] == "retrieval-snapshot-manifest.v1"
             and manifest["snapshot_version"] == SNAPSHOT_VERSION,
             "CORPUS_SCHEMA_UNSUPPORTED")
    _require(sha256(snapshot_bytes).hexdigest() == manifest["snapshot_file_sha256"],
             "CORPUS_SNAPSHOT_HASH_MISMATCH")
    _require(sha256(corpus_bytes).hexdigest() == dataset["corpus_sha256"]
             == manifest["corpus"]["sha256"], "CORPUS_SOURCE_HASH_MISMATCH")
    chunks, sources = _rows(snapshot_bytes), _rows(corpus_bytes)
    normalized = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True)
                           for row in chunks) + "\n"
    _require(sha256(normalized.encode("utf-8")).hexdigest() == manifest["snapshot_hash"],
             "CORPUS_MANIFEST_HASH_MISMATCH")
    _require(len(chunks) == manifest["chunking"]["chunk_count"]
             == dataset["snapshot_chunks"] and len(sources)
             == manifest["corpus"]["record_count"] == dataset["corpus_records"]
             == dataset["snapshot_documents"], "CORPUS_COUNT_MISMATCH")
    _require(enrichment["tenant_id"] == tenant_id, "CORPUS_TENANT_MISMATCH")
    provenance = {}
    for chunk in chunks:
        _require(chunk.get("source_type") in ALLOWED_TYPES, "CORPUS_SOURCE_TYPE_BLOCKED")
        _safety(chunk)
        _require(all(chunk.get(field) is not None for field in (
            "source_id", "version", "tenant_id", "data_mode",
        )) and "as_of" in chunk, "SOURCE_METADATA_INCOMPLETE")
        _require(chunk["tenant_id"] == tenant_id, "CORPUS_TENANT_MISMATCH")
        _require(chunk["data_mode"] == "SYNTHETIC_DEMO", "CORPUS_METADATA_MISMATCH")
        _require(chunk["source_type"] not in LIVE_TTL_SECONDS or chunk["as_of"] is not None,
                 "SOURCE_METADATA_INCOMPLETE")
        key = (chunk["source_id"], chunk["version"])
        values = {field: chunk[field] for field in ("tenant_id", "data_mode", "as_of")}
        _require(key not in provenance or provenance[key] == values,
                 "CORPUS_METADATA_MISMATCH")
        provenance[key] = values
    _require(dict(Counter(row["source_type"] for row in chunks))
             == enrichment["source_type_counts"], "CORPUS_COUNT_MISMATCH")
    documents = {}
    for source in sources:
        _require(source.get("source_type") in ALLOWED_TYPES, "CORPUS_SOURCE_TYPE_BLOCKED")
        _safety(source)
        _require(set(source) <= CORPUS_KEYS, "CORPUS_METADATA_UNSUPPORTED")
        _require(all(source.get(key) is not None for key in (
            "source_id", "version", "title", "content",
            "pii_status", "data_mode", "visibility",
        )) and "as_of" in source, "SOURCE_METADATA_INCOMPLETE")
        metadata = provenance.get((source["source_id"], source["version"]))
        _require(metadata is not None, "CORPUS_SOURCE_MISSING")
        _require("tenant_id" not in source or source["tenant_id"] == tenant_id,
                 "CORPUS_TENANT_MISMATCH")
        _require(source["as_of"] == metadata["as_of"]
                 and source["data_mode"] == metadata["data_mode"], "CORPUS_METADATA_MISMATCH")
        projection = {key: value for key, value in source.items()
                      if key in SafeDocument.model_fields}
        projection.update(metadata)
        document = C04LookupService._safe_document(projection)
        key = (document.source_id, document.version)
        _require(key not in documents, "CORPUS_DUPLICATE_IDENTITY")
        documents[key] = document
    _require(len({key[0] for key in documents}) == manifest["corpus"]["unique_source_count"],
             "CORPUS_COUNT_MISMATCH")
    service = C04LookupService([doc.model_dump() for doc in documents.values()])
    mappings, grouped = {}, {}
    for chunk in chunks:
        _safety(chunk)
        _require(set(chunk) == CHUNK_KEYS
                 and chunk["schema_version"] == "retrieval-chunk-snapshot.v1",
                 "CORPUS_SCHEMA_UNSUPPORTED")
        _require(chunk["source_type"] in ALLOWED_TYPES, "CORPUS_SOURCE_TYPE_BLOCKED")
        key = (chunk["source_id"], chunk["version"])
        document = documents.get(key)
        _require(document is not None, "CORPUS_SOURCE_MISSING")
        _require(chunk["source_type"] == document.source_type
                 and isinstance(chunk["metadata"], dict)
                 and chunk["metadata"].get("title") == document.title,
                 "CORPUS_METADATA_MISMATCH")
        _require(all(type(chunk[field]) is int and chunk[field] >= 0 for field in (
            "chunk_index", "sentence_start", "sentence_end", "token_count",
        )), "CORPUS_CHUNK_INVALID")
        _require(chunk["sentence_end"] > chunk["sentence_start"]
                 and chunk["token_count"] > 0 and isinstance(chunk["text"], str)
                 and bool(chunk["text"]), "CORPUS_CHUNK_INVALID")
        _require(chunk["chunk_id"] == (
            f"{document.source_id}:{document.version}:semantic:{chunk['chunk_index']}"
        ), "CORPUS_CHUNK_IDENTITY_INVALID")
        lookup = service.lookup(tenant_id=tenant_id, source_id=key[0], version=key[1])
        mapping_key = (tenant_id, *key, chunk["chunk_id"])
        _require(mapping_key not in mappings, "CORPUS_DUPLICATE_IDENTITY")
        mappings[mapping_key] = CitationMapping(
            key[0], key[1], chunk["chunk_id"], _hash(chunk["text"]),
            lookup.chunk_id, lookup.excerpt_hash,
            chunk["text"], lookup.excerpt,
        )
        grouped.setdefault(key, []).append(chunk)
    _require(set(grouped) == set(documents), "CORPUS_SOURCE_MISSING")
    for key, group in grouped.items():
        group.sort(key=lambda row: row["chunk_index"])
        _require([row["chunk_index"] for row in group] == list(range(len(group)))
                 and group[0]["sentence_start"] == 0
                 and all(a["sentence_end"] == b["sentence_start"]
                         for a, b in zip(group, group[1:], strict=False))
                 and " ".join(row["text"] for row in group) == documents[key].content,
                 "CORPUS_PROJECTION_MISMATCH")
    return RestoredCorpus(service, MappingProxyType(mappings), "READY",
                          selection_method=selection["method"],
                          selection_status=selection["status"],
                          search_rows=tuple(MappingProxyType({
                              **row, "metadata": MappingProxyType(dict(row["metadata"])),
                          }) for row in chunks))


def restore_corpus(*, tenant_id: str, environment: str) -> RestoredCorpus:
    """Only the fixed server allowlist is read, once per application creation."""
    if environment not in {"DEMO", "LOCAL", "TEST"}:
        return RestoredCorpus(C04LookupService(None), MappingProxyType({}), "DISABLED",
                              "CORPUS_DEMO_ONLY")
    try:
        return _validate_bundle(
            handoff=_json(_read(HANDOFF_PATH, "HANDOFF")),
            manifest=_json(_read(MANIFEST_PATH, "MANIFEST")),
            snapshot_bytes=_read(SNAPSHOT_PATH, "SNAPSHOT"),
            corpus_bytes=_read(CORPUS_PATH, "SOURCE"), tenant_id=tenant_id,
        )
    except (CorpusRestoreFailure, LookupFailure, KeyError, TypeError, AttributeError) as exc:
        code = (str(exc) if isinstance(exc, (CorpusRestoreFailure, LookupFailure))
                else "CORPUS_METADATA_INVALID")
        logging.getLogger(__name__).error("C04 restore unavailable: %s", code)
        status = "BLOCKED_BY_METADATA" if code == "SOURCE_METADATA_INCOMPLETE" else "UNAVAILABLE"
        return RestoredCorpus(C04LookupService(None), MappingProxyType({}), status, code)
