from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import create_app


def main() -> None:
    app = create_app()

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

        # 2) Product 검색으로 Conversation 생성
        search_response = client.post(
            "/api/v1/conversations/product-search",
            json={
                "query": "투명 주사위 찾아줘",
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

        # 마지막 USER message의 context를 그대로 사용
        user_message = next(
            item
            for item in reversed(messages)
            if item["role"] == "USER"
        )


        context = user_message["context"]

        analysis_context = {
            "scope": "ENTITY",
            "targetType": context["target_type"],
            "targetId": context["target_id"],
            "targetLabel": context["target_label"],
            "source": context["source"],
            "asOf": context["source_as_of"],
        }

        analysis_response = client.post(
            (
                f"/api/v1/conversations/"
                f"{conversation_id}/messages"
            ),
            json={
                "context": analysis_context,
                "intent": "INSPECT_TARGET",
                "analysis_kind": "HYBRID",
                "request_revision": context["context_revision"],
            },
        )

        print(
            "ANALYSIS_STATUS=",
            analysis_response.status_code,
        )

        if analysis_response.status_code != 200:
            print(analysis_response.text)
            return

        body = analysis_response.json()
        result = body["data"]

        print(
            "CONVERSATION_STATUS=",
            result["conversation_status"],
        )

        print("MESSAGES=")

        for message in result["messages"][-3:]:
            print(
                message["role"],
                message.get("response_status"),
                message["content"],
            )


if __name__ == "__main__":
    main()