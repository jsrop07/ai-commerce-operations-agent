"""Allowlisted Backend-to-AI SKU aggregate contract."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_FORBIDDEN_EVIDENCE_TOKENS = (
    "order_id",
    "order_item_id",
    "order_line_id",
    "customer_id",
    "shipping",
    "payment",
    "inquiry",
    "free_memo",
    "transaction_timestamp",
    "source_order_url",
    "order_lookup",
)


class AiSkuAggregate(BaseModel):
    """Customer-unlinked, SKU-level aggregate intended for a future AI input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sku_id: str = Field(min_length=1)
    product_no: int = Field(gt=0)
    required_qty: int | None = Field(default=None, ge=0)
    expected_inventory: int | None = None
    available_inventory: int | None = None
    reserved: int | None = Field(default=None, ge=0)
    confirmed_incoming: int | None = Field(default=None, ge=0)
    calculation_status: str = Field(min_length=1)
    quality_status: str = Field(min_length=1)
    data_mode: str = Field(min_length=1)
    as_of: datetime
    evidence_ids: tuple[str, ...] = ()

    @field_validator("as_of")
    @classmethod
    def as_of_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("as_of must include timezone")
        return value

    @field_validator("evidence_ids")
    @classmethod
    def evidence_must_be_allowlisted(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for evidence_id in value:
            if not evidence_id:
                raise ValueError("evidence_ids must not contain empty values")
            lowered = evidence_id.lower()
            if any(token in lowered for token in _FORBIDDEN_EVIDENCE_TOKENS):
                raise ValueError("evidence id is not C02-safe")
        return tuple(dict.fromkeys(value))
