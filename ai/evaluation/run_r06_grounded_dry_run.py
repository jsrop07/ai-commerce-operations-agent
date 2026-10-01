import json
from pathlib import Path

PLAN = Path("artifacts/experiments/OPS-RAG-01/r06_eval_plan.json")
OUT = Path("artifacts/experiments/OPS-RAG-01/r06_dry_run_result.json")

def main() -> int:
    plan = json.load(PLAN.open(encoding="utf-8"))
    records = []
    provider_calls = 0
    for case in plan["evaluation_cases"]:
        allowed = bool(case["provider_call_allowed"])
        records.append({"evaluation_id":case["evaluation_id"],"case_id":case["case_id"],"condition":case["condition"],"status":"READY_FOR_PROVIDER" if allowed else "PREBLOCKED","provider_called":False})
    result = {"schema_version":"r06-dry-run-result.v0.1","execution_mode":"DRY_RUN","records":records,"counts":{"total":len(records),"ready_for_provider":sum(r["status"]=="READY_FOR_PROVIDER" for r in records),"preblocked":sum(r["status"]=="PREBLOCKED" for r in records),"actual_provider_calls":provider_calls}}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("R06_DRY_RUN_OK")
    print("TOTAL=",result["counts"]["total"])
    print("READY_FOR_PROVIDER=",result["counts"]["ready_for_provider"])
    print("PREBLOCKED=",result["counts"]["preblocked"])
    print("ACTUAL_PROVIDER_CALLS=",result["counts"]["actual_provider_calls"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
