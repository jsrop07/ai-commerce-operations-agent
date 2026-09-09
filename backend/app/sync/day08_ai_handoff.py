"""Day 8 Backend → AI sanitized handoff package builder."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import html
import re

from backend.app.sync.cafe24_community_integrity import (
    run_cafe24_community_integrity,
)
from backend.app.worker.privacy.snapshot_manifest import (
    select_canonical_sanitized_artifacts,
)
from backend.app.worker.privacy.text_redaction import (
    EMAIL_PATTERN,
    IPV4_PATTERN,
    ORDER_ID_PATTERN,
    PHONE_PATTERN,
    redact_free_text,
)

@dataclass(frozen=True)
class Day08AIHandoffResult:
    product_count: int
    product_code_unique_count: int

    article_record_count: int
    canonical_article_count: int
    duplicate_article_excluded_count: int
    conflicting_article_quarantine_count: int

    reply_article_count: int
    comment_record_count: int

    attachment_reference_count: int
    attachment_ai_included_count: int
    attachment_ai_excluded_count: int

    product_mapping_coverage_count: int
    product_mapping_conflict_count: int
    product_mapping_unknown_count: int

    pii_scan_passed: bool
    secret_scan_passed: bool

    output_path: Path
    output_sha256: str


_FORBIDDEN_KEYS = {
    "customer_name",
    "buyer_name",
    "recipient_name",
    "receiver_name",
    "email",
    "phone",
    "mobile",
    "address",
    "zipcode",
    "password",
    "access_token",
    "refresh_token",
    "client_secret",
    "authorization",
    "cookie",
}
_FORBIDDEN_VALUE_MARKERS = (
    "<PHONE>",
    "<EMAIL>",
    "<ADDRESS>",
    "<NAME>",
    "<ORDER_REF>",
)

def _load_json(path: Path) -> Any:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


def _contains_forbidden_key(
    value: Any,
) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _FORBIDDEN_KEYS:
                return True
            if _contains_forbidden_key(child):
                return True

    elif isinstance(value, list):
        return any(
            _contains_forbidden_key(item)
            for item in value
        )

    return False



def _contains_forbidden_value(
    value: Any,
) -> bool:
    if isinstance(value, str):
        lowered = value.lower()

        return any(
            marker.lower() in lowered
            for marker
            in _FORBIDDEN_VALUE_MARKERS
        )

    if isinstance(value, dict):
        return any(
            _contains_forbidden_value(child)
            for child
            in value.values()
        )

    if isinstance(value, list):
        return any(
            _contains_forbidden_value(item)
            for item
            in value
        )

    return False

_REDACTION_MARKERS = (
    "<PHONE>",
    "<EMAIL>",
    "<IP>",
    "<ORDER_REF>",
)

_HTML_BREAK_PATTERN = re.compile(
    r"(?i)<(?:br\s*/?|/p|/div)>"
)

_HTML_TAG_PATTERN = re.compile(
    r"<[^>]+>"
)

_SENSITIVE_LABEL_PATTERN = re.compile(
    r"^\s*("
    r"이름|성함|수령인|받는\s*분|"
    r"연락처|전화번호|휴대폰|핸드폰|"
    r"이메일|메일주소|"
    r"주소|배송지|우편번호|"
    r"주문번호"
    r")\s*[:：]"
)

_PERSONAL_NAME_PHRASE_PATTERN = re.compile(
    r"(?:제\s*이름은|"
    r"제\s*성함은|"
    r"이름은|성함은)"
    r"\s*[가-힣]{2,4}"
)

_KOREAN_ADDRESS_PATTERN = re.compile(
    r"(?:"
    r"특별시|광역시|특별자치시|"
    r"특별자치도|"
    r"[가-힣]+도|"
    r"[가-힣]+시|"
    r"[가-힣]+군|"
    r"[가-힣]+구"
    r")"
    r".{0,40}"
    r"(?:"
    r"[가-힣0-9]+로|"
    r"[가-힣0-9]+길|"
    r"[가-힣0-9]+동|"
    r"[가-힣0-9]+읍|"
    r"[가-힣0-9]+면|"
    r"[가-힣0-9]+리"
    r")"
    r".{0,20}\d"
)

_POSTCODE_PATTERN = re.compile(
    r"(?<!\d)\d{5}(?!\d)"
)


def _normalize_free_text(
    value: str,
) -> str:
    value = html.unescape(value)

    value = _HTML_BREAK_PATTERN.sub(
        "\n",
        value,
    )

    value = _HTML_TAG_PATTERN.sub(
        " ",
        value,
    )

    value = value.replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    )

    return value


def _safe_ai_text(
    *,
    title: str,
    content: str,
) -> tuple[str | None, str | None]:
    combined = "\n".join(
        part
        for part in (
            title,
            content,
        )
        if part.strip()
    )

    combined = _normalize_free_text(
        combined
    )

    # 기존 Backend privacy redaction을
    # 반드시 먼저 재사용한다.
    combined = redact_free_text(
        combined
    )

    safe_lines: list[str] = []

    removed_sensitive_line = False

    for raw_line in combined.splitlines():
        line = re.sub(
            r"\s+",
            " ",
            raw_line,
        ).strip()

        if not line:
            continue

        # 이미 PII가 검출된 줄은
        # marker만 남기는 대신 줄 전체를 버린다.
        if any(
            marker in line
            for marker in _REDACTION_MARKERS
        ):
            removed_sensitive_line = True
            continue

        # 이름:, 주소:, 전화번호: 같은
        # 개인정보 입력 형식은 줄 전체 제외.
        if _SENSITIVE_LABEL_PATTERN.search(
            line
        ):
            removed_sensitive_line = True
            continue

        if _PERSONAL_NAME_PHRASE_PATTERN.search(
            line
        ):
            removed_sensitive_line = True
            continue

        # 주소값 자체로 보이는 경우만 제거한다.
        # "배송지 변경 가능한가요?" 같은
        # intent 문장은 제거하지 않는다.
        if _KOREAN_ADDRESS_PATTERN.search(
            line
        ):
            removed_sensitive_line = True
            continue

        if _POSTCODE_PATTERN.search(
            line
        ):
            removed_sensitive_line = True
            continue

        safe_lines.append(
            line
        )

    safe_text = " ".join(
        safe_lines
    ).strip()

    # redaction 이후 실제 의미가 거의
    # 남지 않은 record는 AI에서 제외한다.
    meaningful_length = len(
        re.sub(
            r"\s+",
            "",
            safe_text,
        )
    )

    if meaningful_length < 5:
        return (
            None,
            "NO_USABLE_TEXT_AFTER_REDACTION",
        )

    # 방어적 최종 PII 재검사.
    if (
        EMAIL_PATTERN.search(safe_text)
        or PHONE_PATTERN.search(safe_text)
        or IPV4_PATTERN.search(safe_text)
        or ORDER_ID_PATTERN.search(safe_text)
        or _PERSONAL_NAME_PHRASE_PATTERN.search(
            safe_text
        )
        or _KOREAN_ADDRESS_PATTERN.search(
            safe_text
        )
    ):
        return (
            None,
            "PII_PATTERN_REMAINED",
        )

    if any(
        marker in safe_text
        for marker in _REDACTION_MARKERS
    ):
        return (
            None,
            "PII_MARKER_REMAINED",
        )

    if removed_sensitive_line:
        return (
            safe_text,
            "SENSITIVE_LINES_REMOVED",
        )

    return safe_text, None

def _load_raw_article_texts(
    *,
    protected_root: Path,
    canonical_keys: set[
        tuple[int, int]
    ],
) -> tuple[
    dict[
        tuple[int, int],
        dict[str, Any],
    ],
    set[tuple[int, int]],
]:
    raw_root = (
        protected_root
        / "cafe24"
        / "raw"
    )

    found: dict[
        tuple[int, int],
        dict[str, Any],
    ] = {}

    conflicting: set[
        tuple[int, int]
    ] = set()

    page_files = sorted(
        raw_root.rglob(
            "page-*.json"
        )
    )

    for path in page_files:
        if path.parent.name not in {
            "board_5_articles",
            "board_6_articles",
        }:
            continue

        payload = _load_json(
            path
        )

        if not isinstance(
            payload,
            dict,
        ):
            continue

        rows = payload.get(
            "articles"
        )

        if not isinstance(
            rows,
            list,
        ):
            continue

        for row in rows:
            if not isinstance(
                row,
                dict,
            ):
                continue

            board_no = _as_int(
                row.get(
                    "board_no"
                )
            )

            article_no = _as_int(
                row.get(
                    "article_no"
                )
            )

            if (
                board_no is None
                or article_no is None
            ):
                continue

            key = (
                board_no,
                article_no,
            )

            if key not in canonical_keys:
                continue

            # 개인정보 필드는 아예 담지 않는다.
            candidate = {
                "board_no": board_no,
                "article_no": article_no,
                "parent_article_no": (
                    _as_int(
                        row.get(
                            "parent_article_no"
                        )
                    )
                ),
                "reply": row.get(
                    "reply"
                ),
                "reply_depth": row.get(
                    "reply_depth"
                ),
                "title": (
                    row.get("title")
                    if isinstance(
                        row.get("title"),
                        str,
                    )
                    else ""
                ),
                "content": (
                    row.get("content")
                    if isinstance(
                        row.get("content"),
                        str,
                    )
                    else ""
                ),
            }

            existing = found.get(
                key
            )

            if existing is None:
                found[key] = candidate
                continue

            # 같은 canonical key인데
            # Raw 자연어 내용이 다르면
            # AI에는 사용하지 않는다.
            if (
                existing["title"]
                != candidate["title"]
                or existing["content"]
                != candidate["content"]
            ):
                conflicting.add(
                    key
                )

    for key in conflicting:
        found.pop(
            key,
            None,
        )

    return found, conflicting

def _as_int(
    value: Any,
) -> int | None:
    if type(value) is int:
        return value

    if isinstance(value, str):
        stripped = value.strip()

        if stripped.isdigit():
            return int(stripped)

    return None

def _is_reply_article(
    record: dict[str, Any],
) -> bool:
    parent_article_no = _as_int(
        record.get(
            "parent_article_no"
        )
    )

    reply = record.get(
        "reply"
    )

    reply_depth = _as_int(
        record.get(
            "reply_depth"
        )
    )

    return (
        reply in {
            "T",
            "Y",
            True,
            1,
            "1",
        }
        or (
            reply_depth is not None
            and reply_depth > 0
        )
        or (
            parent_article_no is not None
            and parent_article_no > 0
        )
    )
def _load_canonical_records(
    *,
    protected_root: Path,
    resource: str,
    filename_pattern: str = "*.sanitized.json",
) -> list[dict[str, Any]]:
    selection = (
        select_canonical_sanitized_artifacts(
            protected_root=protected_root,
            resource=resource,
            filename_pattern=filename_pattern,
        )
    )

    if (
        selection.missing_manifest_count != 0
        or selection.invalid_artifact_count != 0
    ):
        raise ValueError(
            f"{resource} canonical selection invalid"
        )

    records: list[dict[str, Any]] = []

    for path in selection.artifacts:
        payload = _load_json(path)

        items = payload.get(
            "records",
            [],
        )

        if not isinstance(items, list):
            raise ValueError(
                f"{resource} records must be list"
            )

        records.extend(
            item
            for item in items
            if isinstance(item, dict)
        )

    return records


def build_day08_ai_handoff(
    *,
    protected_root: Path,
    output_path: Path,
) -> Day08AIHandoffResult:
    root = protected_root.resolve()

    products = _load_canonical_records(
        protected_root=root,
        resource="products",
        filename_pattern=(
            "product-full-*.sanitized.json"
        ),
    )

    categories = _load_canonical_records(
        protected_root=root,
        resource="categories",
    )

    board5_articles = _load_canonical_records(
        protected_root=root,
        resource="board_5_articles",
    )

    board6_articles = _load_canonical_records(
        protected_root=root,
        resource="board_6_articles",
    )

    comments = _load_canonical_records(
        protected_root=root,
        resource="article_comments",
    )

    community = (
        run_cafe24_community_integrity(
            protected_root=root,
        )
    )

    if not community.passed:
        raise ValueError(
            "community integrity is not safe "
            "for Day8 AI handoff"
        )

    product_codes = [
        str(record.get("product_code")).strip()
        for record in products
        if record.get("product_code")
        not in (None, "")
    ]

    unique_product_codes = set(
        product_codes
    )

    product_mapping_coverage_count = len(
        unique_product_codes
    )

    product_mapping_conflict_count = (
        len(product_codes)
        - len(unique_product_codes)
    )

    product_mapping_unknown_count = (
        len(products)
        - len(product_codes)
    )

    canonical_articles: dict[
        tuple[int, int],
        dict[str, Any],
    ] = {}

    # 1. 먼저 canonical_articles를 채운다.
    for record in (
        board5_articles
        + board6_articles
    ):
        board_no = _as_int(
            record.get(
                "board_no"
            )
        )

        article_no = _as_int(
            record.get(
                "article_no"
            )
        )

        if (
            board_no is not None
            and article_no is not None
        ):
            canonical_articles[
                (
                    board_no,
                    article_no,
                )
            ] = record


    # 2. 그 다음 canonical_keys를 만든다.
    canonical_keys = set(
        canonical_articles
    )


    # 3. 그 다음 raw text 연결
    raw_articles, raw_text_conflicts = (
        _load_raw_article_texts(
            protected_root=root,
            canonical_keys=canonical_keys,
        )
    )


    # 4. 통계 초기화
    query_candidate_count = 0
    reply_candidate_count = 0

    query_text_included_count = 0
    query_text_excluded_count = 0

    reply_text_included_count = 0
    reply_text_excluded_count = 0

    no_usable_text_count = 0
    pii_pattern_excluded_count = 0
    sensitive_lines_removed_count = 0

    board5_included_count = 0
    board6_included_count = 0

    query_eval_seed: list[
        dict[str, Any]
    ] = []


    # 5. 마지막에 canonical 624개 순회
    for key in sorted(
        canonical_keys
    ):
        canonical = (
            canonical_articles[key]
        )

        is_reply = _is_reply_article(
            canonical
        )

        if is_reply:
            reply_candidate_count += 1
        else:
            query_candidate_count += 1

        raw = raw_articles.get(
            key
        )

        if raw is None:
            if is_reply:
                reply_text_excluded_count += 1
            else:
                query_text_excluded_count += 1

            continue

        safe_text, sanitization_reason = (
            _safe_ai_text(
                title=raw["title"],
                content=raw["content"],
            )
        )

        if safe_text is None:
            if is_reply:
                reply_text_excluded_count += 1
            else:
                query_text_excluded_count += 1

            if (
                sanitization_reason
                == "NO_USABLE_TEXT_AFTER_REDACTION"
            ):
                no_usable_text_count += 1
            else:
                pii_pattern_excluded_count += 1

            continue

        if (
            sanitization_reason
            == "SENSITIVE_LINES_REMOVED"
        ):
            sensitive_lines_removed_count += 1

        board_no = key[0]

        source_role = (
            "PRODUCT_AFTER_SERVICE_INQUIRY"
            if board_no == 5
            else "ORDER_PRODUCT_INQUIRY"
        )

        if is_reply:
            reply_text_included_count += 1

            seed = {
                "board_no": board_no,
                "article_no": key[1],
                "parent_article_no": (
                    _as_int(
                        canonical.get(
                            "parent_article_no"
                        )
                    )
                ),
                "source_role": source_role,
                "source_type": (
                    "HISTORICAL_REPLY_CANDIDATE"
                ),
                "sanitized_answer_text": (
                    safe_text
                ),
                "policy_truth": False,
                "candidate_label": None,
            }

        else:
            query_text_included_count += 1

            seed = {
                "board_no": board_no,
                "article_no": key[1],
                "parent_article_no": None,
                "source_role": source_role,
                "source_type": (
                    "CUSTOMER_INQUIRY"
                ),
                "sanitized_query_text": (
                    safe_text
                ),
                "candidate_label": None,
            }

        if board_no == 5:
            board5_included_count += 1
        elif board_no == 6:
            board6_included_count += 1

        query_eval_seed.append(
            seed
        )

    article_seed = [
        {
            "board_no": _as_int(
                record.get(
                    "board_no"
                )
            ),
            "article_no": _as_int(
                record.get(
                    "article_no"
                )
            ),
            "parent_article_no": _as_int(
                record.get(
                    "parent_article_no"
                )
            ),
            "reply": record.get("reply"),
            "reply_depth": (
                record.get("reply_depth")
            ),
            "subject_sha256": (
                record.get(
                    "subject_sha256"
                )
            ),
            "content_sha256": (
                record.get(
                    "content_sha256"
                )
            ),
            "has_attachments": (
                record.get(
                    "has_attachments",
                    False,
                )
            ),
            "attachment_count": (
                record.get(
                    "attachment_count",
                    0,
                )
            ),
        }
        for record
        in canonical_articles.values()
    ]

    comment_seed = [
        {
            "board_no": record.get(
                "board_no"
            ),
            "article_no": record.get(
                "article_no"
            ),
            "comment_no": record.get(
                "comment_no"
            ),
            "parent_comment_no": record.get(
                "parent_comment_no"
            ),
            "content_sha256": record.get(
                "content_sha256"
            ),
        }
        for record in comments
    ]

    product_seed = [
        {
            "product_code": (
                record.get(
                    "product_code"
                )
            ),
            "product_no": (
                record.get(
                    "product_no"
                )
            ),
            "custom_product_code": (
                record.get(
                    "custom_product_code"
                )
            ),
            "product_name": (
                record.get(
                    "product_name"
                )
            ),
        }
        for record in products
    ]

    category_seed = [
        {
            "category_no": record.get(
                "category_no"
            ),
            "category_name": record.get(
                "category_name"
            ),
            "parent_category_no": record.get(
                "parent_category_no"
            ),
            "category_depth": record.get(
                "category_depth"
            ),
            "use_display": record.get(
                "use_display"
            ),
        }
        for record in categories
    ]

    payload: dict[str, Any] = {
        "schema_version": (
            "day08-ai-handoff.v1"
        ),
        "source_classification": {
            "CAFE24": {
                "products": (
                    "LIVE_READ+FILE_IMPORT"
                ),
                "categories": "LIVE_READ",
                "orders": (
                    "LIVE_READ+FILE_IMPORT"
                ),
                "order_items": (
                    "LIVE_READ+FILE_IMPORT"
                ),
                "refunds": "LIVE_READ",
                "boards": "LIVE_READ",
                "articles": "LIVE_READ",
                "comments": "LIVE_READ",
                "attachments": (
                    "LIVE_READ_AI_EXCLUDED"
                ),
            },
            "TOSS_POS": (
                "CONTRACT_ONLY"
            ),
            "ECOUNT": (
                "SOURCE_QUALITY_BLOCKED"
            ),
        },
        "products": {
            "canonical_count": (
                len(products)
            ),
            "unique_product_code_count": (
                len(unique_product_codes)
            ),
            "mapping": {
                "coverage_count": (
                    product_mapping_coverage_count
                ),
                "conflict_count": (
                    product_mapping_conflict_count
                ),
                "unknown_count": (
                    product_mapping_unknown_count
                ),
            },
            "seed": product_seed,
        },
        "categories": {
            "seed": category_seed,
            "historical_preorder_warning": (
                "Current category membership "
                "must not be used as proof of "
                "historical preorder status."
            ),
        },
        "inquiries": {
            "collected_article_count": (
                community.article_record_count
            ),
            "canonical_candidate_count": (
                community.unique_article_count
            ),
            "dedupe_excluded_count": (
                community
                .duplicate_article_record_count
            ),
            "conflict_quarantine_count": (
                community
                .conflicting_duplicate_count
            ),
            "reply_article_count": (
                community.reply_article_count
            ),
            "comment_record_count": (
                community.comment_record_count
            ),
            "board_scope": [5, 6],
            "article_seed": article_seed,
            "comment_seed": comment_seed,
            "board_roles": {
                "5": (
                    "PRODUCT_AFTER_SERVICE_INQUIRY"
                ),
                "6": (
                    "ORDER_PRODUCT_INQUIRY"
                ),
            },
            "candidate_labels": [
                "AFTER_SERVICE",
                "DELIVERY_STATUS",
                "DELIVERY_ADDRESS_CHANGE",
                "CANCEL_REFUND",
                "RESTOCK_DATE",
                "UNREGISTERED_PRODUCT_ORDER",
                "OTHER",
            ],
            "query_eval_seed": (
                query_eval_seed
            ),
            "quality": {
                "query_candidate_count": (
                    query_candidate_count
                ),
                "reply_candidate_count": (
                    reply_candidate_count
                ),
                "query_text_included_count": (
                    query_text_included_count
                ),
                "query_text_excluded_count": (
                    query_text_excluded_count
                ),
                "reply_text_included_count": (
                    reply_text_included_count
                ),
                "reply_text_excluded_count": (
                    reply_text_excluded_count
                ),
                "no_usable_text_after_redaction_count": (
                    no_usable_text_count
                ),
                "pii_pattern_excluded_count": (
                    pii_pattern_excluded_count
                ),
                "sensitive_lines_removed_count": (
                    sensitive_lines_removed_count
                ),
                "raw_text_conflict_count": (
                    len(raw_text_conflicts)
                ),
                "raw_text_missing_count": (
                    len(
                        canonical_keys
                        - set(raw_articles)
                        - raw_text_conflicts
                    )
                ),
                "board_5_included_count": (
                    board5_included_count
                ),
                "board_6_included_count": (
                    board6_included_count
                ),
            },
        },
        "attachments": {
            "reference_count": (
                community
                .unique_attachment_ref_count
            ),
            "backend_available_count": (
                community
                .attachment_file_count
            ),
            "provider_source_missing_count": (
                community
                .attachment_source_missing_count
            ),
            "ai_included_count": 0,
            "ai_excluded_count": (
                community
                .unique_attachment_ref_count
            ),
            "exclusion_reason": (
                "Attachment AI ingestion is "
                "blocked until MIME, size, "
                "malware, PII and OCR "
                "sanitization checks exist."
            ),
        },
        "safety": {
            "raw_data_included": False,
            "credentials_included": False,
            "customer_pii_included": False,
            "production_write_allowed": False,
        },
    }

    forbidden_key_found = (
        _contains_forbidden_key(
            payload
        )
    )

    forbidden_value_found = (
        _contains_forbidden_value(
            payload
        )
    )

    pii_scan_passed = (
        not forbidden_value_found
    )

    secret_scan_passed = (
        not forbidden_key_found
    )

    if not pii_scan_passed:
        raise ValueError(
            "Day8 AI handoff contains "
            "forbidden PII marker"
        )

    if not secret_scan_passed:
        raise ValueError(
            "Day8 AI handoff contains "
            "forbidden secret-like key"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    output_sha256 = _sha256(
        output_path
    )

    return Day08AIHandoffResult(
        product_count=len(products),
        product_code_unique_count=(
            len(unique_product_codes)
        ),
        article_record_count=(
            community.article_record_count
        ),
        canonical_article_count=(
            community.unique_article_count
        ),
        duplicate_article_excluded_count=(
            community
            .duplicate_article_record_count
        ),
        conflicting_article_quarantine_count=(
            community
            .conflicting_duplicate_count
        ),
        reply_article_count=(
            community.reply_article_count
        ),
        comment_record_count=(
            community.comment_record_count
        ),
        attachment_reference_count=(
            community
            .unique_attachment_ref_count
        ),
        attachment_ai_included_count=0,
        attachment_ai_excluded_count=(
            community
            .unique_attachment_ref_count
        ),
        product_mapping_coverage_count=(
            product_mapping_coverage_count
        ),
        product_mapping_conflict_count=(
            product_mapping_conflict_count
        ),
        product_mapping_unknown_count=(
            product_mapping_unknown_count
        ),
        pii_scan_passed=(
            pii_scan_passed
        ),
        secret_scan_passed=(
            secret_scan_passed
        ),
        output_path=output_path,
        output_sha256=output_sha256,
    )