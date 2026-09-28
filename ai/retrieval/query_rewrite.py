from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from ai.retrieval.query_preprocess import (
    QueryPreprocessResult,
    preprocess_query,
)


_REFERENTIAL_PATTERN = re.compile(
    r"(그거|이거|저거|"
    r"그\s*상품|이\s*상품|저\s*상품|"
    r"그\s*제품|이\s*제품|저\s*제품|"
    r"해당\s*상품|해당\s*제품)"
)

_QUANTITY_PATTERNS = (
    re.compile(
        r"(?i)\b\d+\s*"
        r"(?:개|박스|세트|팩|권|ea|pcs?)\b"
    ),
)

_NEGATION_PATTERNS = (
    re.compile(r"안\s+\S+"),
    re.compile(r"못\s+\S+"),
    re.compile(r"\S+\s*말고"),
    re.compile(r"\S+\s*아니"),
    re.compile(r"\S+\s*없"),
    re.compile(r"(?i)\b(?:not|without|except)\b"),
)

_TIME_PATTERNS = (
    re.compile(
        r"(이번\s*주\s*안에|"
        r"이번\s*주말|"
        r"주말\s*전|"
        r"이번\s*주|다음\s*주|"
        r"이번\s*달|다음\s*달|"
        r"오늘|내일|모레|어제)"
    ),
    re.compile(
        r"\b\d{4}[-./]\d{1,2}[-./]\d{1,2}\b"
    ),
    re.compile(
        r"\b\d{1,2}월\s*\d{1,2}일\b"
    ),
)


@dataclass(frozen=True)
class PreservedEntity:
    entity_type: str
    value: str
    source: str

    def to_dict(self) -> dict[str, str]:
        return {
            "entity_type": self.entity_type,
            "value": self.value,
            "source": self.source,
        }


@dataclass(frozen=True)
class ChangedField:
    field: str
    before: str
    after: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "field": self.field,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class QueryRewriteResult:
    original_query: str
    rewritten_query: str
    preserved_entities: tuple[
        PreservedEntity,
        ...
    ]
    changed_fields: tuple[
        ChangedField,
        ...
    ]
    reason: str
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "original_query":
                self.original_query,
            "rewritten_query":
                self.rewritten_query,
            "preserved_entities": [
                item.to_dict()
                for item
                in self.preserved_entities
            ],
            "changed_fields": [
                item.to_dict()
                for item
                in self.changed_fields
            ],
            "reason": self.reason,
            "warnings":
                list(self.warnings),
        }


def _unique_entities(
    entities: Iterable[PreservedEntity],
) -> tuple[PreservedEntity, ...]:
    output: list[PreservedEntity] = []
    seen: set[
        tuple[str, str, str]
    ] = set()

    for entity in entities:
        key = (
            entity.entity_type,
            entity.value.casefold(),
            entity.source,
        )

        if key in seen:
            continue

        seen.add(key)
        output.append(entity)

    return tuple(output)


def _find_pattern_values(
    text: str,
    patterns: Iterable[
        re.Pattern[str]
    ],
) -> tuple[str, ...]:
    matches: list[
        tuple[int, int, str]
    ] = []

    for pattern in patterns:
        for match in pattern.finditer(
            text
        ):
            matches.append(
                (
                    match.start(),
                    match.end(),
                    match.group(0),
                )
            )

    # 같은 시작점 또는 겹치는 표현에서는
    # 더 긴 surface form을 우선한다.
    matches.sort(
        key=lambda item: (
            item[0],
            -(item[1] - item[0]),
        )
    )

    selected: list[
        tuple[int, int, str]
    ] = []

    for (
        start,
        end,
        value,
    ) in matches:
        cleaned = value.strip()

        if not cleaned:
            continue

        overlaps_existing = any(
            start < selected_end
            and end > selected_start
            for (
                selected_start,
                selected_end,
                _,
            )
            in selected
        )

        if overlaps_existing:
            continue

        selected.append(
            (
                start,
                end,
                cleaned,
            )
        )

    selected.sort(
        key=lambda item: item[0]
    )

    output: list[str] = []
    seen: set[str] = set()

    for _, _, value in selected:
        key = value.casefold()

        if key in seen:
            continue

        seen.add(key)
        output.append(value)

    return tuple(output)

def _is_referential_text(
    text: str,
) -> bool:
    return bool(
        _REFERENTIAL_PATTERN.search(
            text
        )
    )


def _collect_current_entities(
    query: str,
    preprocessed: QueryPreprocessResult,
) -> tuple[PreservedEntity, ...]:
    entities: list[
        PreservedEntity
    ] = []

    for value in _remove_contained_values(
        preprocessed.language_expressions
    ):
        if _is_referential_text(
            value
        ):
            continue

        entities.append(
            PreservedEntity(
                entity_type="product_name",
                value=value,
                source="CURRENT_QUERY",
            )
        )

    for value in (
        preprocessed.language_expressions
    ):
        entities.append(
            PreservedEntity(
                entity_type="language",
                value=value,
                source="CURRENT_QUERY",
            )
        )

    for value in (
        preprocessed.edition_expressions
    ):
        entities.append(
            PreservedEntity(
                entity_type="edition",
                value=value,
                source="CURRENT_QUERY",
            )
        )

    for value in (
        preprocessed.expansion_expressions
    ):
        entities.append(
            PreservedEntity(
                entity_type="expansion",
                value=value,
                source="CURRENT_QUERY",
            )
        )

    for value in _find_pattern_values(
        query,
        _QUANTITY_PATTERNS,
    ):
        entities.append(
            PreservedEntity(
                entity_type="quantity",
                value=value,
                source="CURRENT_QUERY",
            )
        )

    for value in _find_pattern_values(
        query,
        _NEGATION_PATTERNS,
    ):
        entities.append(
            PreservedEntity(
                entity_type="negation",
                value=value,
                source="CURRENT_QUERY",
            )
        )

    for value in _find_pattern_values(
        query,
        _TIME_PATTERNS,
    ):
        entities.append(
            PreservedEntity(
                entity_type="time_condition",
                value=value,
                source="CURRENT_QUERY",
            )
        )

    return _unique_entities(
        entities
    )


def _select_previous_product(
    previous: QueryPreprocessResult,
) -> str | None:
    candidates = [
        value
        for value
        in previous.product_name_candidates
        if not _is_referential_text(
            value
        )
    ]

    if not candidates:
        return None

    # Day 9 preprocessing의 표면형을 그대로 사용한다.
    return candidates[0]


def _append_previous_qualifiers(
    rewritten: str,
    previous: QueryPreprocessResult,
    entities: list[PreservedEntity],
    changed_fields: list[ChangedField],
) -> str:
    qualifier_groups = (
        (
            "edition",
            previous.edition_expressions,
        ),
        (
            "language",
            _remove_contained_values(
                previous.language_expressions
            ),
        ),
        (
            "expansion",
            previous.expansion_expressions,
        ),
    )

    values_to_append: list[str] = []

    for (
        entity_type,
        values,
    ) in qualifier_groups:
        for value in values:
            if (
                value.casefold()
                in rewritten.casefold()
            ):
                continue

            values_to_append.append(
                value
            )

            entities.append(
                PreservedEntity(
                    entity_type=entity_type,
                    value=value,
                    source="PREVIOUS_QUERY",
                )
            )

    if not values_to_append:
        return rewritten

    before = rewritten

    # 상품 identity qualifier를 검색문 앞부분에
    # 보존한다. 값을 새 표현으로 치환하지 않는다.
    prefix = " ".join(
        values_to_append
    )

    rewritten = (
        f"{prefix} {rewritten}"
    ).strip()

    changed_fields.append(
        ChangedField(
            field="context_qualifiers",
            before=before,
            after=rewritten,
            reason=(
                "PREVIOUS_PRODUCT_IDENTITY_"
                "QUALIFIER_PRESERVED"
            ),
        )
    )

    return rewritten


def rewrite_query(
    query: str,
    *,
    previous_query: str | None = None,
    product_name_lexicon: Iterable[
        str
    ]
    | None = None,
    brand_lexicon: Iterable[
        str
    ]
    | None = None,
) -> QueryRewriteResult:
    """
    D10-AI-01 상품명 보존형 query rewrite.

    원칙:
    - 현재 query의 상품명/수량/판본/언어/
      expansion/부정어/시간 조건을 삭제하거나
      다른 표현으로 바꾸지 않는다.
    - 대명사·지시어가 있을 때만 이전 query의
      검증 가능한 상품 표현을 가져온다.
    - 임의 alias 확장, brand/language 추정,
      상품명 교정은 수행하지 않는다.
    - 이전 문맥이 불충분하면 rewrite하지 않고
      원문을 유지한다.
    """

    current = preprocess_query(
        query,
        product_name_lexicon=(
            product_name_lexicon
        ),
        brand_lexicon=brand_lexicon,
    )

    original = (
        current.normalized_query
    )

    entities = list(
        _collect_current_entities(
            original,
            current,
        )
    )

    changed_fields: list[
        ChangedField
    ] = []

    warnings: list[str] = list(
        current.warnings
    )

    referential_match = (
        _REFERENTIAL_PATTERN.search(
            original
        )
    )

    if referential_match is None:
        return QueryRewriteResult(
            original_query=query,
            rewritten_query=original,
            preserved_entities=(
                _unique_entities(
                    entities
                )
            ),
            changed_fields=(),
            reason="NO_REWRITE_NEEDED",
            warnings=tuple(warnings),
        )

    if previous_query is None:
        warnings.append(
            "REFERENTIAL_CONTEXT_MISSING"
        )

        return QueryRewriteResult(
            original_query=query,
            rewritten_query=original,
            preserved_entities=(
                _unique_entities(
                    entities
                )
            ),
            changed_fields=(),
            reason=(
                "REFERENTIAL_QUERY_"
                "LEFT_UNCHANGED"
            ),
            warnings=tuple(warnings),
        )

    previous = preprocess_query(
        previous_query,
        product_name_lexicon=(
            product_name_lexicon
        ),
        brand_lexicon=brand_lexicon,
    )

    previous_product = (
        _select_previous_product(
            previous
        )
    )

    if previous_product is None:
        warnings.append(
            "PREVIOUS_PRODUCT_NOT_RESOLVED"
        )

        return QueryRewriteResult(
            original_query=query,
            rewritten_query=original,
            preserved_entities=(
                _unique_entities(
                    entities
                )
            ),
            changed_fields=(),
            reason=(
                "REFERENTIAL_QUERY_"
                "LEFT_UNCHANGED"
            ),
            warnings=tuple(warnings),
        )

    referential_surface = (
        referential_match.group(0)
    )

    rewritten = (
        original[
            :referential_match.start()
        ]
        + previous_product
        + original[
            referential_match.end():
        ]
    )

    entities.append(
        PreservedEntity(
            entity_type="product_name",
            value=previous_product,
            source="PREVIOUS_QUERY",
        )
    )

    changed_fields.append(
        ChangedField(
            field=(
                "referential_expression"
            ),
            before=referential_surface,
            after=previous_product,
            reason=(
                "RESOLVED_FROM_"
                "PREVIOUS_QUERY"
            ),
        )
    )

    rewritten = (
        _append_previous_qualifiers(
            rewritten,
            previous,
            entities,
            changed_fields,
        )
    )

    return QueryRewriteResult(
        original_query=query,
        rewritten_query=rewritten,
        preserved_entities=(
            _unique_entities(
                entities
            )
        ),
        changed_fields=tuple(
            changed_fields
        ),
        reason=(
            "REFERENTIAL_PRODUCT_RESOLVED"
        ),
        warnings=tuple(
            dict.fromkeys(
                warnings
            )
        ),
    )


def entity_preservation_failures(
    result: QueryRewriteResult,
) -> tuple[PreservedEntity, ...]:
    """
    현재 query에서 보존 대상으로 추출된 entity가
    rewritten query에서 사라졌는지 검사한다.

    이전 query에서 추가된 entity 역시 최종 검색문에
    존재해야 한다.
    """

    rewritten = (
        result.rewritten_query.casefold()
    )

    failures = [
        entity
        for entity
        in result.preserved_entities
        if entity.value.casefold()
        not in rewritten
    ]

    return tuple(failures)


def entity_preservation_rate(
    result: QueryRewriteResult,
) -> float:
    total = len(
        result.preserved_entities
    )

    if total == 0:
        return 1.0

    failures = (
        entity_preservation_failures(
            result
        )
    )

    return (
        total - len(failures)
    ) / total

def _remove_contained_values(
    values: Iterable[str],
) -> tuple[str, ...]:
    ordered = sorted(
        {
            value.strip()
            for value in values
            if value.strip()
        },
        key=len,
        reverse=True,
    )

    selected: list[str] = []

    for value in ordered:
        if any(
            value.casefold()
            in existing.casefold()
            for existing in selected
        ):
            continue

        selected.append(value)

    # 원래 입력 순서와 비슷하게 안정적으로 유지
    return tuple(
        value
        for value in values
        if value in selected
    )