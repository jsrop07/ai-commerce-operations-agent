from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import app

def main() -> None:
    with TestClient(
        app,
        base_url="https://testserver",
    ) as client:
        # 1) Demo Session 생성
        session_response = client.post(
            "/api/v1/demo/session"
        )

        print(
            "DEMO_SESSION_STATUS=",
            session_response.status_code,
        )

        if session_response.status_code not in {
            200,
            201,
        }:
            print(session_response.text)
            return
        # 2) Synthetic reservation projection 준비
        prepare_response = client.post(
            "/api/v1/demo/reservations/prepare"
        )

        print(
            "RESERVATION_PREPARE_STATUS=",
            prepare_response.status_code,
        )

        if prepare_response.status_code != 200:
            print(prepare_response.text)
            return

        print(
            "RESERVATION_PREPARE_BODY=",
            prepare_response.json(),
        )
        print("RESERVATION_PROJECTIONS=")

        for projection in (
            app.state.reservation_risk_projections
        ):
            print(
                "tenant_id=",
                projection.tenant_id,
                "reservation_id=",
                projection.reservation_id,
                "sku_id=",
                projection.sku_id,
                "required=",
                projection.required_qty,
                "secured=",
                projection.secured_qty,
                "confirmed=",
                projection.confirmed_incoming_qty,
                "shortage=",
                projection.shortage,
            )
        # 2) Hero Product 검색
        search_response = client.post(
            "/api/v1/conversations/product-search",
            json={
                "query": "DEMO-P-0009"
            },
        )

        print(
            "PRODUCT_SEARCH_STATUS=",
            search_response.status_code,
        )

        if search_response.status_code != 201:
            print(search_response.text)
            return

        search_body = search_response.json()
        conversation = search_body["data"]

        conversation_id = conversation[
            "conversation_id"
        ]

        print(
            "CONVERSATION_ID=",
            conversation_id,
        )

        messages = conversation["messages"]

        # 마지막 USER message의 context 사용
        user_message = next(
            item
            for item in reversed(messages)
            if item["role"] == "USER"
        )

        context = user_message["context"]

        analysis_context = {
            "scope": "ENTITY",
            "targetType": context[
                "target_type"
            ],
            "targetId": context[
                "target_id"
            ],
            "targetLabel": context[
                "target_label"
            ],
            "source": context[
                "source"
            ],
            "asOf": context[
                "source_as_of"
            ],
        }

        # 3) 실제 HYBRID 분석
        analysis_response = client.post(
            (
                f"/api/v1/conversations/"
                f"{conversation_id}/messages"
            ),
            json={
                "context": analysis_context,
                "intent": "INSPECT_TARGET",
                "analysis_kind": "HYBRID",
                "request_revision": context[
                    "context_revision"
                ],
            },
        )

        print(
            "ANALYSIS_STATUS=",
            analysis_response.status_code,
        )

        if analysis_response.status_code != 200:
            print(analysis_response.text)
            return

        analysis_body = (
            analysis_response.json()
        )

        result = analysis_body["data"]

        print(
            "CONVERSATION_STATUS=",
            result["conversation_status"],
        )

        print("MESSAGES=")

        for message in result["messages"][-3:]:
            print(
                message["role"],
                message.get(
                    "response_status"
                ),
                message["content"],
            )


if __name__ == "__main__":
    main()