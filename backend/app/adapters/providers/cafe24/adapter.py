"""Cafe24 Day 5 읽기 전용 Adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from backend.app.adapters.providers.base import (
    CommerceProvider,
    ProviderNonRetryableError,
    UnsupportedCapability,
    WriteDisabledMixin,
)
from backend.app.adapters.providers.http_transport import ReadOnlyHttpTransport
from backend.app.worker.privacy.staging import build_staging_record
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

            sanitized_items.append(staging.sanitized_payload)
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

        if not self.mall_id:
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
                f"Cafe24 cursor 형식이 올바르지 않습니다: {cursor}"
            )

        raw_offset = cursor.removeprefix(prefix)

        try:
            offset = int(raw_offset)
        except ValueError as exc:
            raise ProviderNonRetryableError(
                f"Cafe24 cursor offset이 숫자가 아닙니다: {cursor}"
            ) from exc

        if offset < 0:
            raise ProviderNonRetryableError(
                f"Cafe24 cursor offset은 음수일 수 없습니다: {cursor}"
            )

        return offset

    def _page(
        self,
        *,
        resource: str,
        items: list[dict[str, Any]],
        offset: int,
    ) -> ProviderReadPage[dict[str, Any]]:
        """Cafe24 목록 응답을 기존 ProviderReadPage 계약으로 감싼다."""

        now = datetime.now(UTC)

        has_more = len(items) == self.PAGE_SIZE

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

    def read_orders(
        self,
        cursor: str | None = None,
    ) -> ProviderReadPage[dict[str, Any]]:
        """Cafe24 주문 목록 GET 응답을 ProviderReadPage로 반환한다."""

        transport = self._require_transport()
        offset = self._offset_from_cursor(cursor)

        url = (
            f"https://{self.mall_id}.cafe24api.com"
            "/api/v2/admin/orders"
        )

        today = datetime.now(UTC).date()
        start_date = today - timedelta(days=30)

        payload = transport.get(
            url=url,
            required_scopes={self.ORDER_SCOPE},
            headers=self._authorization_headers(),
            params={
                "start_date": start_date.isoformat(),
                "end_date": today.isoformat(),
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
