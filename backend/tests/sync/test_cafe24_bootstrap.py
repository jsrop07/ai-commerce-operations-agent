"""Bootstrap tests use actual adapter/transport with synthetic HTTP JSON fixtures."""

from copy import deepcopy
import hashlib
import json
from urllib.parse import urlsplit

import pytest

from backend.app.adapters.providers.base import ProviderNonRetryableError
from backend.app.adapters.providers.cafe24.adapter import Cafe24Adapter
from backend.app.adapters.providers.capability_guard import (
    CAFE24_ALLOWED_READ_PATH_PATTERNS, CAFE24_ALLOWED_READ_PATHS,
)
from backend.app.adapters.providers.http_transport import ReadOnlyHttpTransport
from backend.app.api.cafe24_oauth import REQUIRED_READ_SCOPES
from backend.app.sync import cafe24_bootstrap
from backend.app.sync.cafe24_commerce_integrity import (
    run_cafe24_commerce_integrity,
)
from backend.app.sync.cafe24_community_integrity import (
    run_cafe24_community_integrity,
)
from backend.app.sync.cafe24_order_item_full_runner import _load_order_ids
from backend.app.sync.cafe24_bootstrap import (
    _collect_cafe24_resources,
    _product_batch_resume,
    run_cafe24_read_bootstrap,
)
from backend.app.worker.privacy.protected_storage import (
    write_protected_raw_response,
    write_sanitized_export,
)
from backend.app.worker.privacy.staging import sanitize_community_record
from backend.app.worker.privacy.snapshot_manifest import (
    build_raw_response_manifest_entry,
    write_snapshot_manifest,
)
from contracts.providers import ProviderReadPage

ACCESS_FIXTURE = "synthetic-access-token"
PHONE_FIXTURE = "-".join(("010", "0000", "0000"))


class FixtureHTTP:
    def __init__(self, paginated=(), failure=False):
        self.paginated = set(paginated)
        self.failure = failure
        self.calls = []
        self.bodies = []

    def __call__(
        self,
        *,
        method,
        url,
        headers,
        params,
        timeout,
    ):
        assert method == "GET"

        assert (
            headers["Authorization"]
            == f"Bearer {ACCESS_FIXTURE}"
        )

        parts = (
            urlsplit(
                url
            )
            .path
            .split("/")
        )

        key = parts[-1]

        params = (
            params
            or {}
        )

        offset = params.get(
            "offset",
            0,
        )

        self.calls.append(
            (
                method,
                key,
                offset,
                dict(
                    params
                ),
            )
        )

        if (
            self.failure
            and key == "variants"
            and offset
        ):
            raise ProviderNonRetryableError(
                "synthetic partial failure"
            )

        count = (
            3
            if key
            in self.paginated
            else 1
        )

        items = []

        for n in range(
            1,
            count + 1,
        ):
            record = {
                "products": {
                    "product_no": (
                        100 + n
                    ),
                    "product_name": (
                        "Synthetic Product"
                    ),
                },
                "variants": {
                    "product_no": (
                        int(
                            parts[-2]
                        )
                        if key
                        == "variants"
                        else 101
                    ),
                    "variant_code": (
                        f"SYNTHETIC-{n}"
                    ),
                },
                "inventories": {
                    "quantity": 3,
                },
                "categories": {
                    "category_no": n,
                },
                "orders": {
                    "order_id": (
                        f"20260101-{n:06d}"
                    ),
                    "receiver_name": (
                        "synthetic-person"
                    ),
                    "phone": (
                        PHONE_FIXTURE
                    ),
                },
                "items": {
                    "product_no": 101,
                    "quantity": 1,
                },
                "refunds": None,
                "boards": {
                    "board_no": 6,
                },
                "articles": {
                    "board_no": 6,
                    "article_no": (
                        1000 + n
                    ),
                    "content": (
                        "synthetic contact "
                        + PHONE_FIXTURE
                    ),
                },
                "comments": {
                    "comment_no": n,
                    "content": (
                        "synthetic reply"
                    ),
                },
            }[key]

            if record is not None:
                items.append(
                    record
                )

        if "limit" in params:
            items = items[
                offset:
                offset
                + params["limit"]
            ]

        # Cafe24 Variant Inventory는
        # list가 아니라 단건 inventory Object 응답.
        if key == "inventories":
            body = {
                "inventory": (
                    items[0]
                    if items
                    else {}
                ),
                "fixture_metadata": (
                    "synthetic-provider-response"
                ),
            }

        else:
            body = {
                key: items,
                "fixture_metadata": (
                    "synthetic-provider-response"
                ),
            }

        self.bodies.append(
            (
                key,
                deepcopy(
                    body
                ),
            )
        )

        return body


def make_adapter(http, max_request_count=None):
    transport = ReadOnlyHttpTransport(
        request_fn=http, granted_scopes=REQUIRED_READ_SCOPES,
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
        max_request_count=max_request_count,
    )
    adapter = Cafe24Adapter(mall_id="synthetic-mall", access_token=ACCESS_FIXTURE,
                           transport=transport)
    adapter.PAGE_SIZE = 2
    return adapter


def run(tmp_path, http=None, batch_id="synthetic-bootstrap", **kwargs):
    http = http or FixtureHTTP()
    result = run_cafe24_read_bootstrap(adapter=make_adapter(http), protected_root=tmp_path,
                                     batch_id=batch_id, **kwargs)
    return result, http


def test_cafe24_bootstrap_builds_all_snapshots(tmp_path):
    result, http = run(tmp_path)
    assert result.external_write_count == 0
    assert len(result.snapshots) == len(result.raw_snapshots) == 10
    assert result.manifest_path.exists()
    assert {s.resource for s in result.snapshots} == {
        "products", "variants", "variant_inventories", "categories", "orders",
        "order_items", "refunds", "boards", "articles", "article_comments",
    }
    assert all(method == "GET" for method, *_ in http.calls)
    assert result.product_start == 0
    assert result.product_batch_size == 250
    assert result.product_batch_count == 1
    assert result.next_product_start is None
    assert result.product_batch_completed is True
    assert result.request_count == len(http.calls)


def test_cafe24_bootstrap_manifest_has_counts(tmp_path):
    result, _ = run(tmp_path)
    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert payload["snapshot_count"] == 10
    assert payload["raw_total"] == payload["sanitized_total"] == 9
    allowed = {"provider", "resource", "batch_id", "raw_sha256", "raw_count", "sanitized_count"}
    assert all(set(entry) == allowed for entry in payload["resources"])


def test_cafe24_bootstrap_sanitizes_inquiry_text(tmp_path):
    result, _ = run(tmp_path)
    snapshot = next(s for s in result.snapshots if s.resource == "articles")
    sanitized = snapshot.sanitized_path.read_text(encoding="utf-8")
    assert PHONE_FIXTURE not in sanitized
    assert "<PHONE>" not in sanitized
    assert "content_sha256" in sanitized
    assert "content" not in json.loads(sanitized)["records"][0]


def test_actual_provider_raw_is_preserved_before_adapter_sanitization(tmp_path):
    http = FixtureHTTP()
    adapter = make_adapter(http)
    original_transport = adapter.transport
    result = run_cafe24_read_bootstrap(adapter=adapter, protected_root=tmp_path,
                                     batch_id="synthetic-raw-boundary")
    raw = next(s for s in result.raw_snapshots if s.resource == "orders")
    sanitized = next(s for s in result.snapshots if s.resource == "orders")
    expected = next(body for key, body in http.bodies if key == "orders")
    raw_bytes = raw.raw_path.read_bytes()
    assert json.loads(raw_bytes) == expected
    assert "synthetic-person" in raw_bytes.decode()
    assert PHONE_FIXTURE in raw_bytes.decode()
    sanitized_text = sanitized.sanitized_path.read_text(encoding="utf-8")
    assert "synthetic-person" not in sanitized_text and PHONE_FIXTURE not in sanitized_text
    assert "receiver_name" not in sanitized_text and '"phone"' not in sanitized_text
    expected_bytes = json.dumps(expected, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert raw.raw_sha256 == hashlib.sha256(expected_bytes).hexdigest()
    assert raw.raw_sha256 == hashlib.sha256(raw_bytes).hexdigest()
    manifest_text = result.manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    entry = next(e for e in manifest["resources"] if e["resource"] == "orders")
    assert entry["raw_sha256"] == raw.raw_sha256
    assert entry["raw_count"] == entry["sanitized_count"] == 1
    assert str(tmp_path) not in manifest_text
    for forbidden in ("Authorization", "Bearer", ACCESS_FIXTURE, "refresh_token", "client_secret"):
        assert all(forbidden not in s.raw_path.read_text(encoding="utf-8") for s in result.raw_snapshots)
        assert forbidden not in manifest_text
    assert "synthetic-person" not in manifest_text and PHONE_FIXTURE not in manifest_text
    assert adapter.transport is original_transport
    assert result.external_write_count == 0


def test_cafe24_bootstrap_collects_two_product_pages(tmp_path):
    result, http = run(tmp_path, FixtureHTTP(paginated={"products"}))
    assert [offset for _, key, offset, _ in http.calls if key == "products"] == [0, 2]
    counts = {s.resource: s.sanitized_count for s in result.snapshots}
    assert counts["products"] == counts["variants"] == 3
    assert len([s for s in result.raw_snapshots if s.resource == "products"]) == 2


def test_bootstrap_collects_two_page_orders_and_fanout_children(tmp_path):
    result, http = run(tmp_path, FixtureHTTP(paginated={"orders", "variants", "articles", "comments"}))
    counts = {s.resource: s.sanitized_count for s in result.snapshots}
    assert counts["orders"] == counts["order_items"] == 3
    assert counts["variants"] == counts["variant_inventories"] == 3
    assert counts["articles"] == 3 and counts["article_comments"] == 9
    for key in ("orders", "variants", "articles"):
        assert [offset for _, k, offset, _ in http.calls if k == key] == [0, 2]
    assert [offset for _, k, offset, _ in http.calls if k == "comments"] == [0, 2] * 3
    assert sum(s.raw_count for s in result.raw_snapshots) == sum(counts.values())


@pytest.mark.parametrize("failure", ["partial", "repeated_cursor", "budget", "detail_cursor"])
def test_bootstrap_never_commits_incomplete_collection(tmp_path, monkeypatch, failure):
    original_page = Cafe24Adapter._page
    def page(self, **kwargs):
        result = original_page(self, **kwargs)
        if failure == "repeated_cursor" and kwargs["resource"] == "variants" and kwargs["offset"]:
            return result.model_copy(update={"has_more": True, "next_cursor": "offset:2"})
        if failure == "detail_cursor" and kwargs["resource"] == "variant_inventories":
            return result.model_copy(update={"has_more": True, "next_cursor": "offset:2"})
        return result
    monkeypatch.setattr(Cafe24Adapter, "_page", page)
    http = FixtureHTTP(paginated={"variants"}, failure=failure == "partial")
    with pytest.raises(RuntimeError):
        run(tmp_path, http, max_pages=1 if failure == "budget" else 100)
    # Successfully captured HTTP pages remain; incomplete collection never publishes a manifest/export.
    assert list((tmp_path / "cafe24" / "raw").rglob("*.json"))
    assert not list(tmp_path.rglob("*.manifest.json"))
    assert not list(tmp_path.rglob("*.sanitized.json"))


def test_bootstrap_capture_failure_stops_without_retry_or_manifest(tmp_path, monkeypatch):
    def fail(**kwargs):
        raise OSError("synthetic-private-location")
    monkeypatch.setattr(cafe24_bootstrap, "write_protected_raw_response", fail)
    http = FixtureHTTP()
    with pytest.raises(RuntimeError) as caught:
        run(tmp_path, http)
    assert len(http.calls) == 1
    assert "synthetic-private-location" not in str(caught.value)
    assert not list(tmp_path.rglob("*.json"))


def test_bootstrap_batch_replay_preserves_existing_snapshot_and_manifest(tmp_path):
    result, http = run(tmp_path)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    calls = len(http.calls)
    with pytest.raises(FileExistsError):
        run(tmp_path, http)
    assert {p: p.read_bytes() for p in tmp_path.rglob("*.json")} == before
    assert len(http.calls) == calls
    assert result.external_write_count == 0


def test_csv_backfill_does_not_expand_api_history(tmp_path):
    _, http = run(tmp_path)
    from datetime import date
    for _, resource, _, params in http.calls:
        if resource in {"orders", "refunds"}:
            assert (date.fromisoformat(params["end_date"]) - date.fromisoformat(params["start_date"])).days == 30


def test_bootstrap_rejects_adapter_without_raw_transport(tmp_path):
    with pytest.raises(ValueError, match="capture-capable"):
        run_cafe24_read_bootstrap(adapter=Cafe24Adapter(), protected_root=tmp_path,
                                 batch_id="synthetic-no-transport")
    assert list(tmp_path.iterdir()) == []


def _page(resource, items):
    return ProviderReadPage(
        provider="CAFE24",
        resource=resource,
        items=items,
        next_cursor=None,
        watermark=None,
        has_more=False,
        request_count=1,
        source_as_of=None,
        schema_version="1.0",
    )


class SixHundredProductAdapter:
    def __init__(self):
        self.variant_products = []
        self.inventory_products = []

    def read_products(self, cursor=None):
        return _page(
            "products",
            [{"product_no": number} for number in range(1, 601)],
        )

    def read_variants(self, product_no, cursor=None):
        self.variant_products.append(product_no)
        return _page(
            "variants",
            [{"product_no": product_no, "variant_code": f"SYN-{product_no}"}],
        )

    def read_variant_inventory(self, product_no, variant_code):
        self.inventory_products.append(product_no)
        return _page("variant_inventories", [{"product_no": product_no}])

    def read_categories(self, cursor=None):
        return _page("categories", [])

    def read_orders(self, cursor=None):
        return _page("orders", [])

    def read_order_items(self, order_id):
        raise AssertionError("no synthetic orders")

    def read_refunds(self, cursor=None):
        return _page("refunds", [])

    def read_boards(self, cursor=None):
        return _page("boards", [])

    def read_articles(self, board_no, cursor=None):
        raise AssertionError("no synthetic boards")

    def read_article_comments(self, board_no, article_no, cursor=None):
        raise AssertionError("no synthetic articles")


@pytest.mark.parametrize(
    ("start", "expected_first", "expected_last", "expected_count", "next_start"),
    [
        (0, 1, 250, 250, 250),
        (250, 251, 500, 250, 500),
        (500, 501, 600, 100, None),
        (600, None, None, 0, None),
        (700, None, None, 0, None),
    ],
)
def test_six_hundred_products_use_deterministic_fanout_batches(
    start,
    expected_first,
    expected_last,
    expected_count,
    next_start,
):
    adapter = SixHundredProductAdapter()

    collected = _collect_cafe24_resources(
        adapter=adapter,  # type: ignore[arg-type]
        max_pages=100,
        product_start=start,
        product_batch_size=250,
    )
    batch_count, actual_next = _product_batch_resume(
        product_total=len(collected["products"]),
        product_start=start,
        product_batch_size=250,
    )

    assert len(collected["products"]) == 600
    assert len(collected["variants"]) == expected_count
    assert len(collected["variant_inventories"]) == expected_count
    assert len(adapter.variant_products) == expected_count
    assert adapter.inventory_products == adapter.variant_products
    if expected_count:
        assert adapter.variant_products[0] == expected_first
        assert adapter.variant_products[-1] == expected_last
    assert batch_count == expected_count
    assert actual_next == next_start


@pytest.mark.parametrize(
    ("product_start", "product_batch_size"),
    [(-1, 250), (0, 0), (0, -1), (True, 250), (0, True)],
)
def test_bootstrap_rejects_invalid_product_batch_arguments(
    tmp_path,
    product_start,
    product_batch_size,
):
    with pytest.raises(ValueError):
        run_cafe24_read_bootstrap(
            adapter=make_adapter(FixtureHTTP()),
            protected_root=tmp_path,
            batch_id="synthetic-invalid-batch",
            product_start=product_start,
            product_batch_size=product_batch_size,
        )
    assert list(tmp_path.iterdir()) == []


def test_request_limit_during_product_fanout_never_publishes_success(tmp_path):
    http = FixtureHTTP()
    adapter = make_adapter(http, max_request_count=2)

    with pytest.raises(RuntimeError):
        run_cafe24_read_bootstrap(
            adapter=adapter,
            protected_root=tmp_path,
            batch_id="synthetic-limited-batch",
        )

    assert len(http.calls) == 2
    assert not list(tmp_path.rglob("*.manifest.json"))
    assert not list(tmp_path.rglob("*.sanitized.json"))


def test_commerce_integrity_uses_only_canonical_batches(tmp_path) -> None:
    batch_id = "order-full-integrity-synthetic"
    raw = write_protected_raw_response(
        protected_root=tmp_path,
        provider="CAFE24",
        resource="orders",
        batch_id=batch_id,
        page_id="page-000001",
        payload={"orders": [{"order_id": "20260101-000001"}]},
        raw_count=1,
    )
    write_sanitized_export(
        protected_root=tmp_path,
        provider="CAFE24",
        resource="orders",
        batch_id=batch_id,
        records=[{"order_id": "20260101-000001"}],
    )
    write_snapshot_manifest(
        output_path=tmp_path / "cafe24" / "manifests" / f"{batch_id}.manifest.json",
        entries=[build_raw_response_manifest_entry(raw, sanitized_count=1)],
    )
    write_sanitized_export(
        protected_root=tmp_path,
        provider="CAFE24",
        resource="orders",
        batch_id="order-full-orphan-synthetic",
        records=[{"order_id": "20260101-999999"}],
    )
    csv_path = tmp_path / "orders.csv"
    csv_path.write_text(
        "주문번호,품목별 주문번호\n20260101-000001,\n",
        encoding="utf-8-sig",
    )

    result = run_cafe24_commerce_integrity(
        protected_root=tmp_path, csv_path=csv_path
    )
    assert result.api_unique_order_count == 1
    assert result.order_manifest_missing_count == 1
    assert result.manifest_invalid_count == 0
    assert _load_order_ids(root=tmp_path) == ["20260101-000001"]

    manifest_path = tmp_path / "cafe24" / "manifests" / f"{batch_id}.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resources"][0]["raw_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    invalid = run_cafe24_commerce_integrity(
        protected_root=tmp_path, csv_path=csv_path
    )
    assert invalid.manifest_invalid_count == 1
    assert invalid.passed is False

def test_community_integrity_uses_only_canonical_batches(tmp_path) -> None:
    resource = "board_6_articles"
    batch_id = "community-article-6-integrity-synthetic"
    raw = write_protected_raw_response(
        protected_root=tmp_path,
        provider="CAFE24",
        resource=resource,
        batch_id=batch_id,
        page_id="page-000001",
        payload={"articles": [{"board_no": 6, "article_no": 1001}]},
        raw_count=1,
    )
    write_sanitized_export(
        protected_root=tmp_path,
        provider="CAFE24",
        resource=resource,
        batch_id=batch_id,
        records=[sanitize_community_record({"board_no": 6, "article_no": 1001})],
    )
    write_snapshot_manifest(
        output_path=tmp_path / "cafe24" / "manifests" / f"{batch_id}.manifest.json",
        entries=[build_raw_response_manifest_entry(raw, sanitized_count=1)],
    )
    write_sanitized_export(
        protected_root=tmp_path,
        provider="CAFE24",
        resource=resource,
        batch_id="community-article-6-orphan-synthetic",
        records=[sanitize_community_record({"board_no": 6, "article_no": 9999})],
    )

    result = run_cafe24_community_integrity(protected_root=tmp_path)
    assert result.unique_article_count == 1
    assert result.article_manifest_missing_count == 1
    assert result.manifest_invalid_count == 0

    manifest_path = tmp_path / "cafe24" / "manifests" / f"{batch_id}.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["resources"][0]["raw_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    invalid = run_cafe24_community_integrity(protected_root=tmp_path)
    assert invalid.manifest_invalid_count == 1
    assert invalid.passed is False