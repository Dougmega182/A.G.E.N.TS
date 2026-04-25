import json
from pathlib import Path

from agents.execution_dispatch import enqueue_execution


STORE_PATH = Path("Agent logs/preflight_approvals.json")


def main():
    if not STORE_PATH.exists():
        print("preflight_approvals.json not found")
        return

    data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    requests = data.get("requests", [])
    candidates = [
        req for req in requests
        if str(req.get("status", "")).lower() == "approved"
        and not req.get("execution_status")
    ]

    print(f"Found {len(candidates)} approved request(s) without execution_status.")
    for req in candidates:
        request_id = req.get("request_id")
        trace_id = req.get("trace_id")
        result = enqueue_execution(request_id=request_id, source="backfill")
        print(f"{request_id} | {trace_id} | {result.get('status')}")


if __name__ == "__main__":
    main()
