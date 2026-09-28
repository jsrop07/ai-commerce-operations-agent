"""Exact lookup over explicitly injected, trusted safe Demo projections.

No corpus discovery, file/URL loading, AI imports, or retrieval. CLEAN is an
upstream attestation, not a PII detector. Only synthetic data is supported.
"""

import re
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from threading import Lock
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")]
SourceType = Literal["PRODUCT", "POLICY", "INVENTORY_SNAPSHOT", "INCOMING_STOCK"]
# Demo initial TTLs match ai/retrieval/freshness.yaml; not production SLAs.
LIVE_TTL_SECONDS = {"INVENTORY_SNAPSHOT": 300, "INCOMING_STOCK": 3600}
SENSITIVE_REFERENCE = re.compile(
    r"\b(?:affected_order_ids|reservation_id|order_status|"
    r"(?:order|order_line|customer|shipping|payment|inquiry)_ids?)\b|"
    r"[\"']?\b(?:order|order_line|customer|shipping|payment|inquiry)"
    r"\b[\"']?\s*[:=]",
    re.IGNORECASE,
)


class SafeDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(min_length=1)
    source_id: Identifier
    source_type: SourceType
    title: str = Field(min_length=1)
    version: Identifier
    as_of: AwareDatetime | None
    pii_status: Literal["CLEAN"]
    content: str = Field(min_length=1, max_length=16000)
    data_mode: Literal["SYNTHETIC_DEMO"]
    visibility: Literal["DEMO_PUBLIC"]
    stale: bool = False

    @model_validator(mode="after")
    def require_live_timestamp(self):
        if self.source_type in LIVE_TTL_SECONDS and self.as_of is None:
            raise ValueError("Live source requires as_of")
        return self


class LookupResult(BaseModel):
    source_id: str
    source_type: SourceType
    title: str
    version: str
    as_of: AwareDatetime | None
    data_mode: Literal["SYNTHETIC_DEMO"]
    visibility: Literal["DEMO_PUBLIC"]
    chunk_id: str
    excerpt: str
    excerpt_hash: str
    stale: bool
    warnings: list[str]
    # Lookup alone never authorizes an answer, including for fresh documents.
    definitive_answer_allowed: Literal[False] = False


class LookupFailure(Exception):
    def __init__(self, status_code: int, code: str):
        self.status_code = status_code
        self.code = code
        super().__init__(code)


class C04LookupService:
    """A private snapshot; () is empty, None explicitly means unavailable.

    Records must be pre-reviewed synthetic projections, with no order-linked
    data. Unknown fields are denied, never automatically inherited as AI keys.
    """

    def __init__(self, records: tuple[dict, ...] | list[dict] | None = ()):
        self._registration_lock = Lock()
        self._records = None if records is None else {}
        for record in records or ():
            key = (record["tenant_id"], record["source_id"], record["version"])
            if key in self._records:
                raise ValueError("Duplicate C04 record identity")
            self._records[key] = deepcopy(record)

    @staticmethod
    def _safe_document(raw: dict) -> SafeDocument:
        try:
            document = SafeDocument.model_validate(raw)
        except ValidationError:
            raise LookupFailure(403, "C04_RECORD_BLOCKED") from None
        if any(SENSITIVE_REFERENCE.search(value) for value in (
            document.source_id, document.title, document.content,
        )):
            raise LookupFailure(403, "C04_RECORD_BLOCKED")
        return document

    def register_demo_record(
        self, record: dict, *, environment: str, tenant_id: str,
    ) -> LookupResult:
        """Append a validated Demo projection; never replace an existing version."""
        if environment != "DEMO":
            raise LookupFailure(403, "C04_DEMO_ONLY")
        document = self._safe_document(record)
        if document.tenant_id != tenant_id:
            raise LookupFailure(403, "C04_RECORD_BLOCKED")
        key = (tenant_id, document.source_id, document.version)
        with self._registration_lock:
            if self._records is None:
                raise LookupFailure(503, "C04_REGISTRY_UNAVAILABLE")
            previous = self._records.get(key)
            if previous is not None and self._safe_document(previous) != document:
                raise LookupFailure(409, "C04_VERSION_CONFLICT")
            if previous is None:
                self._records[key] = document.model_dump()
        return self.lookup(tenant_id=tenant_id, source_id=document.source_id,
                           version=document.version)

    def lookup(
        self, *, tenant_id: str, source_id: str, version: str,
        chunk_id: str | None = None, now: datetime | None = None,
    ) -> LookupResult:
        if self._records is None:
            raise LookupFailure(503, "C04_REGISTRY_UNAVAILABLE")
        raw = self._records.get((tenant_id, source_id, version))
        # Missing source, foreign tenant and mismatched version are indistinguishable.
        if raw is None:
            raise LookupFailure(404, "C04_NOT_FOUND")
        document = self._safe_document(raw)
        # One whole-content projection. Do not impersonate AI semantic chunk IDs.
        expected_chunk = f"{source_id}:{version}:c04:0"
        if chunk_id is not None and chunk_id != expected_chunk:
            raise LookupFailure(404, "C04_CHUNK_NOT_FOUND")
        age = (None if document.as_of is None else
               ((now or datetime.now(UTC)) - document.as_of).total_seconds())
        ttl = LIVE_TTL_SECONDS.get(document.source_type)
        stale = document.stale or (
            age is not None and (age < 0 or (ttl is not None and age > ttl))
        )
        warnings = ["C04_STALE: refresh or review; not definitive answer evidence"] if stale else []
        return LookupResult(
            source_id=document.source_id, source_type=document.source_type,
            title=document.title, version=document.version, as_of=document.as_of,
            data_mode=document.data_mode, visibility=document.visibility,
            chunk_id=expected_chunk, excerpt=document.content,
            excerpt_hash=f"sha256:{sha256(document.content.encode('utf-8')).hexdigest()}",
            stale=stale, warnings=warnings,
        )
