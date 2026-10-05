"""Allowlisted C09 VIEW context snapshot; no DOM or arbitrary request body capture."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.app.worker.privacy.text_redaction import EMAIL_PATTERN, ORDER_ID_PATTERN, PHONE_PATTERN

ViewPage = Literal["PRODUCT_INVENTORY", "ORDERS_SALES"]
VIEW_SNAPSHOT_KEY = "c09_view_context_v1"


class ViewFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selling: bool | None = None
    sold_out: bool | None = None
    major_category: str | None = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9가-힣 &()_.-]+$"
    )


class ViewDateRange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_date: datetime
    to_date: datetime

    @model_validator(mode="after")
    def valid_range(self):
        if self.from_date.tzinfo is None or self.to_date.tzinfo is None:
            raise ValueError("date_range requires timezone-aware timestamps")
        if self.from_date > self.to_date:
            raise ValueError("date_range must be ordered")
        return self


class ViewSort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by: Literal["cafe24_product_no", "sale_price", "as_of"]
    direction: Literal["asc", "desc"]


class ViewContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["VIEW"]
    page: ViewPage
    filters: ViewFilters = Field(default_factory=ViewFilters)
    search: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9가-힣 &()_.-]*$")
    date_range: ViewDateRange | None = None
    sort: ViewSort | None = None

    @field_validator("search")
    @classmethod
    def safe_search(cls, value: str | None) -> str | None:
        if value and (
            EMAIL_PATTERN.search(value)
            or PHONE_PATTERN.search(value)
            or ORDER_ID_PATTERN.search(value)
            or any(token in value.lower() for token in (
                "order_id", "order_item_id", "order_line_id", "customer_id", "inquiry"
            ))
        ):
            raise ValueError("forbidden view search")
        return value

    @model_validator(mode="after")
    def safe_category(self):
        category = self.filters.major_category
        if category and any(token in category.lower() for token in (
            "order_id", "customer_id", "inquiry", "payment", "shipping"
        )):
            raise ValueError("forbidden view category")
        return self

    def snapshot(self) -> dict:
        return self.model_dump(mode="json", exclude_none=True)
