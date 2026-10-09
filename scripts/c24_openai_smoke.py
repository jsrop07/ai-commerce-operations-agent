from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import Settings
from backend.app.services.c24_grounded_operations import (
    run_product_grounded_explanation,
)


def main() -> None:
    settings = Settings()

    factory = sessionmaker(
        bind=create_engine(settings.postgres_v2_url),
        expire_on_commit=False,
    )

    result = run_product_grounded_explanation(
        factory=factory,
        settings=settings,
        tenant_id=UUID(
            "35556e27-4200-4712-8ac5-e5a569a91c47"
        ),
        demo_session_id=UUID(
            "5c852edb-4f44-483d-8c95-1181759506d9"
        ),
        request_id=(
            "c24-openai-smoke-"
            + uuid4().hex[:12]
        ),
        question=(
            "이 상품이 어떤 상품인지 "
            "확인된 근거만 사용해서 설명해줘."
        ),
        data_mode="SYNTHETIC_DEMO",
        evidence_id=(
            "rag:PRODUCT:"
            "e87b23a3-a2f5-517e-9a7e-c7fc45bd7e23"
        ),
        evidence_version=(
            "demo-c15-20261006-v1"
        ),
        evidence_excerpt=(
            "상품명: 투명 주사위 세트\n"
            "상품 코드: DEMO-P-0120\n"
            "범위: 상품 master 정보"
        ),
    )

    print(
        "STATUS=",
        result.output.status.value,
    )
    print(
        "CONCLUSION=",
        result.output.conclusion,
    )
    print(
        "FACTS=",
        result.output.used_facts,
    )
    print(
        "CITATIONS=",
        [
            (item.source_id, item.version)
            for item in result.output.citations
        ],
    )

    receipt = result.receipt

    print("MODEL=", receipt.model)
    print("RESPONSE_ID=", receipt.response_id)
    print("ATTEMPTS=", receipt.attempts)
    print("RETRIES=", receipt.retries)
    print(
        "INPUT_TOKENS=",
        receipt.usage.input_tokens,
    )
    print(
        "CACHED_INPUT_TOKENS=",
        receipt.usage.cached_input_tokens,
    )
    print(
        "OUTPUT_TOKENS=",
        receipt.usage.output_tokens,
    )
    print(
        "LATENCY_MS=",
        receipt.latency_ms,
    )


if __name__ == "__main__":
    main()