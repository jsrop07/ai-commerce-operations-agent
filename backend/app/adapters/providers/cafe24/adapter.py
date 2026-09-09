"""Cafe24 Day 5 읽기 전용 Adapter."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Any

from backend.app.adapters.providers.base import (
    CommerceProvider,
    ProviderNonRetryableError,
    UnsupportedCapability,
    WriteDisabledMixin,
)
from backend.app.adapters.providers.http_transport import ReadOnlyHttpTransport
from backend.app.worker.privacy.staging import (
    build_staging_record,
    sanitize_community_record,
)
from contracts.events import Provider
from contracts.providers import (
    CapabilityMatrix,
    CapabilityStatus,
    ConnectionMode,
    ProviderReadPage,
)


class Cafe24Adapter(WriteDisabledMixin, CommerceProvider):
    """Cafe24의 확정된 Read Resource만 공통 Provider 계약으로 변환한다."""

    provider = Provider.CAFE24

    PRODUCT_SCOPE = "mall.read_product"
    ORDER_SCOPE = "mall.read_order"
    CATEGORY_SCOPE = "mall.read_category"
    COMMUNITY_SCOPE = "mall.read_community"
    PAGE_SIZE = 25

    def __init__(
        self,
        *,
        mall_id: str | None = None,
        access_token: str | None = None,
        transport: ReadOnlyHttpTransport | None = None,
    ) -> None:
        self.mall_id = mall_id
        self.access_token = access_token
        self.transport = transport

    def capabilities(self) -> CapabilityMatrix:
        return CapabilityMatrix(
            provider=self.provider,
            connection_mode=ConnectionMode.CONTRACT_ONLY,
            products_read=CapabilityStatus.SUPPORTED,
            orders_read=CapabilityStatus.SUPPORTED,
            inventory_read=CapabilityStatus.VERIFY,
            inquiries_read=CapabilityStatus.VERIFY,
            incoming_stock_read=CapabilityStatus.UNKNOWN,
            inventory_write=CapabilityStatus.DISABLED_CORE,
            evidence_ref="docs/provider_capabilities/cafe24.md",
        )
    
    def _sanitize_items(
        self,
        *,
        resource: str,
        items: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Cafe24 raw item을 보호 참조와 비식별 staging 경계를 거쳐 반환한다."""

        sanitized_items: list[dict[str, Any]] = []
        raw_refs: list[str] = []

        for index, item in enumerate(items, start=1):
            staging = build_staging_record(
                provider="CAFE24",
                resource=resource,
                raw_payload=item,
                storage_ref=(
                    f"protected://cafe24/{resource}/"
                    f"request-item-{index}"
                ),
            )

            sanitized_payload = staging.sanitized_payload
            if resource in {"articles", "article_comments", "boards"}:
                sanitized_payload = sanitize_community_record(item)
            sanitized_items.append(sanitized_payload)
            raw_refs.append(staging.raw_ref.raw_sha256)

        return sanitized_items, raw_refs
    
    def verify_health(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "status": "contract_only",
        }

    def _require_transport(self) -> ReadOnlyHttpTransport:
        """승인된 Transport가 없는 상태에서는 외부 Read를 시작하지 않는다."""

        if self.transport is None:
            raise UnsupportedCapability(
                "UNSUPPORTED_CAPABILITY: Cafe24 읽기 Transport가 활성화되지 않았습니다."
            )

        if not isinstance(self.mall_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", self.mall_id):
            raise ProviderNonRetryableError(
                "Cafe24 mall_id가 설정되지 않았습니다."
            )

        return self.transport

    def _authorization_headers(self) -> dict[str, str]:
        """Access Token은 HTTP Header에서만 사용하고 로그용 값으로 반환하지 않는다."""

        if not self.access_token:
            raise ProviderNonRetryableError(
                "Cafe24 access token이 설정되지 않았습니다."
            )

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _offset_from_cursor(self, cursor: str | None) -> int:
        """Day 5에서는 Cafe24 offset 기반의 최소 Cursor만 사용한다."""

        if cursor is None:
            return 0

        prefix = "offset:"

        if not cursor.startswith(prefix):
            raise ProviderNonRetryableError(
                "Cafe24 cursor 형식이 올바르지 않습니다"
            )

        raw_offset = cursor.removeprefix(prefix)

        try:
            offset = int(raw_offset)
        except ValueError as exc:
            raise ProviderNonRetryableError(
                "Cafe24 cursor offset이 숫자가 아닙니다"
            ) from exc

        if offset < 0:
            raise ProviderNonRetryableError(
                "Cafe24 cursor offset은 음수일 수 없습니다"
            )

        return offset

    def _page(
        self,
        *,
        resource: str,
        items: list[dict[str, Any]],
        offset: int,
        paginated: bool = True,
    ) -> ProviderReadPage[dict[str, Any]]:
        """Cafe24 목록 응답을 기존 ProviderReadPage 계약으로 감싼다."""

        now = datetime.now(UTC)

        has_more = paginated and len(items) == self.PAGE_SIZE

        next_cursor = (
            f"offset:{offset + self.PAGE_SIZE}"
            if has_more
            else None
        )

        return ProviderReadPage(
            provider=self.provider,
            resource=resource,
            items=items,
            next_cursor=next_cursor,
            watermark=now,
            has_more=has_more,
            request_count=1,
            source_as_of=now,
        )

    def read_products(
        self,
        cursor: str | None = None,
    ) -> ProviderReadPage[dict[str, Any]]:
        """Cafe24 상품 목록 GET 응답을 ProviderReadPage로 반환한다."""

        transport = self._require_transport()
        offset = self._offset_from_cursor(cursor)

        url = (
            f"https://{self.mall_id}.cafe24api.com"
            "/api/v2/admin/products"
        )

        payload = transport.get(
            url=url,
            required_scopes={self.PRODUCT_SCOPE},
            headers=self._authorization_headers(),
            params={
                "limit": self.PAGE_SIZE,
                "offset": offset,
            },
        )

        if not isinstance(payload, dict):
            raise ProviderNonRetryableError(
                "Cafe24 상품 응답이 JSON Object가 아닙니다."
            )

        items = payload.get("products")

        if not isinstance(items, list):
            raise ProviderNonRetryableError(
                "Cafe24 상품 응답에 products 목록이 없습니다."
            )

        if not all(isinstance(item, dict) for item in items):
            raise ProviderNonRetryableError(
                "Cafe24 상품 응답의 products 항목이 JSON Object가 아닙니다."
            )

        sanitized_items, _ = self._sanitize_items(
            resource="products",
            items=items,
        )

        return self._page(
            resource="products",
            items=sanitized_items,
            offset=offset,
        )

    def read_variants(
        self,
        product_no: int,
        cursor: str | None = None,
    ) -> ProviderReadPage[dict[str, Any]]:
        """Cafe24 상품별 Variant 목록을 Read-Only로 조회한다."""

        if type(product_no) is not int or product_no < 1:
            raise ProviderNonRetryableError(
                "Cafe24 product_no는 1 이상이어야 합니다."
            )

        transport = self._require_transport()
        offset = self._offset_from_cursor(cursor)

        url = (
            f"https://{self.mall_id}.cafe24api.com"
            f"/api/v2/admin/products/{product_no}/variants"
        )

        payload = transport.get(
            url=url,
            required_scopes={self.PRODUCT_SCOPE},
            headers=self._authorization_headers(),
            params={
                "limit": self.PAGE_SIZE,
                "offset": offset,
            },
        )

        if not isinstance(payload, dict):
            raise ProviderNonRetryableError(
                "Cafe24 Variant 응답은 JSON Object여야 합니다."
            )

        items = payload.get("variants")

        if not isinstance(items, list):
            raise ProviderNonRetryableError(
                "Cafe24 Variant 응답에 variants 배열이 없습니다."
            )

        if not all(isinstance(item, dict) for item in items):
            raise ProviderNonRetryableError(
                "Cafe24 Variant 항목은 JSON Object여야 합니다."
            )

        variant_items = [
            {
                **item,
                "product_no": product_no,
            }
            for item in items
        ]

        sanitized_items, _ = self._sanitize_items(
            resource="variants",
            items=variant_items,
        )
        return self._page(
            resource="variants",
            items=sanitized_items,
            offset=offset,
        )

    def read_variant_inventory(
        self,
        product_no: int,
        variant_code: str,
    ) -> ProviderReadPage[dict[str, Any]]:
        """Cafe24 특정 Variant의 재고를 Read-Only로 조회한다."""

        if type(product_no) is not int or product_no < 1:
            raise ProviderNonRetryableError(
                "Cafe24 product_no는 1 이상이어야 합니다."
            )

        if not isinstance(variant_code, str):
            raise ProviderNonRetryableError("Cafe24 variant_code must be text")
        normalized_variant_code = variant_code.strip()

        if not normalized_variant_code:
            raise ProviderNonRetryableError(
                "Cafe24 variant_code가 비어 있습니다."
            )

        if not re.fullmatch(r"[A-Za-z0-9_-]+", normalized_variant_code):
            raise ProviderNonRetryableError(
                "Cafe24 variant_code에 허용되지 않은 '/' 문자가 포함되어 있습니다."
            )

        transport = self._require_transport()

        url = (
            f"https://{self.mall_id}.cafe24api.com"
            f"/api/v2/admin/products/{product_no}/variants/"
            f"{normalized_variant_code}/inventories"
        )

        payload = transport.get(
            url=url,
            required_scopes={self.PRODUCT_SCOPE},
            headers=self._authorization_headers(),
        )

        if not isinstance(payload, dict):
            raise ProviderNonRetryableError(
                "Cafe24 Variant Inventory 응답은 JSON Object여야 합니다."
            )

        inventory = payload.get("inventory")

        if not isinstance(inventory, dict):
            raise ProviderNonRetryableError(
                "Cafe24 Variant Inventory 응답에 inventory Object가 없습니다."
            )

        inventory_item = {
            **inventory,
            "product_no": product_no,
            "variant_code": normalized_variant_code,
        }

        sanitized_items, _ = self._sanitize_items(
            resource="variant_inventories",
            items=[inventory_item],
        )

        return self._page(
            resource="variant_inventories",
            items=sanitized_items,
            offset=0,
        )

    def read_categories(
        self,
        cursor: str | None = None,
    ) -> ProviderReadPage[dict[str, Any]]:
        """Cafe24 상품분류 목록을 Read-Only로 조회한다."""

        transport = self._require_transport()
        offset = self._offset_from_cursor(cursor)

        url = (
            f"https://{self.mall_id}.cafe24api.com"
            "/api/v2/admin/categories"
        )

        payload = transport.get(
            url=url,
            required_scopes={self.CATEGORY_SCOPE},
            headers=self._authorization_headers(),
            params={
                "limit": self.PAGE_SIZE,
                "offset": offset,
            },
        )

        if not isinstance(payload, dict):
            raise ProviderNonRetryableError(
                "Cafe24 Category 응답은 JSON Object여야 합니다."
            )

        items = payload.get("categories")

        if not isinstance(items, list):
            raise ProviderNonRetryableError(
                "Cafe24 Category 응답에 categories 배열이 없습니다."
            )

        if not all(isinstance(item, dict) for item in items):
            raise ProviderNonRetryableError(
                "Cafe24 Category 항목은 JSON Object여야 합니다."
            )

        sanitized_items, _ = self._sanitize_items(
            resource="categories",
            items=items,
        )

        return self._page(
            resource="categories",
            items=sanitized_items,
            offset=offset,
        )

    def read_category(
        self,
        category_no: int,
    ) -> dict[str, Any]:
        """Cafe24 특정 상품분류 상세를 Read-Only로 조회한다."""

        if type(category_no) is not int or category_no < 1:
            raise ProviderNonRetryableError(
                "Cafe24 category_no는 1 이상이어야 합니다."
            )

        transport = self._require_transport()

        url = (
            f"https://{self.mall_id}.cafe24api.com"
            f"/api/v2/admin/categories/{category_no}"
        )

        payload = transport.get(
            url=url,
            required_scopes={self.CATEGORY_SCOPE},
            headers=self._authorization_headers(),
        )

        if not isinstance(payload, dict):
            raise ProviderNonRetryableError(
                "Cafe24 Category 상세 응답은 JSON Object여야 합니다."
            )

        category = payload.get("category")

        if not isinstance(category, dict):
            raise ProviderNonRetryableError(
                "Cafe24 Category 상세 응답에 category Object가 없습니다."
            )

        sanitized_items, _ = self._sanitize_items(
            resource="categories",
            items=[category],
        )

        return sanitized_items[0]

    def read_orders(
        self,
        cursor: str | None = None,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> ProviderReadPage[dict[str, Any]]:
        """Cafe24 주문 목록 GET 응답을 ProviderReadPage로 반환한다."""

        transport = self._require_transport()
        offset = self._offset_from_cursor(cursor)

        url = (
            f"https://{self.mall_id}.cafe24api.com"
            "/api/v2/admin/orders"
        )

        today = datetime.now(UTC).date()

        resolved_end_date = (
            end_date
            if end_date is not None
            else today
        )

        resolved_start_date = (
            start_date
            if start_date is not None
            else resolved_end_date
            - timedelta(days=30)
        )

        if (
            type(resolved_start_date) is not date
            or type(resolved_end_date) is not date
        ):
            raise ProviderNonRetryableError(
                "Cafe24 주문 조회 날짜는 date 형식이어야 합니다."
            )

        if resolved_start_date > resolved_end_date:
            raise ProviderNonRetryableError(
                "Cafe24 주문 조회 시작일은 종료일보다 늦을 수 없습니다."
            )

        if (
            resolved_end_date
            - resolved_start_date
        ).days > 30:
            raise ProviderNonRetryableError(
                "Cafe24 주문 조회 구간은 최대 31일로 제한합니다."
            )

        payload = transport.get(
            url=url,
            required_scopes={self.ORDER_SCOPE},
            headers=self._authorization_headers(),
            params={
                "start_date": (
                    resolved_start_date.isoformat()
                ),
                "end_date": (
                    resolved_end_date.isoformat()
                ),
                "limit": self.PAGE_SIZE,
                "offset": offset,
            },
        )

        if not isinstance(payload, dict):
            raise ProviderNonRetryableError(
                "Cafe24 주문 응답이 JSON Object가 아닙니다."
            )

        items = payload.get("orders")

        if not isinstance(items, list):
            raise ProviderNonRetryableError(
                "Cafe24 주문 응답에 orders 목록이 없습니다."
            )

        if not all(isinstance(item, dict) for item in items):
            raise ProviderNonRetryableError(
                "Cafe24 주문 응답의 orders 항목이 JSON Object가 아닙니다."
            )

        sanitized_items, _ = self._sanitize_items(
            resource="orders",
            items=items,
        )

        return self._page(
            resource="orders",
            items=sanitized_items,
            offset=offset,
        )

    def read_order_items(
        self,
        order_id: str,
    ) -> ProviderReadPage[dict[str, Any]]:
        """Cafe24 특정 주문의 품목 목록을 Read-Only로 조회한다."""

        if not isinstance(order_id, str):
            raise ProviderNonRetryableError("Cafe24 order_id must be text")
        normalized_order_id = order_id.strip()

        if not normalized_order_id:
            raise ProviderNonRetryableError(
                "Cafe24 order_id가 비어 있습니다."
            )

        if not re.fullmatch(r"[A-Za-z0-9_-]+", normalized_order_id):
            raise ProviderNonRetryableError(
                "Cafe24 order_id 형식이 올바르지 않습니다."
            )

        transport = self._require_transport()

        url = (
            f"https://{self.mall_id}.cafe24api.com"
            f"/api/v2/admin/orders/{normalized_order_id}/items"
        )

        payload = transport.get(
            url=url,
            required_scopes={self.ORDER_SCOPE},
            headers=self._authorization_headers(),
        )

        if not isinstance(payload, dict):
            raise ProviderNonRetryableError(
                "Cafe24 OrderItem 응답은 JSON Object여야 합니다."
            )

        items = payload.get("items")

        if not isinstance(items, list):
            raise ProviderNonRetryableError(
                "Cafe24 OrderItem 응답에 items 배열이 없습니다."
            )

        if not all(isinstance(item, dict) for item in items):
            raise ProviderNonRetryableError(
                "Cafe24 OrderItem 항목은 JSON Object여야 합니다."
            )

        sanitized_items, _ = self._sanitize_items(
            resource="order_items",
            items=items,
        )

        return self._page(
            resource="order_items",
            items=sanitized_items,
            offset=0,
            paginated=False,
        )

    def read_refunds(
        self,
        cursor: str | None = None,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> ProviderReadPage[dict[str, Any]]:
        """Cafe24 환불 목록을 Read-Only로 조회한다."""

        transport = self._require_transport()
        offset = self._offset_from_cursor(cursor)

        url = (
            f"https://{self.mall_id}.cafe24api.com"
            "/api/v2/admin/refunds"
        )

        today = datetime.now(UTC).date()

        resolved_end_date = (
            end_date
            if end_date is not None
            else today
        )

        resolved_start_date = (
            start_date
            if start_date is not None
            else resolved_end_date
            - timedelta(days=30)
        )

        if (
            type(resolved_start_date) is not date
            or type(resolved_end_date) is not date
        ):
            raise ProviderNonRetryableError(
                "Cafe24 환불 조회 날짜는 date 형식이어야 합니다."
            )

        if resolved_start_date > resolved_end_date:
            raise ProviderNonRetryableError(
                "Cafe24 환불 조회 시작일은 종료일보다 늦을 수 없습니다."
            )

        if (
            resolved_end_date
            - resolved_start_date
        ).days > 30:
            raise ProviderNonRetryableError(
                "Cafe24 환불 조회 구간은 최대 31일로 제한합니다."
            )

        payload = transport.get(
            url=url,
            required_scopes={self.ORDER_SCOPE},
            headers=self._authorization_headers(),
            params={
                "start_date": (
                    resolved_start_date.isoformat()
                ),
                "end_date": (
                    resolved_end_date.isoformat()
                ),
                "limit": self.PAGE_SIZE,
                "offset": offset,
            },
        )

        if not isinstance(payload, dict):
            raise ProviderNonRetryableError(
                "Cafe24 Refund 응답은 JSON Object여야 합니다."
            )

        items = payload.get("refunds")

        if not isinstance(items, list):
            raise ProviderNonRetryableError(
                "Cafe24 Refund 응답에 refunds 배열이 없습니다."
            )

        if not all(isinstance(item, dict) for item in items):
            raise ProviderNonRetryableError(
                "Cafe24 Refund 항목은 JSON Object여야 합니다."
            )

        sanitized_items, _ = self._sanitize_items(
            resource="refunds",
            items=items,
        )

        return self._page(
            resource="refunds",
            items=sanitized_items,
            offset=offset,
        )

    def read_boards(
        self,
        cursor: str | None = None,
    ) -> ProviderReadPage[dict[str, Any]]:
        """Cafe24 게시판 목록을 Read-Only로 조회한다."""

        transport = self._require_transport()
        offset = self._offset_from_cursor(cursor)

        url = (
            f"https://{self.mall_id}.cafe24api.com"
            "/api/v2/admin/boards"
        )

        payload = transport.get(
            url=url,
            required_scopes={self.COMMUNITY_SCOPE},
            headers=self._authorization_headers(),
            params={
                "limit": self.PAGE_SIZE,
                "offset": offset,
            },
        )

        if not isinstance(payload, dict):
            raise ProviderNonRetryableError(
                "Cafe24 Board 응답은 JSON Object여야 합니다."
            )

        items = payload.get("boards")

        if not isinstance(items, list):
            raise ProviderNonRetryableError(
                "Cafe24 Board 응답에 boards 배열이 없습니다."
            )

        if not all(isinstance(item, dict) for item in items):
            raise ProviderNonRetryableError(
                "Cafe24 Board 항목은 JSON Object여야 합니다."
            )

        sanitized_items, _ = self._sanitize_items(
            resource="boards",
            items=items,
        )

        return self._page(
            resource="boards",
            items=sanitized_items,
            offset=offset,
        )

    def read_articles(
        self,
        board_no: int,
        cursor: str | None = None,
    ) -> ProviderReadPage[dict[str, Any]]:
        """Cafe24 특정 게시판의 게시글 목록을 Read-Only로 조회한다."""

        if type(board_no) is not int or board_no < 1:
            raise ProviderNonRetryableError(
                "Cafe24 board_no는 1 이상이어야 합니다."
            )

        transport = self._require_transport()
        offset = self._offset_from_cursor(cursor)

        url = (
            f"https://{self.mall_id}.cafe24api.com"
            f"/api/v2/admin/boards/{board_no}/articles"
        )

        payload = transport.get(
            url=url,
            required_scopes={self.COMMUNITY_SCOPE},
            headers=self._authorization_headers(),
            params={
                "limit": self.PAGE_SIZE,
                "offset": offset,
            },
        )

        if not isinstance(payload, dict):
            raise ProviderNonRetryableError(
                "Cafe24 Article 응답은 JSON Object여야 합니다."
            )

        items = payload.get("articles")

        if not isinstance(items, list):
            raise ProviderNonRetryableError(
                "Cafe24 Article 응답에 articles 배열이 없습니다."
            )

        if not all(isinstance(item, dict) for item in items):
            raise ProviderNonRetryableError(
                "Cafe24 Article 항목은 JSON Object여야 합니다."
            )

        sanitized_items, _ = self._sanitize_items(
            resource="articles",
            items=items,
        )

        # 게시판 Article API는 공지/고정글 등의 영향으로
        # 요청 limit(25)보다 많은 항목을 반환할 수 있다.
        # 따라서 정확히 25개인 경우만 다음 페이지로 판단하면
        # 실제 데이터가 남아 있어도 첫 페이지에서 종료될 수 있다.
        has_more = (
            len(sanitized_items)
            >= self.PAGE_SIZE
        )

        next_cursor = (
            f"offset:{offset + self.PAGE_SIZE}"
            if has_more
            else None
        )

        now = datetime.now(UTC)

        return ProviderReadPage(
            provider=self.provider,
            resource="articles",
            items=sanitized_items,
            next_cursor=next_cursor,
            watermark=now,
            has_more=has_more,
            request_count=1,
            source_as_of=now,
        )

    def read_article_comments(
        self,
        board_no: int,
        article_no: int,
        cursor: str | None = None,
    ) -> ProviderReadPage[dict[str, Any]]:
        """Cafe24 특정 게시글의 댓글/답변을 Read-Only로 조회한다."""

        if type(board_no) is not int or board_no < 1:
            raise ProviderNonRetryableError(
                "Cafe24 board_no는 1 이상이어야 합니다."
            )

        if type(article_no) is not int or article_no < 1:
            raise ProviderNonRetryableError(
                "Cafe24 article_no는 1 이상이어야 합니다."
            )

        transport = self._require_transport()
        offset = self._offset_from_cursor(cursor)

        url = (
            f"https://{self.mall_id}.cafe24api.com"
            f"/api/v2/admin/boards/{board_no}/articles/"
            f"{article_no}/comments"
        )

        payload = transport.get(
            url=url,
            required_scopes={self.COMMUNITY_SCOPE},
            headers=self._authorization_headers(),
            params={
                "limit": self.PAGE_SIZE,
                "offset": offset,
            },
        )

        if not isinstance(payload, dict):
            raise ProviderNonRetryableError(
                "Cafe24 Comment 응답은 JSON Object여야 합니다."
            )

        items = payload.get("comments")

        if not isinstance(items, list):
            raise ProviderNonRetryableError(
                "Cafe24 Comment 응답에 comments 배열이 없습니다."
            )

        if not all(isinstance(item, dict) for item in items):
            raise ProviderNonRetryableError(
                "Cafe24 Comment 항목은 JSON Object여야 합니다."
            )

        sanitized_items, _ = self._sanitize_items(
            resource="article_comments",
            items=items,
        )

        now = datetime.now(UTC)

        has_more = (
            len(sanitized_items)
            >= self.PAGE_SIZE
        )

        next_cursor = (
            f"offset:{offset + self.PAGE_SIZE}"
            if has_more
            else None
        )

        return ProviderReadPage(
            provider=self.provider,
            resource="article_comments",
            items=sanitized_items,
            next_cursor=next_cursor,
            watermark=now,
            has_more=has_more,
            request_count=1,
            source_as_of=now,
        )

    def read_inventory(
        self,
        cursor: str | None = None,
    ) -> ProviderReadPage[dict[str, Any]]:
        raise UnsupportedCapability(
            "UNSUPPORTED_CAPABILITY: Cafe24 재고 Resource는 아직 VERIFY 상태입니다."
        )

    def read_inquiries(
        self,
        cursor: str | None = None,
    ) -> ProviderReadPage[dict[str, Any]]:
        raise UnsupportedCapability(
            "UNSUPPORTED_CAPABILITY: Cafe24 문의 Mapping은 아직 VERIFY 상태입니다."
        )

    def read_incoming_stock(
        self,
        cursor: str | None = None,
    ) -> ProviderReadPage[dict[str, Any]]:
        raise UnsupportedCapability(
            "UNSUPPORTED_CAPABILITY: Cafe24 입고예정 Resource는 UNKNOWN 상태입니다."
        )
