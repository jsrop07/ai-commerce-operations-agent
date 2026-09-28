"""Read-only safe corpus lookup using server tenant context, not user auth."""

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import AwareDatetime, BaseModel

from backend.app.services.c04_lookup import (
    C04LookupService,
    Identifier,
    LookupFailure,
    LookupResult,
)
from contracts.api import ApiEnvelope

router = APIRouter(prefix="/api/v1", tags=["c04"])


class LookupError(BaseModel):
    detail: str


class C04Envelope(ApiEnvelope[LookupResult]):
    as_of: AwareDatetime | None


@router.get(
    "/c04/lookup",
    response_model=C04Envelope,
    responses={
        403: {"model": LookupError, "description": "Unsafe or inaccessible record"},
        404: {"model": LookupError, "description": "Source/version/tenant/chunk not found"},
        503: {"model": LookupError, "description": "Registry unavailable"},
    },
    description=(
        "Exact synthetic corpus lookup. Server settings tenant only; no user authentication. "
        "Omit chunk_id for the sole source_id:version:c04:0 projection. "
        "SHA-256 hashes exact UTF-8 excerpt bytes. No search or external reads."
    ),
)
def lookup_document(
    request: Request,
    source_id: Annotated[Identifier, Query()],
    version: Annotated[Identifier, Query()],
    chunk_id: Annotated[str | None, Query(min_length=1, max_length=300)] = None,
) -> C04Envelope:
    service = getattr(request.app.state, "c04_lookup_service", None)
    if not isinstance(service, C04LookupService):
        raise HTTPException(status_code=503, detail="C04_REGISTRY_UNAVAILABLE")
    tenant_id = request.app.state.settings.tenant_id
    try:
        result = service.lookup(
            tenant_id=tenant_id, source_id=source_id, version=version, chunk_id=chunk_id,
        )
    except LookupFailure as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.code) from None
    return C04Envelope(
        tenant_id=tenant_id,
        request_id=request.headers.get("x-request-id", f"req_{uuid4().hex}"),
        trace_id=request.headers.get("x-trace-id", f"tr_{uuid4().hex}"),
        data=result, as_of=result.as_of, warnings=result.warnings,
    )
