"""Build the Day 9 AI catalog handoff from protected sanitized data only.

This module deliberately has no Cafe24 adapter or HTTP client dependency.  It
projects current catalog metadata for a later AI consumer; current category
membership is never historical reservation evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.services.category_product_projection import (
    CURRENT_CATEGORY_EVIDENCE,
    CategoryProductMembership,
    CategoryRecord,
    ProductRecord,
    project_catalog_products,
    project_category_scope,
)

SCHEMA_VERSION = "day09-ai-catalog-handoff.v1"
ARTIFACT_VERSION = "1.0.0"
SOURCE_CLASSIFICATION = "SANITIZED_REAL"
HISTORICAL_RESERVATION_WARNING = (
    "Current category membership must not be used as proof of historical "
    "preorder status."
)
DEFAULT_PROTECTED_ROOT = Path(r"C:\ai-commerce-private\cafe24")
DEFAULT_OUTPUT_DIR = Path("artifacts/integration/day09")

_FORBIDDEN_KEYS = {
    "customer_name",
    "buyer_name",
    "recipient_name",
    "receiver_name",
    "email",
    "phone",
    "mobile",
    "address",
    "zipcode",
    "payment_information",
    "customer_id",
    "member_id",
    "access_token",
    "refresh_token",
    "client_secret",
    "authorization",
    "cookie",
}
_PII_PATTERNS = (
    re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE),
    re.compile(r"(?<!\d)01[016789][ -]?\d{3,4}[ -]?\d{4}(?!\d)"),
)
_SECRET_PATTERNS = (
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)


@dataclass(frozen=True)
class Day09AICatalogHandoffResult:
    artifact_path: Path
    validation_path: Path
    manifest_path: Path
    artifact_hash: str
    product_observation_count: int
    product_count: int
    category_count: int
    product_category_relation_count: int
    validation_passed: bool


@dataclass(frozen=True)
class _Observation:
    record: dict[str, Any]
    batch_id: str
    file_name: str
    file_sha256: str
    sequence: int


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _as_positive_int(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if parsed < 1:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _batch_datetime(batch_id: str) -> datetime | None:
    match = re.search(r"(\d{8}T\d{12}Z)", batch_id)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%dT%H%M%S%fZ").replace(
            tzinfo=UTC
        )
    except ValueError:
        return None


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _observation_datetime(observation: _Observation) -> datetime:
    record = observation.record
    return (
        _parse_datetime(record.get("updated_date"))
        or _parse_datetime(record.get("as_of"))
        or _parse_datetime(record.get("created_date"))
        or _batch_datetime(observation.batch_id)
        or datetime(1970, 1, 1, tzinfo=UTC)
    )


def _load_observations(
    directory: Path,
    *,
    preferred_glob: str,
) -> tuple[list[_Observation], int]:
    files = sorted(directory.glob(preferred_glob))
    if not files:
        files = sorted(directory.glob("*.sanitized.json"))
    if not files:
        raise FileNotFoundError(f"no sanitized snapshots in {directory}")

    observations: list[_Observation] = []
    for path in files:
        encoded = path.read_bytes()
        payload = json.loads(encoded.decode("utf-8"))
        if payload.get("resource") != directory.name:
            raise ValueError(f"unexpected resource in {path.name}")
        records = payload.get("records")
        if not isinstance(records, list):
            raise ValueError(f"records must be a list in {path.name}")
        batch_id = str(payload.get("batch_id") or path.stem)
        digest = _sha256_bytes(encoded)
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise ValueError(f"record must be an object in {path.name}")
            observations.append(
                _Observation(record, batch_id, path.name, digest, index)
            )
    return observations, len(files)


def _latest_by_identity(
    observations: Iterable[_Observation],
    *,
    identity_field: str,
) -> dict[int, _Observation]:
    selected: dict[int, _Observation] = {}
    for observation in observations:
        identity = _as_positive_int(
            observation.record.get(identity_field), identity_field
        )
        prior = selected.get(identity)
        if prior is None or (
            _observation_datetime(observation),
            observation.batch_id,
            observation.file_name,
            observation.sequence,
        ) > (
            _observation_datetime(prior),
            prior.batch_id,
            prior.file_name,
            prior.sequence,
        ):
            selected[identity] = observation
    return selected


def _evidence_id(resource: str, observation: _Observation, identity: str) -> str:
    existing = observation.record.get("evidence_id")
    if isinstance(existing, str) and existing:
        return existing
    return f"cafe24-sanitized:{resource}:{observation.file_sha256}:{identity}"


def _provenance(resource: str, observation: _Observation) -> dict[str, object]:
    existing = observation.record.get("provenance")
    result: dict[str, object] = {
        "provider": "CAFE24",
        "resource": resource,
        "batch_id": observation.batch_id,
        "sanitized_sha256": observation.file_sha256,
    }
    if isinstance(existing, dict):
        for key in ("provider", "resource", "batch_id", "raw_sha256"):
            value = existing.get(key)
            if value is not None:
                result[key] = value
    return result


def _scan_payload(payload: object) -> tuple[list[str], list[str]]:
    pii_matches: list[str] = []
    secret_matches: list[str] = []

    def visit(value: object, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                if str(key).lower() in _FORBIDDEN_KEYS:
                    secret_matches.append(child_path)
                visit(child, child_path)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")
        elif isinstance(value, str):
            if any(pattern.search(value) for pattern in _PII_PATTERNS):
                pii_matches.append(path)
            if any(pattern.search(value) for pattern in _SECRET_PATTERNS):
                secret_matches.append(path)

    visit(payload, "")
    return sorted(set(pii_matches)), sorted(set(secret_matches))


def build_day09_ai_catalog_handoff(
    *,
    protected_root: Path = DEFAULT_PROTECTED_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    preorder_category_no: int = 56,
) -> Day09AICatalogHandoffResult:
    """Create deterministic Day 9 catalog and validation artifacts."""

    sanitized_root = protected_root / "cafe24" / "sanitized"
    product_observations, product_snapshot_file_count = _load_observations(
        sanitized_root / "products", preferred_glob="product-full-*.sanitized.json"
    )
    category_observations, category_snapshot_file_count = _load_observations(
        sanitized_root / "categories", preferred_glob="category-full-*.sanitized.json"
    )
    relation_observations, relation_snapshot_file_count = _load_observations(
        sanitized_root / "category_product_relations",
        preferred_glob="category-products-snapshot-*.sanitized.json",
    )

    products_by_no = _latest_by_identity(
        product_observations, identity_field="product_no"
    )
    categories_by_no = _latest_by_identity(
        category_observations, identity_field="category_no"
    )

    relations_by_identity: dict[tuple[int, int], _Observation] = {}
    for observation in relation_observations:
        category_no = _as_positive_int(
            observation.record.get("category_no"), "category_no"
        )
        product_no = _as_positive_int(
            observation.record.get("product_no"), "product_no"
        )
        key = (category_no, product_no)
        prior = relations_by_identity.get(key)
        if prior is None or (
            _observation_datetime(observation), observation.file_name
        ) > (_observation_datetime(prior), prior.file_name):
            relations_by_identity[key] = observation

    product_records: list[ProductRecord] = []
    for product_no, observation in sorted(products_by_no.items()):
        evidence_id = _evidence_id("products", observation, str(product_no))
        product_records.append(
            ProductRecord(
                product_no=product_no,
                display=observation.record.get("display"),
                selling=observation.record.get("selling"),
                sold_out=observation.record.get("sold_out"),
                as_of=_observation_datetime(observation),
                source_classification=SOURCE_CLASSIFICATION,
                evidence_ids=(evidence_id,),
            )
        )

    category_records: list[CategoryRecord] = []
    category_evidence: dict[int, str] = {}
    for category_no, observation in sorted(categories_by_no.items()):
        evidence_id = _evidence_id("categories", observation, str(category_no))
        category_evidence[category_no] = evidence_id
        parent_value = observation.record.get("parent_category_no")
        parent_no = int(parent_value) if parent_value not in (None, "", 0, "0") else None
        category_records.append(
            CategoryRecord(
                category_no=category_no,
                parent_category_no=parent_no,
                as_of=_observation_datetime(observation),
                source_classification=SOURCE_CLASSIFICATION,
                evidence_ids=(evidence_id,),
            )
        )

    memberships: list[CategoryProductMembership] = []
    relation_rows: list[dict[str, object]] = []
    for (category_no, product_no), observation in sorted(relations_by_identity.items()):
        if product_no not in products_by_no:
            raise ValueError(f"relation references unknown product {product_no}")
        if category_no not in categories_by_no:
            raise ValueError(f"relation references unknown category {category_no}")
        evidence_type = observation.record.get("evidence_type")
        if evidence_type != CURRENT_CATEGORY_EVIDENCE:
            raise ValueError("relation is not CURRENT_CATEGORY_EVIDENCE")
        source = observation.record.get("source_classification")
        if source != SOURCE_CLASSIFICATION:
            raise ValueError("relation is not SANITIZED_REAL")
        evidence_id = _evidence_id(
            "category_product_relations", observation, f"{category_no}:{product_no}"
        )
        as_of = _observation_datetime(observation)
        memberships.append(
            CategoryProductMembership(
                category_no=category_no,
                product_no=product_no,
                as_of=as_of,
                source_classification=str(source),
                evidence_ids=(evidence_id,),
                evidence_type=str(evidence_type),
            )
        )
        relation_rows.append(
            {
                "as_of": _iso(as_of),
                "category_no": category_no,
                "evidence_id": evidence_id,
                "evidence_type": CURRENT_CATEGORY_EVIDENCE,
                "product_no": product_no,
                "provenance": _provenance("category_product_relations", observation),
                "source_classification": str(source),
            }
        )

    projections = project_catalog_products(
        products=tuple(product_records), memberships=tuple(memberships)
    )
    projection_by_no = {item.product_no: item for item in projections}

    product_rows: list[dict[str, object]] = []
    for product_no, observation in sorted(products_by_no.items()):
        record = observation.record
        projection = projection_by_no[product_no]
        product_rows.append(
            {
                "as_of": _iso(projection.as_of),
                "brand_code": record.get("brand_code"),
                "category_nos": list(projection.category_nos),
                "category_status": projection.category_status,
                "custom_product_code": record.get("custom_product_code"),
                "display": projection.display,
                "evidence_ids": list(projection.evidence_ids),
                "operational": projection.operational,
                "product_code": record.get("product_code"),
                "product_name": record.get("product_name"),
                "product_no": product_no,
                "provenance": [_provenance("products", observation)],
                "selling": projection.selling,
                "sold_out": projection.sold_out,
                "source_classification": SOURCE_CLASSIFICATION,
            }
        )

    category_rows: list[dict[str, object]] = []
    for category_no, observation in sorted(categories_by_no.items()):
        record = observation.record
        category_rows.append(
            {
                "as_of": _iso(_observation_datetime(observation)),
                "category_depth": record.get("category_depth"),
                "category_name": record.get("category_name"),
                "category_no": category_no,
                "evidence_ids": [category_evidence[category_no]],
                "parent_category_no": (
                    int(record["parent_category_no"])
                    if record.get("parent_category_no") not in (None, "", 0, "0")
                    else None
                ),
                "provenance": [_provenance("categories", observation)],
                "source_classification": SOURCE_CLASSIFICATION,
            }
        )

    scopes = {
        category_no: project_category_scope(
            category_no=category_no,
            categories=tuple(category_records),
            memberships=tuple(memberships),
        )
        for category_no in (46, 56, 57, 67)
    }
    operational_count = sum(bool(row["operational"]) for row in product_rows)
    categorized_count = sum(row["category_status"] == "CATEGORIZED" for row in product_rows)
    uncategorized_operational_count = sum(
        row["category_status"] == "UNCATEGORIZED" and bool(row["operational"])
        for row in product_rows
    )
    multi_category_count = sum(len(row["category_nos"]) > 1 for row in product_rows)
    max_categories = max((len(row["category_nos"]) for row in product_rows), default=0)
    preorder_product_nos = set(scopes[preorder_category_no].direct_product_nos)
    preorder_rows = [row for row in product_rows if row["product_no"] in preorder_product_nos]

    product_as_of = max(record.as_of for record in product_records)
    category_as_of = max(record.as_of for record in category_records)
    relation_as_of = max(membership.as_of for membership in memberships)
    generated_at = max(product_as_of, category_as_of, relation_as_of)

    payload: dict[str, object] = {
        "artifact_version": ARTIFACT_VERSION,
        "category_count": len(category_rows),
        "category_product_relation_count": len(relation_rows),
        "category_snapshot_as_of": _iso(category_as_of),
        "category_snapshot_file_count": category_snapshot_file_count,
        "categorized_product_count": categorized_count,
        "categories": category_rows,
        "category_product_relations": relation_rows,
        "generated_at": _iso(generated_at),
        "historical_reservation_warning": HISTORICAL_RESERVATION_WARNING,
        "identity_rule": "product_no; relation identity is (category_no, product_no)",
        "latest_observation_rule": (
            "updated_date, then as_of, then created_date, then batch timestamp; "
            "stable batch/file/record order breaks ties"
        ),
        "max_categories_per_product": max_categories,
        "multi_category_product_count": multi_category_count,
        "non_operational_product_count": len(product_rows) - operational_count,
        "operational_product_count": operational_count,
        "preorder_category_no": preorder_category_no,
        "preorder_operational_product_count": sum(
            bool(row["operational"]) for row in preorder_rows
        ),
        "preorder_relation_product_count": len(preorder_rows),
        "preorder_sold_out_product_count": sum(
            row["sold_out"] == "T" for row in preorder_rows
        ),
        "product_count": len(product_rows),
        "product_observation_count": len(product_observations),
        "product_snapshot_as_of": _iso(product_as_of),
        "product_snapshot_file_count": product_snapshot_file_count,
        "products": product_rows,
        "recursive_category_scopes": {
            str(category_no): {
                "category_no": category_no,
                "descendant_category_nos": list(scope.descendant_category_nos),
                "direct_product_count": scope.direct_product_count,
                "recursive_product_count": scope.recursive_product_count,
            }
            for category_no, scope in sorted(scopes.items())
        },
        "relation_snapshot_as_of": _iso(relation_as_of),
        "relation_snapshot_file_count": relation_snapshot_file_count,
        "safety": {
            "cafe24_api_call_count": 0,
            "customer_pii_included": False,
            "external_network_call_count": 0,
            "oauth_call_count": 0,
            "production_provider_write_count": 0,
            "raw_data_included": False,
        },
        "schema_version": SCHEMA_VERSION,
        "source_classification": SOURCE_CLASSIFICATION,
        "uncategorized_operational_product_count": uncategorized_operational_count,
        "uncategorized_product_count": len(product_rows) - categorized_count,
    }

    pii_matches, secret_matches = _scan_payload(payload)
    if pii_matches:
        raise ValueError(f"PII scan failed at {pii_matches[0]}")
    if secret_matches:
        raise ValueError(f"secret scan failed at {secret_matches[0]}")

    artifact_hash = _sha256_bytes(_canonical_bytes(payload))
    payload["artifact_hash"] = artifact_hash
    artifact_path = output_dir / "ai_catalog_handoff.json"
    validation_path = output_dir / "ai_catalog_handoff_validation.json"
    manifest_path = output_dir / "ai_catalog_handoff_manifest.json"
    _write_json(artifact_path, payload)

    actual = {
        "unique_products": len(product_rows),
        "operational_products": operational_count,
        "non_operational_products": len(product_rows) - operational_count,
        "categorized_products": categorized_count,
        "uncategorized_products": len(product_rows) - categorized_count,
        "uncategorized_operational_products": uncategorized_operational_count,
        "multi_category_products": multi_category_count,
        "max_categories_per_product": max_categories,
        "distinct_categories": len(category_rows),
        "preorder_direct_products": len(preorder_rows),
        "preorder_operational_products": sum(bool(row["operational"]) for row in preorder_rows),
        "preorder_sold_out_products": sum(row["sold_out"] == "T" for row in preorder_rows),
        "recursive_46_products": scopes[46].recursive_product_count,
        "recursive_57_products": scopes[57].recursive_product_count,
        "recursive_67_products": scopes[67].recursive_product_count,
    }
    expected = {
        "unique_products": 2167,
        "operational_products": 2019,
        "non_operational_products": 148,
        "categorized_products": 2132,
        "uncategorized_products": 35,
        "uncategorized_operational_products": 8,
        "multi_category_products": 27,
        "max_categories_per_product": 4,
        "distinct_categories": 123,
        "preorder_direct_products": 48,
        "preorder_operational_products": 46,
        "preorder_sold_out_products": 16,
        "recursive_46_products": 570,
        "recursive_57_products": 669,
        "recursive_67_products": 364,
    }
    assertions = {
        key: {"actual": actual[key], "expected": value, "passed": actual[key] == value}
        for key, value in expected.items()
    }
    validation_passed = all(item["passed"] for item in assertions.values())
    validation_payload = {
        "artifact_hash": artifact_hash,
        "artifact_version": ARTIFACT_VERSION,
        "assertions": assertions,
        "brand_code_non_empty_count": sum(bool(row["brand_code"]) for row in product_rows),
        "external_network_call_count": 0,
        "generated_at": _iso(generated_at),
        "pii_scan": {"match_count": 0, "passed": True},
        "production_provider_write_count": 0,
        "schema_version": "day09-ai-catalog-handoff-validation.v1",
        "secret_scan": {"match_count": 0, "passed": True},
        "source_classification": SOURCE_CLASSIFICATION,
        "status": "PASSED" if validation_passed else "FAILED",
    }
    _write_json(validation_path, validation_payload)
    _write_json(
        manifest_path,
        {
            "artifact": artifact_path.name,
            "artifact_file_sha256": _sha256_file(artifact_path),
            "artifact_hash": artifact_hash,
            "generated_at": _iso(generated_at),
            "schema_version": "day09-ai-catalog-handoff-manifest.v1",
            "source_classification": SOURCE_CLASSIFICATION,
            "validation": validation_path.name,
            "validation_file_sha256": _sha256_file(validation_path),
        },
    )
    if not validation_passed:
        failures = [key for key, value in assertions.items() if not value["passed"]]
        failures_text = ", ".join(failures)
        raise ValueError(f"Day 9 catalog validation failed: {failures_text}")

    return Day09AICatalogHandoffResult(
        artifact_path=artifact_path,
        validation_path=validation_path,
        manifest_path=manifest_path,
        artifact_hash=artifact_hash,
        product_observation_count=len(product_observations),
        product_count=len(product_rows),
        category_count=len(category_rows),
        product_category_relation_count=len(relation_rows),
        validation_passed=validation_passed,
    )


if __name__ == "__main__":
    result = build_day09_ai_catalog_handoff()
    print(json.dumps(asdict(result), default=str, sort_keys=True))
