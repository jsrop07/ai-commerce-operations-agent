from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.core.config import Settings
from backend.app.services.c24_grounded_operations import (
    run_reservation_grounded_explanation,
)
from backend.app.services.reservation_projection import (
    build_reservation_risk_projection,
)
from backend.app.services.reservation_shortage import (
    IncomingConfirmation,
    IncomingEvidence,
    IncomingFreshness,
    calculate_reservation_shortage,
)
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models_v2.ai import DemoSessionV2

TENANT_ID = UUID(
    "35556e27-4200-4712-8ac5-e5a569a91c47"
)


def main() -> None:
    settings = Settings()
    engine = create_engine(
        settings.postgres_v2_url
    )

    with Session(engine) as db:
        demo_session = db.scalars(
            select(DemoSessionV2)
            .where(
                DemoSessionV2.tenant_id == TENANT_ID,
                DemoSessionV2.status == "ACTIVE",
            )
            .order_by(
                DemoSessionV2.created_at.desc()
            )
        ).first()

    if demo_session is None:
        raise RuntimeError(
            "ACTIVE_DEMO_SESSION_NOT_FOUND"
        )

    demo_session_id = demo_session.id

    print(
        "DEMO_SESSION_ID=",
        demo_session_id,
    )
    now = datetime.now(UTC)

    # Backend authoritative calculation.
    shortage = calculate_reservation_shortage(
        required_qty=5,
        secured_qty=1,
        incoming=(
            IncomingEvidence(
                evidence_id="demo-incoming-confirmed-01",
                quantity=2,
                confirmation_status=(
                    IncomingConfirmation.CONFIRMED
                ),
                quality_status="CONFIRMED",
                freshness=IncomingFreshness.FRESH,
                source_classification="SYNTHETIC_DEMO",
                as_of=now,
            ),
        ),
        as_of=now,
    )

    projection = build_reservation_risk_projection(
        reservation_id="DEMO-RES-HERO",
        tenant_id=str(TENANT_ID),
        sku_id="DEMO-SKU-HERO",
        required_qty=shortage.required_qty,
        secured_qty=shortage.secured_qty,
        confirmed_incoming_qty=(
            shortage.confirmed_incoming_qty
        ),
        tentative_incoming_qty=(
            shortage.tentative_incoming_qty
        ),
        shortage=shortage.shortage,
        affected_order_ids=(),
        aging_hours=24,
        priority=2,
        priority_reason="DEMO",
        calculation_status=(
            shortage.calculation_status
        ),
        evidence=shortage.evidence_ids,
        source_classification="SYNTHETIC_DEMO",
        quality_status="CONFIRMED",
        as_of=now,
        data_mode="SYNTHETIC_DEMO",
    )

    print("BACKEND_REQUIRED=", projection.required_qty)
    print("BACKEND_SECURED=", projection.secured_qty)
    print(
        "BACKEND_CONFIRMED_INCOMING=",
        projection.confirmed_incoming_qty,
    )
    print("BACKEND_SHORTAGE=", projection.shortage)
    print(
        "BACKEND_CALCULATION_STATUS=",
        projection.calculation_status,
    )

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    result = run_reservation_grounded_explanation(
        factory=factory,
        settings=settings,
        tenant_id=TENANT_ID,
        demo_session_id=demo_session_id,
        request_id=(
            "c24-reservation-smoke-"
            + uuid4().hex[:12]
        ),
        question=(
            "왜 이 예약 상품의 수량이 부족한지 "
            "확인된 수치만 사용해서 설명해줘."
        ),
        projection=projection,
    )

    print("STATUS=", result.output.status.value)
    print(
        "CONCLUSION=",
        result.output.conclusion,
    )

    print("NUMERIC_FACTS=")
    for fact in result.output.used_numeric_facts:
        print(
            fact.field,
            fact.value,
            fact.unit,
        )

    print(
        "CITATIONS=",
        [
            (item.source_id, item.version)
            for item in result.output.citations
        ],
    )

    print("MODEL=", result.receipt.model)
    print(
        "INPUT_TOKENS=",
        result.receipt.usage.input_tokens,
    )
    print(
        "OUTPUT_TOKENS=",
        result.receipt.usage.output_tokens,
    )
    print(
        "LATENCY_MS=",
        result.receipt.latency_ms,
    )


if __name__ == "__main__":
    main()