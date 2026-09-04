"""Common API success and error envelopes."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ApiEnvelope(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    tenant_id: str
    request_id: str
    trace_id: str
    data: T
    evidence_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    as_of: datetime


class ErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool
    details: dict[str, object] = Field(default_factory=dict)


class ApiError(BaseModel):
    error: ErrorBody
    request_id: str
    trace_id: str
