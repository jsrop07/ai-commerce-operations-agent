from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable


_WHITESPACE_PATTERN = re.compile(
    r"\s+"
)

_QUOTED_PATTERNS = (
    re.compile(r'"([^"]{2,120})"'),
    re.compile(r"'([^']{2,120})'"),
    re.compile(r"“([^”]{2,120})”"),
    re.compile(r"‘([^’]{2,120})’"),
)

_PAREN_PATTERN = re.compile(
    r"\([^()]{1,80}\)"
)

_EDITION_HINT_PATTERN = re.compile(
    r"(?i)"
    r"(?:"
    r"\bedition\b"
    r"|\bed\.?\b"
    r"|에디션"
    r"|판본"
    r"|(?:\d+)(?:st|nd|rd|th)\b"
    r"|(?:\d+)\s*판\b"
    r")"
)

_STANDALONE_EDITION_PATTERNS = (
    re.compile(
        r"(?i)\b\d+(?:st|nd|rd|th)\s+edition\b"
    ),
    re.compile(
        r"\b\d+\s*판\b"
    ),
    re.compile(
        r"(?i)\b(?:first|second|third)\s+edition\b"
    ),
)

_LANGUAGE_PATTERNS = (
    re.compile(r"한글판"),
    re.compile(r"한국어판"),
    re.compile(r"한국어"),
    re.compile(r"영문판"),
    re.compile(r"영어판"),
    re.compile(r"영어"),
    re.compile(r"(?i)\bkorean(?:\s+edition)?\b"),
    re.compile(r"(?i)\benglish(?:\s+edition)?\b"),
)

_EXPANSION_PATTERNS = (
    re.compile(r"확장판"),
    re.compile(r"확장팩"),
    re.compile(r"확장\s+세트"),
    re.compile(r"(?i)\bexpansion(?:\s+set|\s+pack)?\b"),
    re.compile(r"(?i)\bsupplement\b"),
)

_OPERATION_SUFFIX_PATTERN = re.compile(
    r"\s+(?:"
    r"재고(?:가|는|이)?"
    r"|입고(?:가|는|이)?"
    r"|가격(?:이|은|는)?"
    r"|배송(?:이|은|는)?"
    r"|호환(?:이|은|는)?"
    r"|구매(?:가|는|이)?"
    r"|주문(?:이|은|는)?"
    r")\b.*$"
)


@dataclass(frozen=True)
class QueryPreprocessResult:
    """
    Day 9 Retrieval query preprocessing 결과.

    정규화 과정에서는 상품 식별에 필요한
    문자열을 삭제하거나 다른 값으로 치환하지 않는다.
    """

    original_query: str
    normalized_query: str

    product_name_candidates: tuple[str, ...]
    brand_candidates: tuple[str, ...]

    language_expressions: tuple[str, ...]
    edition_expressions: tuple[str, ...]
    expansion_expressions: tuple[str, ...]

    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "original_query": self.original_query,
            "normalized_query": self.normalized_query,
            "product_name_candidates": list(
                self.product_name_candidates
            ),
            "brand_candidates": list(
                self.brand_candidates
            ),
            "language_expressions": list(
                self.language_expressions
            ),
            "edition_expressions": list(
                self.edition_expressions
            ),
            "expansion_expressions": list(
                self.expansion_expressions
            ),
            "warnings": list(
                self.warnings
            ),
        }


def _unique_preserve_order(
    values: Iterable[str],
) -> tuple[str, ...]:
    output: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = value.strip()

        if not cleaned:
            continue

        key = cleaned.casefold()

        if key in seen:
            continue

        seen.add(key)
        output.append(cleaned)

    return tuple(output)


def normalize_query(
    query: str,
) -> str:
    """
    검색용 query를 최소한으로 정규화한다.

    허용:
    - Unicode NFC 정규화
    - 연속 whitespace를 한 칸으로 정리
    - 앞뒤 whitespace 제거

    금지:
    - lower-case 강제 변환
    - 숫자/쉼표 제거
    - 괄호 제거
    - edition 제거
    - 상품 token alias 자동 치환
    """

    if not isinstance(
        query,
        str,
    ):
        raise TypeError(
            "query must be a string"
        )

    normalized = unicodedata.normalize(
        "NFC",
        query,
    )

    normalized = _WHITESPACE_PATTERN.sub(
        " ",
        normalized,
    ).strip()

    if not normalized:
        raise ValueError(
            "query must not be empty"
        )

    return normalized


def _find_pattern_matches(
    text: str,
    patterns: Iterable[
        re.Pattern[str]
    ],
) -> tuple[str, ...]:
    matches: list[
        tuple[int, str]
    ] = []

    for pattern in patterns:
        for match in pattern.finditer(
            text
        ):
            matches.append(
                (
                    match.start(),
                    match.group(0),
                )
            )

    matches.sort(
        key=lambda item: item[0]
    )

    return _unique_preserve_order(
        value
        for _, value in matches
    )


def _find_edition_expressions(
    text: str,
) -> tuple[str, ...]:
    matches: list[
        tuple[int, str]
    ] = []

    for match in _PAREN_PATTERN.finditer(
        text
    ):
        value = match.group(0)

        if _EDITION_HINT_PATTERN.search(
            value
        ):
            matches.append(
                (
                    match.start(),
                    value,
                )
            )

    for pattern in (
        _STANDALONE_EDITION_PATTERNS
    ):
        for match in pattern.finditer(
            text
        ):
            matches.append(
                (
                    match.start(),
                    match.group(0),
                )
            )

    matches.sort(
        key=lambda item: item[0]
    )

    return _unique_preserve_order(
        value
        for _, value in matches
    )


def _find_lexicon_matches(
    text: str,
    lexicon: Iterable[str] | None,
) -> tuple[str, ...]:
    """
    실제 query 표면 문자열을 그대로 반환한다.

    등록되지 않은 brand/product를 추측하지 않는다.
    """

    if lexicon is None:
        return ()

    matches: list[
        tuple[int, str]
    ] = []

    terms = sorted(
        {
            value.strip()
            for value in lexicon
            if isinstance(value, str)
            and value.strip()
        },
        key=len,
        reverse=True,
    )

    for term in terms:
        pattern = re.compile(
            re.escape(term),
            flags=re.IGNORECASE,
        )

        match = pattern.search(
            text
        )

        if match is None:
            continue

        matches.append(
            (
                match.start(),
                match.group(0),
            )
        )

    matches.sort(
        key=lambda item: item[0]
    )

    return _unique_preserve_order(
        value
        for _, value in matches
    )


def _find_quoted_candidates(
    text: str,
) -> tuple[str, ...]:
    candidates: list[
        tuple[int, str]
    ] = []

    for pattern in _QUOTED_PATTERNS:
        for match in pattern.finditer(
            text
        ):
            candidates.append(
                (
                    match.start(),
                    match.group(1),
                )
            )

    candidates.sort(
        key=lambda item: item[0]
    )

    return _unique_preserve_order(
        value
        for _, value in candidates
    )


def _fallback_product_candidate(
    text: str,
) -> str:
    """
    상품 lexicon match가 없을 때 사용하는
    보수적인 후보.

    운영 의도 suffix만 분리해보고,
    확실하지 않으면 전체 query를 보존한다.
    """

    candidate = (
        _OPERATION_SUFFIX_PATTERN.sub(
            "",
            text,
        ).strip()
    )

    if len(candidate) >= 2:
        return candidate

    return text


def preprocess_query(
    query: str,
    *,
    product_name_lexicon: Iterable[
        str
    ]
    | None = None,
    brand_lexicon: Iterable[
        str
    ]
    | None = None,
) -> QueryPreprocessResult:
    """
    D09-AI-01 공식 query preprocessing.

    실제 Product/Brand lexicon이 전달되면
    query 안에 실제로 존재하는 표현만
    candidate로 추출한다.

    새로운 상품명/brand를 생성하지 않는다.
    """

    normalized = normalize_query(
        query
    )

    product_matches = (
        _find_lexicon_matches(
            normalized,
            product_name_lexicon,
        )
    )

    quoted_candidates = (
        _find_quoted_candidates(
            normalized
        )
    )

    if product_matches:
        product_candidates = (
            product_matches
        )

    elif quoted_candidates:
        product_candidates = (
            quoted_candidates
        )

    else:
        product_candidates = (
            _fallback_product_candidate(
                normalized
            ),
        )

    brand_candidates = (
        _find_lexicon_matches(
            normalized,
            brand_lexicon,
        )
    )

    language_expressions = (
        _find_pattern_matches(
            normalized,
            _LANGUAGE_PATTERNS,
        )
    )

    edition_expressions = (
        _find_edition_expressions(
            normalized
        )
    )

    expansion_expressions = (
        _find_pattern_matches(
            normalized,
            _EXPANSION_PATTERNS,
        )
    )

    warnings: list[str] = []

    if (
        product_name_lexicon is None
    ):
        warnings.append(
            "PRODUCT_LEXICON_NOT_PROVIDED"
        )

    if brand_lexicon is None:
        warnings.append(
            "BRAND_LEXICON_NOT_PROVIDED"
        )

    return QueryPreprocessResult(
        original_query=query,
        normalized_query=normalized,
        product_name_candidates=(
            product_candidates
        ),
        brand_candidates=(
            brand_candidates
        ),
        language_expressions=(
            language_expressions
        ),
        edition_expressions=(
            edition_expressions
        ),
        expansion_expressions=(
            expansion_expressions
        ),
        warnings=tuple(
            warnings
        ),
    )