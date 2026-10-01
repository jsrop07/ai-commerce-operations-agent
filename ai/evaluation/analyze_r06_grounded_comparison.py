import json
from pathlib import Path
from statistics import mean


PATH = Path(
    "artifacts/experiments/OPS-RAG-01/"
    "r06_grounded_comparison_results.json"
)

OUTPUT = Path(
    "artifacts/experiments/OPS-RAG-01/"
    "r06_grounded_comparison_analysis.json"
)


data = json.loads(
    PATH.read_text(encoding="utf-8")
)

records = data["records"]

pairs = {}

for record in records:
    case_id = record["case_id"]
    pairs.setdefault(case_id, {})
    pairs[case_id][record["condition"]] = record


pair_results = []

for case_id, conditions in pairs.items():
    basic = conditions["BASIC"]
    citation = conditions["CITATION"]

    basic_citations = (
        basic["model_output"]["citations"]
    )
    citation_citations = (
        citation["model_output"]["citations"]
    )

    result = {
        "case_id": case_id,
        "category": basic["category"],
        "basic": {
            "valid":
                basic["validation"]["valid"],
            "citation_count":
                len(basic_citations),
            "input_tokens":
                basic["usage"]["input_tokens"],
            "output_tokens":
                basic["usage"]["output_tokens"],
            "latency_ms":
                basic["latency_ms"],
            "estimated_cost_usd":
                basic["estimated_cost_usd"],
            "status":
                basic["model_output"]["status"],
            "conclusion":
                basic["model_output"]["conclusion"],
        },
        "citation": {
            "valid":
                citation["validation"]["valid"],
            "citation_count":
                len(citation_citations),
            "input_tokens":
                citation["usage"]["input_tokens"],
            "output_tokens":
                citation["usage"]["output_tokens"],
            "latency_ms":
                citation["latency_ms"],
            "estimated_cost_usd":
                citation["estimated_cost_usd"],
            "status":
                citation["model_output"]["status"],
            "conclusion":
                citation["model_output"]["conclusion"],
        },
        "delta": {
            "input_tokens":
                citation["usage"]["input_tokens"]
                - basic["usage"]["input_tokens"],
            "output_tokens":
                citation["usage"]["output_tokens"]
                - basic["usage"]["output_tokens"],
            "latency_ms":
                round(
                    citation["latency_ms"]
                    - basic["latency_ms"],
                    2,
                ),
            "estimated_cost_usd":
                round(
                    citation["estimated_cost_usd"]
                    - basic["estimated_cost_usd"],
                    8,
                ),
        },
        "basic_added_citation_voluntarily":
            len(basic_citations) > 0,
        "citation_requirement_satisfied":
            len(citation_citations) > 0,
    }

    pair_results.append(result)


basic_records = [
    r for r in records
    if r["condition"] == "BASIC"
]

citation_records = [
    r for r in records
    if r["condition"] == "CITATION"
]


summary = {
    "schema_version":
        "r06-grounded-comparison-analysis.v0.1",
    "case_count":
        len(pair_results),
    "evaluation_count":
        len(records),
    "basic": {
        "validator_passed":
            sum(
                r["validation"]["valid"]
                for r in basic_records
            ),
        "avg_input_tokens":
            round(
                mean(
                    r["usage"]["input_tokens"]
                    for r in basic_records
                ),
                2,
            ),
        "avg_output_tokens":
            round(
                mean(
                    r["usage"]["output_tokens"]
                    for r in basic_records
                ),
                2,
            ),
        "avg_latency_ms":
            round(
                mean(
                    r["latency_ms"]
                    for r in basic_records
                ),
                2,
            ),
        "total_estimated_cost_usd":
            round(
                sum(
                    r["estimated_cost_usd"]
                    for r in basic_records
                ),
                8,
            ),
        "voluntary_citation_cases":
            sum(
                len(
                    r["model_output"]["citations"]
                ) > 0
                for r in basic_records
            ),
    },
    "citation": {
        "validator_passed":
            sum(
                r["validation"]["valid"]
                for r in citation_records
            ),
        "avg_input_tokens":
            round(
                mean(
                    r["usage"]["input_tokens"]
                    for r in citation_records
                ),
                2,
            ),
        "avg_output_tokens":
            round(
                mean(
                    r["usage"]["output_tokens"]
                    for r in citation_records
                ),
                2,
            ),
        "avg_latency_ms":
            round(
                mean(
                    r["latency_ms"]
                    for r in citation_records
                ),
                2,
            ),
        "total_estimated_cost_usd":
            round(
                sum(
                    r["estimated_cost_usd"]
                    for r in citation_records
                ),
                8,
            ),
        "citation_requirement_passed":
            sum(
                len(
                    r["model_output"]["citations"]
                ) > 0
                for r in citation_records
            ),
    },
    "pairs":
        pair_results,
}


OUTPUT.write_text(
    json.dumps(
        summary,
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)


print("R06_COMPARISON_ANALYSIS_OK")
print("CASES=", summary["case_count"])
print(
    "BASIC_VALID=",
    summary["basic"]["validator_passed"],
)
print(
    "CITATION_VALID=",
    summary["citation"]["validator_passed"],
)
print(
    "BASIC_AVG_LATENCY_MS=",
    summary["basic"]["avg_latency_ms"],
)
print(
    "CITATION_AVG_LATENCY_MS=",
    summary["citation"]["avg_latency_ms"],
)
print(
    "BASIC_COST_USD=",
    summary["basic"][
        "total_estimated_cost_usd"
    ],
)
print(
    "CITATION_COST_USD=",
    summary["citation"][
        "total_estimated_cost_usd"
    ],
)
print(
    "BASIC_VOLUNTARY_CITATIONS=",
    summary["basic"][
        "voluntary_citation_cases"
    ],
)
print(
    "CITATION_REQUIREMENT_PASSED=",
    summary["citation"][
        "citation_requirement_passed"
    ],
)
print("OUTPUT=", OUTPUT)