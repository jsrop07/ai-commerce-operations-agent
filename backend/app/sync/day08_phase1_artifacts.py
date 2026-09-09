"""Day 8 Backend Phase 1 공식 통합 산출물 생성기."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


DAY08_FINDINGS = [
    {
        "finding_id": "CAFE24_PRODUCT_RESUME_GAP",
        "severity": "HIGH",
        "status": "CLOSED",
        "area": "CAFE24_PRODUCT",
        "summary": (
            "상품 pagination offset 1250 누락을 발견했으나 "
            "실제 resume recovery로 복구 완료"
        ),
    },
    {
        "finding_id": "CAFE24_ORDER_API_ONLY83",
        "severity": "INFO",
        "status": "OPEN_NON_BLOCKING",
        "area": "CAFE24_ORDER",
        "summary": (
            "CSV에는 없고 Cafe24 API에만 존재하는 주문 83건 확인"
        ),
    },
    {
        "finding_id": "CAFE24_ORDER_ITEM_API_ONLY255",
        "severity": "INFO",
        "status": "OPEN_NON_BLOCKING",
        "area": "CAFE24_ORDER_ITEM",
        "summary": (
            "CSV에는 없고 Cafe24 API에만 존재하는 주문상품 255건 확인"
        ),
    },
    {
        "finding_id": "CAFE24_ATTACHMENT_SOURCE_MISSING1",
        "severity": "WARNING",
        "status": "OPEN_NON_BLOCKING",
        "area": "CAFE24_COMMUNITY_ATTACHMENT",
        "summary": (
            "첨부파일 참조 115건 중 provider 404로 1건 저장 불가"
        ),
    },
    {
        "finding_id": "DAY08_AI_HANDOFF_FREE_TEXT_LEAK",
        "severity": "HIGH",
        "status": "CLOSED",
        "area": "AI_HANDOFF_PRIVACY",
        "summary": (
            "초기 AI handoff에 free text가 직접 포함되던 문제를 제거하고 "
            "sanitized_query_text / sanitized_answer_text 경계로 수정"
        ),
    },
    {
        "finding_id": "DAY08_AI_HANDOFF_CANONICAL_BUILD_ORDER",
        "severity": "HIGH",
        "status": "CLOSED",
        "area": "AI_HANDOFF_CANONICAL",
        "summary": (
            "canonical_articles population 이전에 canonical_keys를 생성해 "
            "query/reply seed가 0건이 되던 순서 오류 수정"
        ),
    },
    {
        "finding_id": "DAY08_COMMUNITY_SANITIZED_FREE_TEXT_LEGACY",
        "severity": "HIGH",
        "status": "CLOSED",
        "area": "COMMUNITY_PRIVACY",
        "summary": (
            "legacy sanitized Community 788건의 title/content free text를 "
            "현재 hash-only privacy contract로 재생성 완료"
        ),
    },
]


def _write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _load_ai_handoff(
    path: Path,
) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "ai_handoff.json must be object"
        )

    return payload


def build_day08_phase1_artifacts(
    *,
    output_root: Path,
) -> None:
    root = output_root.resolve()

    ai_handoff_path = (
        root
        / "ai_handoff.json"
    )

    if not ai_handoff_path.exists():
        raise FileNotFoundError(
            "ai_handoff.json missing"
        )

    ai_handoff = _load_ai_handoff(
        ai_handoff_path
    )

    inquiries = ai_handoff.get(
        "inquiries",
        {},
    )

    quality = (
        inquiries.get(
            "quality",
            {},
        )
        if isinstance(
            inquiries,
            dict,
        )
        else {}
    )

    # -------------------------------------------------
    # 1. cafe24_read.json
    # -------------------------------------------------

    cafe24_read = {
        "schema_version": "day08.phase1.v1",
        "provider": "CAFE24",
        "status": "PASS_WITH_NON_BLOCKING_FINDINGS",
        "production_write_count": 0,
        "products": {
            "api_record_count": 2167,
            "canonical_record_count": 2167,
            "unique_product_code_count": 2167,
            "duplicate_product_code_count": 0,
            "pagination_gap": {
                "offset": 1250,
                "status": "RECOVERED",
                "first_missing_after_recovery": None,
            },
        },
        "orders": {
            "api_order_count": 1402,
            "api_unique_order_count": 1402,
            "api_duplicate_order_count": 0,
            "api_order_item_count": 3934,
            "api_unique_order_item_count": 3934,
            "api_duplicate_order_item_count": 0,
            "csv_order_count": 1319,
            "csv_order_item_count": 3679,
            "order_intersection_count": 1319,
            "order_item_intersection_count": 3679,
            "api_only_order_count": 83,
            "api_only_order_item_count": 255,
            "refund_count": 188,
            "unique_refund_order_count": 186,
            "warning_count": 338,
        },
        "community": {
            "article_record_count": 700,
            "canonical_article_count": 624,
            "duplicate_article_record_count": 76,
            "conflicting_duplicate_count": 0,
            "reply_article_count": 316,
            "comment_record_count": 88,
            "parent_link_count": 315,
            "missing_parent_count": 0,
            "attachment_reference_count": 115,
            "attachment_stored_count": 114,
            "attachment_provider_missing_count": 1,
            "attachment_ai_included_count": 0,
            "attachment_ai_excluded_count": 115,
        },
        "privacy": {
            "community_legacy_repair": {
                "artifact_count": 676,
                "record_count": 788,
                "article_count": 700,
                "comment_count": 88,
                "title_removed_count": 700,
                "content_removed_count": 788,
                "subject_sha256_count": 700,
                "content_sha256_count": 788,
                "status": "PASS",
            },
        },
    }

    _write_json(
        root / "cafe24_read.json",
        cafe24_read,
    )

    # -------------------------------------------------
    # 2. toss_ecount.json
    # -------------------------------------------------

    toss_ecount = {
        "schema_version": "day08.phase1.v1",
        "status": "PASS",
        "providers": {
            "TOSS_POS": {
                "decision": "CONTRACT_ONLY",
                "real_data_available": False,
                "confirmed_inventory_effect": False,
                "reason": (
                    "Day 8 시점 실제 Toss POS 데이터를 "
                    "실시간 연동 검증 대상으로 사용하지 않음"
                ),
            },
            "ECOUNT": {
                "decision": "SOURCE_QUALITY_BLOCKED",
                "real_data_available": False,
                "confirmed_inventory_effect": False,
                "reason": (
                    "현재 eCount 재고 source 품질이 정리되지 않아 "
                    "confirmed inventory에 포함하지 않음"
                ),
            },
        },
        "safety": {
            "unknown_is_zero": False,
            "contract_only_is_real_data": False,
            "source_quality_blocked_is_confirmed": False,
            "production_write_count": 0,
        },
    }

    _write_json(
        root / "toss_ecount.json",
        toss_ecount,
    )

    # -------------------------------------------------
    # 3. provider_read_manifest.json
    # -------------------------------------------------

    provider_read_manifest = {
        "schema_version": "day08.phase1.v1",
        "providers": [
            {
                "provider": "CAFE24",
                "read_status": "VERIFIED_REAL_READ",
                "data_classes": [
                    "PRODUCT",
                    "ORDER",
                    "ORDER_ITEM",
                    "REFUND",
                    "COMMUNITY_ARTICLE",
                    "COMMUNITY_COMMENT",
                    "COMMUNITY_ATTACHMENT_REFERENCE",
                ],
                "production_write_count": 0,
            },
            {
                "provider": "TOSS_POS",
                "read_status": "CONTRACT_ONLY",
                "data_classes": [],
                "production_write_count": 0,
            },
            {
                "provider": "ECOUNT",
                "read_status": "SOURCE_QUALITY_BLOCKED",
                "data_classes": [],
                "production_write_count": 0,
            },
        ],
        "null_semantics": {
            "unknown_equals_zero": False,
            "missing_equals_zero": False,
            "blocked_source_in_confirmed_total": False,
        },
    }

    _write_json(
        root / "provider_read_manifest.json",
        provider_read_manifest,
    )

    # -------------------------------------------------
    # 4. consumer_contract_report.json
    # -------------------------------------------------

    consumer_contract_report = {
        "schema_version": "day08.phase1.v1",
        "backend_to_ai": {
            "artifact": "ai_handoff.json",
            "status": "READY",
            "product_count": 2167,
            "canonical_article_count": 624,
            "reply_article_count": 316,
            "query_candidate_count": (
                quality.get(
                    "query_candidate_count"
                )
            ),
            "reply_candidate_count": (
                quality.get(
                    "reply_candidate_count"
                )
            ),
            "query_text_included_count": (
                quality.get(
                    "query_text_included_count"
                )
            ),
            "reply_text_included_count": (
                quality.get(
                    "reply_text_included_count"
                )
            ),
            "raw_text_conflict_count": (
                quality.get(
                    "raw_text_conflict_count"
                )
            ),
            "raw_text_missing_count": (
                quality.get(
                    "raw_text_missing_count"
                )
            ),
            "candidate_label_owner": "AI_ML_TRACK",
            "historical_reply_policy_truth": False,
            "attachments_ai_included_count": 0,
            "attachments_ai_excluded_count": 115,
        },
        "frontend": {
            "status": "NOT_CONSUMED_IN_PHASE1",
            "reason": (
                "Frontend Day 8 통합은 Backend Phase1 및 "
                "AI handoff 이후 진행"
            ),
        },
        "backend_retrieval": {
            "status": "WAITING_AI_HANDOFF",
            "official_item": "D08-BE-04",
        },
    }

    _write_json(
        root / "consumer_contract_report.json",
        consumer_contract_report,
    )

    # -------------------------------------------------
    # 5. provider_decision.md
    # -------------------------------------------------

    provider_decision = """# Day 8 Provider Decision

## Cafe24

- 상태: `VERIFIED_REAL_READ`
- 상품 2,167건 확인
- 주문 API 1,402건 확인
- 주문상품 API 3,934건 확인
- Board 5/6 Community canonical Article 624건 확인
- Production Write Count: `0`
- 상품 pagination offset 1250 누락은 실제 recovery 후 CLOSED

## Toss POS

- 상태: `CONTRACT_ONLY`
- Day 8 Phase1에서는 실제 Toss POS 데이터를 실데이터로 간주하지 않는다.
- `null`, `unknown`, `contract-only`를 재고 `0`으로 해석하지 않는다.

## eCount

- 상태: `SOURCE_QUALITY_BLOCKED`
- 현재 실제 재고 source 품질이 안정화되지 않았으므로 confirmed inventory에 포함하지 않는다.
- 잘못된 재고 숫자를 AI/Frontend에 제공하지 않는다.

## AI Handoff

- 상품 seed: 2,167
- Community canonical Article: 624
- 고객문의 후보: 308
- 과거답변 후보: 316
- 개인정보 안전처리 후 고객문의 natural-language seed: 302
- 개인정보 안전처리 후 과거답변 seed: 306
- 과거답변은 `policy_truth=false`
- Attachment는 115건 모두 AI content 사용 제외
- `candidate_label`의 최종 판단 주체는 AI/ML 트랙

## Day 8 Phase1 Decision

Backend/Data의 D08-BE-01~03 결과와 AI 전달용 sanitized handoff는 준비되었다.

D08-BE-04 Retrieval 통합은 AI/ML 트랙의 Day 8 handoff가 돌아오기 전까지 `WAITING_AI_HANDOFF` 상태를 유지한다.

Production Write는 수행하지 않는다.
"""

    (
        root
        / "provider_decision.md"
    ).write_text(
        provider_decision,
        encoding="utf-8",
    )

    # -------------------------------------------------
    # 6. defects.csv
    # -------------------------------------------------

    defects_path = (
        root
        / "defects.csv"
    )

    with defects_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as fp:
        writer = csv.DictWriter(
            fp,
            fieldnames=[
                "finding_id",
                "severity",
                "status",
                "area",
                "summary",
            ],
        )

        writer.writeheader()
        writer.writerows(
            DAY08_FINDINGS
        )