"""C06 policy explanation boundary over verified C05 retrieval evidence."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import asdict

from openai import OpenAI

from ai.retrieval.claim_support import (
    ClaimEvidence,
    ClaimType,
    evaluate_claim_support,
)
from ai.retrieval.source_suitability import SourceEvidence, evaluate_source_suitability
from ai.services.grounded_explanation import (
    ExplanationEvidence,
    build_policy_grounded_explanation_input,
)
from ai.services.grounded_explanation_output import GroundedExplanationOutput
from ai.services.grounded_explanation_provider import (
    GroundedProviderResult,
    run_grounded_explanation,
)
from ai.services.grounded_explanation_validator import validate_grounded_explanation
from backend.app.core.config import Settings
from backend.app.services.retrieval_runtime import validate_query

LOGGER = logging.getLogger(__name__)
FORBIDDEN_KEYS = frozenset({
    "order_id", "order_item_id", "order_line_id", "reservation_id",
    "affected_order_ids", "customer_id", "customer", "customer_group",
    "shipping", "payment", "inquiry", "inquiry_body", "inquiry_text",
    "free_memo", "orders", "reservations", "source_order_url",
})


def forbidden_structure(value: object) -> bool:
    if isinstance(value, dict):
        return any(str(k).lower() in FORBIDDEN_KEYS or forbidden_structure(v)
                   for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(forbidden_structure(v) for v in value)
    return False


def hold(reason: str, data_mode: str, request_id: str, *, lookup=(), model_used=False):
    return dict(status="HOLD", conclusion="근거를 확인할 수 없어 설명을 보류합니다.",
                used_facts=[], used_numeric_facts=[], citations=[], next_check=None,
                model_used=model_used, data_mode=data_mode, request_id=request_id,
                warnings=[reason], c04_lookup=list(lookup))


def explain_policy(*, question: str, condition: str, projection: dict,
                   lookup_service, tenant_id: str, request_id: str,
                   provider: Callable | None = None,
                   settings: Settings | None = None) -> dict:
    data_mode = projection.get("data_mode", "SYNTHETIC_DEMO")
    try:
        validate_query(question)
    except Exception:
        return hold("FORBIDDEN_INPUT", data_mode, request_id)
    if forbidden_structure(projection):
        return hold("FORBIDDEN_INPUT", data_mode, request_id)
    if data_mode != "SYNTHETIC_DEMO":
        return hold("RUNTIME_UNAVAILABLE", data_mode, request_id)
    citations = projection.get("citations", [])
    try:
        claim_evidence = tuple(
            ClaimEvidence(
                source_type=str(item["source_type"]), source_id=item["source_id"],
                version=item["version"], excerpt=item["semantic_excerpt"],
            )
            for item in citations
        )
        decision = evaluate_claim_support(question, claim_evidence)
    except (KeyError, TypeError, ValueError):
        return hold("CLAIM_SUPPORT_UNVERIFIED", data_mode, request_id)
    if not citations:
        suitability = evaluate_source_suitability(
            required_source_types=(), evidence=(),
        )
        return hold(suitability.reasons[0], data_mode, request_id)
    if not decision.supported:
        reason = ("UNSUPPORTED_CLAIM" if decision.claim_type == ClaimType.UNSUPPORTED
                  else "CLAIM_SUPPORT_INSUFFICIENT:" + ",".join(decision.missing_requirements))
        return hold(reason, data_mode, request_id)
    selected = [item for item in citations
                if item["source_id"] in decision.supported_source_ids]
    required_types = (("POLICY", "INCOMING_STOCK")
                      if decision.claim_type == ClaimType.TENTATIVE_SHIPPING_READINESS
                      else ("POLICY",))
    source_evidence, evidence, lookups = [], [], []
    mapping_ambiguous = False
    target_verified = True
    source_conflict = False
    seen = {}
    for citation in selected:
        try:
            source_id, version = citation["source_id"], citation["version"]
            previous = seen.setdefault(source_id, version)
            source_conflict |= previous != version
            exact = lookup_service.lookup(tenant_id=tenant_id, source_id=source_id, version=version)
            if exact.data_mode != data_mode or exact.visibility != "DEMO_PUBLIC":
                target_verified = False
            if str(exact.source_type) != str(citation["source_type"]):
                target_verified = False
            key = citation.get("c04_lookup")
            if (citation.get("mapping_status") != "MAPPED" or not key
                    or key.get("source_id") != source_id
                    or key.get("version") != version
                    or key.get("chunk_id") != exact.chunk_id):
                mapping_ambiguous = True
            else:
                lookups.append(key)
            source_evidence.append(SourceEvidence(
                source_type=str(citation["source_type"]), source_id=source_id,
                freshness="STALE" if exact.stale else "FRESH",
                supports_claim=source_id in decision.supported_source_ids,
            ))
            evidence.append(ExplanationEvidence(
                source_type=str(citation["source_type"]), source_id=source_id,
                version=version, excerpt=citation["semantic_excerpt"],
                as_of=exact.as_of.isoformat() if exact.as_of else None,
            ))
        except Exception:
            target_verified = False
    suitability = evaluate_source_suitability(
        required_source_types=required_types, evidence=tuple(source_evidence),
        mapping_ambiguous=mapping_ambiguous, source_conflict=source_conflict,
        target_verified=target_verified,
    )
    if not suitability.provider_call_allowed:
        return hold(suitability.reasons[0], data_mode, request_id)
    if provider is None:
        credential = settings.openai_api_key if settings is not None else None
        if credential is None or not credential.get_secret_value():
            LOGGER.info("C06 OpenAI credential configured=false")
            return hold("RUNTIME_UNAVAILABLE", data_mode, request_id)
    provider_attempted = False
    try:
        model_input = build_policy_grounded_explanation_input(
            question=question, data_mode=data_mode, evidence=tuple(evidence),
        )
        if provider is None:
            runtime_client = OpenAI(
                api_key=credential.get_secret_value(), max_retries=0,
            )
            provider_attempted = True
            runtime_result = run_grounded_explanation(
                model_input, condition=condition, client=runtime_client,
            )
        else:
            provider_attempted = True
            runtime_result = provider(model_input, condition=condition)
        if not isinstance(runtime_result, GroundedProviderResult) or not runtime_result.model_used:
            raise ValueError("MALFORMED_PROVIDER_RESULT")
        output = runtime_result.output
        receipt = runtime_result.receipt
        LOGGER.info(
            "C06 provider receipt request_id=%s response_id=%s latency_ms=%s "
            "attempts=%s retries=%s input_tokens=%s cached_input_tokens=%s output_tokens=%s",
            request_id, receipt.response_id, receipt.latency_ms, receipt.attempts,
            receipt.retries, receipt.usage.input_tokens,
            receipt.usage.cached_input_tokens, receipt.usage.output_tokens,
        )
        if not isinstance(output, GroundedExplanationOutput):
            raise ValueError("MALFORMED_SCHEMA")
        result = validate_grounded_explanation(
            model_input=model_input, model_output=output, condition=condition,
        )
        if not result.valid:
            return hold("MODEL_VALIDATION_FAILED", data_mode, request_id, model_used=True)
        if output.status.value != "ANSWER":
            return hold("MODEL_HOLD", data_mode, request_id, model_used=True)
        return dict(status="ANSWER", conclusion=output.conclusion,
                    used_facts=list(output.used_facts),
                    used_numeric_facts=[asdict(x) for x in output.used_numeric_facts],
                    citations=[asdict(x) for x in output.citations],
                    next_check=output.next_check, model_used=True,
                    data_mode=data_mode, request_id=request_id, warnings=[],
                    c04_lookup=lookups)
    except Exception:
        return hold("C06_RUNTIME_OR_PROVIDER_FAILURE", data_mode, request_id,
                    model_used=provider_attempted)
