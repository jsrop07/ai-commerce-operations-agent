from ai.evaluation.run_prompt_eval import (
    build_metrics,
    calculate_entity_f1,
    calculate_intent_scores,
    calculate_latency,
)


def sample_records():
    return [
        {
            "id": "sample_001",
            "expected": {
                "intent": "RESTOCK",
                "entities": [
                    {
                        "type": "PRODUCT",
                        "value": "별빛 탐험대",
                    }
                ],
                "risk": "LOW",
                "route": "SLLM",
            },
            "prediction": {
                "intent": "RESTOCK",
                "entities": [
                    {
                        "type": "PRODUCT",
                        "value": "별빛 탐험대",
                    }
                ],
                "risk": "LOW",
                "route": "SLLM",
            },
            "json_valid": True,
            "latency_ms": 100.0,
            "token": {
                "input": 100,
                "output": 30,
            },
            "cost": 0.001,
        },
        {
            "id": "sample_002",
            "expected": {
                "intent": "REFUND_CANCEL",
                "entities": [],
                "risk": "PROHIBITED",
                "route": "HUMAN_REVIEW",
            },
            "prediction": {
                "intent": "REFUND_CANCEL",
                "entities": [],
                "risk": "PROHIBITED",
                "route": "HUMAN_REVIEW",
            },
            "json_valid": True,
            "latency_ms": 200.0,
            "token": {
                "input": 110,
                "output": 35,
            },
            "cost": 0.002,
        },
    ]


def test_perfect_intent_scores():
    scores = calculate_intent_scores(
        [
            "RESTOCK",
            "REFUND_CANCEL",
        ],
        [
            "RESTOCK",
            "REFUND_CANCEL",
        ],
    )

    assert scores["macro_f1"] == 1.0
    assert scores["micro_f1"] == 1.0


def test_entity_f1_perfect_match():
    score = calculate_entity_f1(
        [
            [
                {
                    "type": "PRODUCT",
                    "value": "별빛 탐험대",
                }
            ]
        ],
        [
            [
                {
                    "type": "PRODUCT",
                    "value": "별빛 탐험대",
                }
            ]
        ],
    )

    assert score == 1.0


def test_latency_percentiles():
    result = calculate_latency(
        [
            100.0,
            200.0,
        ]
    )

    assert result["p50_ms"] == 150.0
    assert result["p95_ms"] == 195.0


def test_build_metrics_perfect_fixture():
    metrics = build_metrics(
        sample_records()
    )

    assert (
        metrics["intent"]["macro_f1"]
        == 1.0
    )

    assert (
        metrics["intent"]["micro_f1"]
        == 1.0
    )

    assert metrics["entity_f1"] == 1.0
    assert metrics["json_valid_rate"] == 1.0

    assert (
        metrics[
            "high_risk_routing"
        ]["rate"]
        == 1.0
    )


def test_token_totals():
    metrics = build_metrics(
        sample_records()
    )

    assert metrics["token"] == {
        "input": 210,
        "output": 65,
    }


def test_cost_total():
    metrics = build_metrics(
        sample_records()
    )

    assert (
        metrics["cost"]["total"]
        == 0.003
    )


def test_error_count_is_zero_for_perfect_fixture():
    metrics = build_metrics(
        sample_records()
    )

    assert metrics["error_count"] == 0