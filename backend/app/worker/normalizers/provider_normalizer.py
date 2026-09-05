"""Day 6 provider DTO normalization boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True)
class NormalizedRecord:
    provider: str
    resource: str
    status: str
    identity: str | None
    canonical: dict[str, Any] | None
    unknown: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _decimal_or_none(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None

    try:
        return str(Decimal(text.replace(",", "")))
    except (InvalidOperation, ValueError):
        return None


def normalize_cafe24_product_export(
    row: dict[str, Any],
) -> NormalizedRecord:
    """Normalize a sanitized Cafe24 product-export row."""

    product_id = _text(row.get("상품코드"))
    name = _text(row.get("상품명"))

    if product_id is None:
        return NormalizedRecord(
            provider="CAFE24",
            resource="product",
            status="QUARANTINED",
            identity=None,
            canonical=None,
            unknown={},
            reason="MISSING_PRODUCT_CODE",
        )

    if name is None:
        return NormalizedRecord(
            provider="CAFE24",
            resource="product",
            status="QUARANTINED",
            identity=product_id,
            canonical=None,
            unknown={},
            reason="MISSING_PRODUCT_NAME",
        )

    known_fields = {
        "상품코드",
        "자체 상품코드",
        "상품명",
        "영문 상품명",
        "상품명(관리용)",
        "공급사 상품명",
        "모델명",
        "상품분류 번호",
        "브랜드",
        "브랜드명",
        "제조사",
        "제조사명",
        "진열상태",
        "판매상태",
        "자체분류 코드",
        "옵션사용",
        "옵션세트명",
        "출시일자",
        "검색어설정",
        "상품 요약설명",
        "상품 간략설명",
        "판매가",
        "소비자가",
        "이미지등록(상세)",
        "이미지등록(목록)",
        "이미지등록(작은목록)",
        "이미지등록(축소)",
    }

    unknown = {
        key: value
        for key, value in row.items()
        if key not in known_fields
    }

    canonical = {
        "provider_product_id": product_id,
        "name": name,
        "external_sku_candidate": _text(row.get("자체 상품코드")),
        "english_name": _text(row.get("영문 상품명")),
        "management_name": _text(row.get("상품명(관리용)")),
        "supplier_name": _text(row.get("공급사 상품명")),
        "model_name": _text(row.get("모델명")),
        "category_source": _text(row.get("상품분류 번호")),
        "brand_code": _text(row.get("브랜드")),
        "brand_name": _text(row.get("브랜드명")),
        "manufacturer_code": _text(row.get("제조사")),
        "manufacturer_name": _text(row.get("제조사명")),
        "display_status": _text(row.get("진열상태")),
        "sale_status": _text(row.get("판매상태")),
        "custom_category_code": _text(row.get("자체분류 코드")),
        "option_used": _text(row.get("옵션사용")),
        "option_set_name": _text(row.get("옵션세트명")),
        "release_date_raw": _text(row.get("출시일자")),
        "search_alias_raw": _text(row.get("검색어설정")),
        "summary": _text(row.get("상품 요약설명")),
        "short_description": _text(row.get("상품 간략설명")),
        "sale_price": _decimal_or_none(row.get("판매가")),
        "retail_price": _decimal_or_none(row.get("소비자가")),
        "images": {
            "detail": _text(row.get("이미지등록(상세)")),
            "list": _text(row.get("이미지등록(목록)")),
            "small_list": _text(row.get("이미지등록(작은목록)")),
            "thumbnail": _text(row.get("이미지등록(축소)")),
        },
    }

    return NormalizedRecord(
        provider="CAFE24",
        resource="product",
        status="NORMALIZED",
        identity=product_id,
        canonical=canonical,
        unknown=unknown,
    )