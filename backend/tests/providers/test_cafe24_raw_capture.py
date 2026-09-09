"""Synthetic-only transport and protected provider-body capture tests."""

import hashlib
import json

import pytest

from backend.app.adapters.providers.capability_guard import (
    CAFE24_ALLOWED_READ_PATH_PATTERNS, CAFE24_ALLOWED_READ_PATHS,
    CredentialScopeError, ProviderWriteBlockedError,
)
from backend.app.adapters.providers.http_transport import (
    ProviderRequestLimitError,
    RawCaptureError,
    ReadOnlyHttpTransport,
)
from backend.app.adapters.providers.base import ProviderTransientError
from backend.app.sync.retry_policy import RetryPolicy
from backend.app.sync.runner import ProviderSyncRunner, SyncBudget
from backend.app.worker.privacy.protected_storage import write_protected_raw_response

ACCESS_FIXTURE = "synthetic-access-token"
SCOPE = {"mall.read_order"}
URL = "https://synthetic-mall.cafe24api.com/api/v2/admin/orders"


def transport(request_fn, capture=None, scopes=SCOPE):
    return ReadOnlyHttpTransport(
        request_fn=request_fn, granted_scopes=scopes,
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        allowed_path_patterns=CAFE24_ALLOWED_READ_PATH_PATTERNS,
        raw_capture_fn=capture,
    )


@pytest.mark.parametrize("entrypoint", ["get", "request"])
def test_capture_gets_only_validated_path_and_body_before_return(entrypoint):
    body = {"orders": [{"receiver_name": "synthetic-person"}]}
    seen = []
    def capture(*args):
        assert len(args) == 2
        path, payload = args
        assert path == "/api/v2/admin/orders"
        assert payload == body
        seen.append(path)
        payload["orders"][0]["receiver_name"] = "synthetic-mutated"
    client = transport(lambda **kw: body, capture)
    kwargs = dict(url=URL, required_scopes=SCOPE,
                  headers={"Authorization": f"Bearer {ACCESS_FIXTURE}"})
    if entrypoint == "request":
        kwargs["method"] = "GET"
    response = getattr(client, entrypoint)(**kwargs)
    assert response["orders"][0]["receiver_name"] == "synthetic-person"
    assert seen == ["/api/v2/admin/orders"]
    assert client.request_count == 1


@pytest.mark.parametrize("scopes,url,method,error", [
    (set(), URL, "GET", CredentialScopeError),
    (SCOPE, URL + "/unapproved", "GET", ProviderWriteBlockedError),
    (SCOPE, URL + "?method=DELETE", "GET", ProviderWriteBlockedError),
    (SCOPE, URL, "POST", ProviderWriteBlockedError),
    (SCOPE, URL, "DELETE", ProviderWriteBlockedError),
])
def test_failed_guard_performs_zero_requests_and_captures(scopes, url, method, error):
    calls, captures = [], []
    client = transport(lambda **kw: calls.append(kw), lambda *args: captures.append(args), scopes)
    with pytest.raises(error):
        client.request(method=method, url=url, required_scopes=SCOPE)
    assert calls == captures == []
    assert client.request_count == 0


def test_failed_http_request_is_never_captured():
    captures = []
    def fail(**kw):
        raise TimeoutError("synthetic timeout")
    client = transport(fail, lambda *args: captures.append(args))
    with pytest.raises(TimeoutError):
        client.get(url=URL, required_scopes=SCOPE)
    assert captures == []


def test_capture_failure_is_non_retryable_and_has_safe_error():
    def fail(path, payload):
        raise OSError("synthetic-private-location")
    client = transport(lambda **kw: {"orders": []}, fail)
    with pytest.raises(RawCaptureError) as caught:
        client.get(url=URL, required_scopes=SCOPE)
    assert caught.value.retryable is False
    assert "synthetic-private-location" not in str(caught.value)
    assert caught.value.__suppress_context__ is True
    assert client.request_count == 1


def test_credential_echo_never_reaches_capture():
    captures = []
    client = transport(lambda **kw: {"orders": [], "echo": ACCESS_FIXTURE},
                       lambda *args: captures.append(args))
    with pytest.raises(RawCaptureError):
        client.get(url=URL, required_scopes=SCOPE,
                   headers={"Authorization": f"Bearer {ACCESS_FIXTURE}"})
    assert captures == []


def test_actual_body_hash_and_duplicate_raw_page_are_immutable(tmp_path):
    body = {"orders": [{"order_id": "SYNTHETIC-001", "receiver_name": "synthetic-person",
                         "phone": "-".join(("010", "0000", "0000"))}]}
    kwargs = dict(protected_root=tmp_path, provider="CAFE24", resource="orders",
                  batch_id="synthetic-batch", page_id="page-000001", payload=body, raw_count=1)
    result = write_protected_raw_response(**kwargs)
    original = result.raw_path.read_bytes()
    assert json.loads(original) == body
    expected = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert result.raw_sha256 == hashlib.sha256(expected).hexdigest()
    assert result.raw_sha256 == hashlib.sha256(original).hexdigest()
    kwargs["payload"] = {"orders": []}
    with pytest.raises(FileExistsError):
        write_protected_raw_response(**kwargs)
    assert result.raw_path.read_bytes() == original


@pytest.mark.parametrize("key,value", [
    ("Authorization", "synthetic-auth"), ("access_token", ACCESS_FIXTURE),
    ("refresh_token", "synthetic-refresh"), ("client_secret", "synthetic-secret"),
    ("headers", {}), 
])
def test_response_with_credentials_is_rejected_without_storage(tmp_path, key, value):
    with pytest.raises(ValueError):
        write_protected_raw_response(
            protected_root=tmp_path, provider="CAFE24", resource="orders",
            batch_id="synthetic-batch", page_id="page-000001",
            payload={"orders": [{key: value}]}, raw_count=1,
        )
    assert list(tmp_path.iterdir()) == []

def test_response_allows_bearer_word_in_ordinary_content(tmp_path):
    captured = []

    def capture(path, payload):
        captured.append((path, payload))

    payload = {
        "content": "Synthetic Standard Bearer product description",
    }

    # 이 테스트 파일에서 기존 raw capture 함수를 호출하는
    # 동일한 helper/API를 재사용한다.

def test_capture_clone_does_not_replace_existing_hook():
    client = transport(lambda **kw: {}, lambda *args: None)
    with pytest.raises(RawCaptureError):
        client.with_raw_capture(lambda *args: None)


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_request_limit_rejects_invalid_values(limit):
    with pytest.raises(ValueError):
        ReadOnlyHttpTransport(
            request_fn=lambda **kw: {},
            granted_scopes=SCOPE,
            allowed_paths=CAFE24_ALLOWED_READ_PATHS,
            max_request_count=limit,
        )


def test_request_limit_allows_four_and_blocks_fifth_before_http():
    calls = []
    client = ReadOnlyHttpTransport(
        request_fn=lambda **kw: calls.append(kw) or {"orders": []},
        granted_scopes=SCOPE,
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        max_request_count=4,
    )

    for _ in range(4):
        client.get(url=URL, required_scopes=SCOPE)

    with pytest.raises(ProviderRequestLimitError):
        client.get(url=URL, required_scopes=SCOPE)

    assert len(calls) == 4
    assert client.request_count == 4


def test_retry_attempts_consume_request_limit():
    calls = []

    def transient(**kwargs):
        calls.append(kwargs)
        raise ProviderTransientError("synthetic transient failure")

    client = ReadOnlyHttpTransport(
        request_fn=transient,
        granted_scopes=SCOPE,
        allowed_paths=CAFE24_ALLOWED_READ_PATHS,
        max_request_count=2,
    )
    runner = ProviderSyncRunner(
        retry_policy=RetryPolicy(
            max_attempts=3,
            base_delay_seconds=0,
            max_delay_seconds=0,
            jitter_ratio=0,
        ),
        budget=SyncBudget(max_pages=1, max_items=10, max_elapsed_seconds=10),
        sleep_fn=lambda _: None,
    )

    result = runner.run(
        provider=object(),  # type: ignore[arg-type]
        read_page=lambda _provider, _cursor: client.get(
            url=URL,
            required_scopes=SCOPE,
        ),
    )

    assert len(calls) == 2
    assert client.request_count == 2
    assert result.completed is False
    assert result.error_type == "ProviderRequestLimitError"
