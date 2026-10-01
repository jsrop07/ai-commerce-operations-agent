import json
from pathlib import Path

CONFIG = Path("artifacts/experiments/OPS-RAG-01/r06_run_config.json")

REQUIRED = ("provider","model","max_output_tokens","timeout_seconds","max_retries","budget_limit_usd")

def main() -> int:
    config = json.load(CONFIG.open(encoding="utf-8"))
    missing = [key for key in REQUIRED if config.get(key) is None]
    max_requests = config.get("planned_counts",{}).get("currently_runnable_provider_calls_without_retries")
    if max_requests is None or max_requests <= 0:
        missing.append("max_requests")
    if missing:
        print("R06_PROVIDER_CONFIG_BLOCKED")
        print("MISSING=",",".join(missing))
        print("ACTUAL_PROVIDER_CALLS=",config.get("actual_provider_calls",0))
        return 2
    print("R06_PROVIDER_CONFIG_READY")
    print("PROVIDER=",config["provider"])
    print("MODEL=",config["model"])
    print("MAX_REQUESTS=",max_requests)
    print("ACTUAL_PROVIDER_CALLS=",config.get("actual_provider_calls",0))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
