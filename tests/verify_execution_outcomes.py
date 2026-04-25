from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.execution_dispatch import _derive_outcome_from_result


def main() -> int:
    failed_only = {
        "status": "success",
        "result": [
            {"type": "audit_log", "status": "failed"},
        ],
    }
    assert _derive_outcome_from_result(failed_only) == "failure"

    partial_bundle = {
        "status": "success",
        "result": [
            {"type": "gmail_draft", "status": "success"},
            {"type": "calendar_event", "status": "failed"},
        ],
    }
    assert _derive_outcome_from_result(partial_bundle) == "partial"

    clean_success = {
        "status": "success",
        "result": [
            {"type": "gmail_draft", "status": "success"},
        ],
    }
    assert _derive_outcome_from_result(clean_success) == "success"

    assert _derive_outcome_from_result({"status": "dry_run"}) == "success"
    assert _derive_outcome_from_result(None, error="boom") == "failure"

    print("Execution outcome verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
