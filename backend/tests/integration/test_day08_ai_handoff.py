from pathlib import Path

import json

from backend.app.sync.day08_ai_handoff import (
    build_day08_ai_handoff,
)
from backend.app.worker.privacy.text_redaction import (
    EMAIL_PATTERN,
    IPV4_PATTERN,
    ORDER_ID_PATTERN,
    PHONE_PATTERN,
)


PROTECTED_ROOT = Path(
    r"C:\ai-commerce-private\cafe24"
)


def test_day08_ai_handoff_is_sanitized(
    tmp_path: Path,
) -> None:
    output = (
        tmp_path
        / "day08_ai_handoff.json"
    )

    result = build_day08_ai_handoff(
        protected_root=PROTECTED_ROOT,
        output_path=output,
    )

    assert result.product_count == 2167
    assert (
        result.product_code_unique_count
        == 2167
    )

    assert result.article_record_count == 700
    assert (
        result.canonical_article_count
        == 624
    )

    assert (
        result
        .duplicate_article_excluded_count
        == 76
    )

    assert (
        result
        .conflicting_article_quarantine_count
        == 0
    )

    assert result.reply_article_count == 316
    assert result.comment_record_count == 88

    assert (
        result.attachment_reference_count
        == 115
    )

    assert (
        result.attachment_ai_included_count
        == 0
    )

    assert (
        result.attachment_ai_excluded_count
        == 115
    )

    assert (
        result.product_mapping_coverage_count
        == 2167
    )

    assert (
        result.product_mapping_conflict_count
        == 0
    )

    assert (
        result.product_mapping_unknown_count
        == 0
    )

    assert result.pii_scan_passed is True
    assert result.secret_scan_passed is True

    assert output.exists()
    assert len(result.output_sha256) == 64

    # ---------------------------------------------
    # Day 8 AI handoff privacy regression
    # ---------------------------------------------
    text = output.read_text(
        encoding="utf-8"
    )

    for forbidden in (
        "<PHONE>",
        "<EMAIL>",
        "<IP>",
        "<ADDRESS>",
        "<NAME>",
        "<ORDER_REF>",
        '"access_token"',
        '"refresh_token"',
        '"client_secret"',
        '"authorization"',
    ):
        assert (
            forbidden.lower()
            not in text.lower()
        )

    # content_sha256는 허용하지만
    # raw 자유문자열 content 필드는 금지한다.
    assert '"content":' not in text

    payload = json.loads(
        output.read_text(
            encoding="utf-8"
        )
    )

    inquiries = payload[
        "inquiries"
    ]

    quality = inquiries[
        "quality"
    ]

    assert (
        quality["query_candidate_count"]
        == 308
    )

    assert (
        quality["reply_candidate_count"]
        == 316
    )

    assert (
        quality["query_candidate_count"]
        + quality["reply_candidate_count"]
        == 624
    )

    assert (
        quality["query_text_included_count"]
        + quality["query_text_excluded_count"]
        == 308
    )

    assert (
        quality["reply_text_included_count"]
        + quality["reply_text_excluded_count"]
        == 316
    )

    assert (
        quality["raw_text_conflict_count"]
        == 0
    )

    seeds = inquiries[
        "query_eval_seed"
    ]

    assert len(seeds) == (
        quality["query_text_included_count"]
        + quality["reply_text_included_count"]
    )

    for seed in seeds:
        assert seed[
            "candidate_label"
        ] is None

        assert seed[
            "board_no"
        ] in {
            5,
            6,
        }

        if (
            seed["source_type"]
            == "CUSTOMER_INQUIRY"
        ):
            safe_text = seed[
                "sanitized_query_text"
            ]

            assert (
                "sanitized_answer_text"
                not in seed
            )

        else:
            assert (
                seed["source_type"]
                == "HISTORICAL_REPLY_CANDIDATE"
            )

            assert (
                seed["policy_truth"]
                is False
            )

            safe_text = seed[
                "sanitized_answer_text"
            ]

        assert EMAIL_PATTERN.search(
            safe_text
        ) is None

        assert PHONE_PATTERN.search(
            safe_text
        ) is None

        assert IPV4_PATTERN.search(
            safe_text
        ) is None

        assert ORDER_ID_PATTERN.search(
            safe_text
        ) is None

        for marker in (
            "<PHONE>",
            "<EMAIL>",
            "<IP>",
            "<ORDER_REF>",
        ):
            assert marker not in safe_text


def test_day08_ai_handoff_is_deterministic(
    tmp_path: Path,
) -> None:
    first = (
        tmp_path
        / "first.json"
    )

    second = (
        tmp_path
        / "second.json"
    )

    first_result = (
        build_day08_ai_handoff(
            protected_root=PROTECTED_ROOT,
            output_path=first,
        )
    )

    second_result = (
        build_day08_ai_handoff(
            protected_root=PROTECTED_ROOT,
            output_path=second,
        )
    )

    assert (
        first.read_bytes()
        == second.read_bytes()
    )

    assert (
        first_result.output_sha256
        == second_result.output_sha256
    )