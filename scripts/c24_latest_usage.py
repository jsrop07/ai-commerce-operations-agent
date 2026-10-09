from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models_v2.ai import DemoProviderUsageV2


settings = Settings()

with Session(
    create_engine(settings.postgres_v2_url)
) as session:
    row = session.scalars(
        select(DemoProviderUsageV2)
        .order_by(
            DemoProviderUsageV2.created_at.desc()
        )
    ).first()

    if row is None:
        print("NO_USAGE")
    else:
        print("REQUEST=", row.request_id)
        print("STATUS=", row.status)
        print("MODEL=", row.model)
        print(
            "RESERVED=",
            row.reserved_input_tokens,
            row.reserved_output_tokens,
            row.reserved_cost_usd,
        )
        print(
            "ACTUAL=",
            row.actual_input_tokens,
            row.actual_output_tokens,
            row.actual_cost_usd,
        )
        print("SETTLED_AT=", row.settled_at)