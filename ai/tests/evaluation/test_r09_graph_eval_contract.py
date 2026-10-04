from ai.evaluation.r09_graph_eval_contract import (
    EXPECTED_STATUS_COUNTS,
    R09_EMBEDDING_CONFIG,
    GraphEvalPrediction,
    R09GraphMethod,
    load_gold_cases,
    score_prediction,
    validate_gold_contract,
)


def _cases_by_id():
    return {
        case["case_id"]: case
        for case in load_gold_cases()
    }


def test_r08_gold_contract_is_fixed_3_2_1():
    cases = load_gold_cases()

    assert len(cases) == 6
    assert validate_gold_contract(cases) == EXPECTED_STATUS_COUNTS


def test_embedding_config_reuses_r07_pre_fixed_values():
    assert (
        R09_EMBEDDING_CONFIG.model
        == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    assert (
        R09_EMBEDDING_CONFIG.revision
        == "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
    )
    assert R09_EMBEDDING_CONFIG.dimension == 384
    assert R09_EMBEDDING_CONFIG.normalized is True


def test_answer_case_requires_exact_path_and_relations():
    case = _cases_by_id()["R08-G-01"]

    prediction = GraphEvalPrediction(
        case_id="R08-G-01",
        method=R09GraphMethod.DETERMINISTIC,
        predicted_status="ANSWER",
        predicted_nodes=(
            "INCOMING_STOCK:incoming-demo-001",
            "TASK:task-inspection",
            "TASK:task-product-page",
        ),
        predicted_relations=(
            "IMPACTS",
            "PRECEDES",
        ),
    )

    score = score_prediction(case, prediction)

    assert score.passed is True
    assert score.path_match is True
    assert score.relation_match is True
    assert score.false_edge_count == 0


def test_cross_incoming_edge_is_rejected():
    case = _cases_by_id()["R08-G-05"]

    prediction = GraphEvalPrediction(
        case_id="R08-G-05",
        method=R09GraphMethod.RELATION_DOCUMENT,
        predicted_status="NO_EDGE",
        predicted_nodes=(
            "TASK:task-other-incoming",
        ),
        predicted_relations=(
            "IMPACTS",
        ),
    )

    score = score_prediction(case, prediction)

    assert score.passed is False
    assert score.false_edge_count > 0


def test_no_edge_without_fabrication_passes():
    case = _cases_by_id()["R08-G-04"]

    prediction = GraphEvalPrediction(
        case_id="R08-G-04",
        method=R09GraphMethod.DETERMINISTIC,
        predicted_status="NO_EDGE",
    )

    score = score_prediction(case, prediction)

    assert score.passed is True
    assert score.false_edge_count == 0


def test_hold_without_fabrication_passes():
    case = _cases_by_id()["R08-G-06"]

    prediction = GraphEvalPrediction(
        case_id="R08-G-06",
        method=R09GraphMethod.HYBRID,
        predicted_status="HOLD",
    )

    score = score_prediction(case, prediction)

    assert score.passed is True
    assert score.hold_correct is True
    assert score.false_edge_count == 0


def test_hold_with_fabricated_relation_fails():
    case = _cases_by_id()["R08-G-06"]

    prediction = GraphEvalPrediction(
        case_id="R08-G-06",
        method=R09GraphMethod.HYBRID,
        predicted_status="HOLD",
        predicted_nodes=(
            "TASK:fabricated-task",
        ),
        predicted_relations=(
            "IMPACTS",
        ),
    )

    score = score_prediction(case, prediction)

    assert score.passed is False
    assert score.false_edge_count == 2

def test_r09_score_preserves_evidence_and_provenance_metadata():
    case = {
        "case_id": "R08-G-01",
        "question": "test",
        "start_node": "INCOMING_STOCK:incoming-demo-001",
        "intermediate_nodes": ["TASK:task-inspection"],
        "end_nodes": ["TASK:task-product-page"],
        "required_relations": ["IMPACTS", "PRECEDES"],
        "expected": "test",
        "expected_status": "ANSWER",
        "query_sha256": "test",
        "gold_sha256": "test",
    }

    prediction = GraphEvalPrediction(
        case_id="R08-G-01",
        method=R09GraphMethod.RELATION_DOCUMENT,
        predicted_status="ANSWER",
        predicted_nodes=(
            "INCOMING_STOCK:incoming-demo-001",
            "TASK:task-inspection",
            "TASK:task-product-page",
        ),
        predicted_relations=(
            "IMPACTS",
            "PRECEDES",
        ),
        evidence_available=True,
        provenance_available=True,
        source_available=True,
        valid_time_available=False,
    )

    score = score_prediction(case, prediction)

    assert score.passed is True
    assert score.evidence_available is True
    assert score.provenance_available is True
    assert score.source_available is True
    assert score.valid_time_available is False
    assert score.failure_reason is None