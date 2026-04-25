from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.logic.external_gateway import ExternalGateway


def main() -> int:
    gateway = ExternalGateway()

    assert gateway._normalize_operator_status({"status": "SUCCESS"}) == "success"
    assert gateway._normalize_operator_status({"status": "error", "error": "bad"}) == "failed"
    assert gateway._normalize_operator_status(
        {
            "status": "success",
            "result": {"status": "error", "error": "Invalid To header"},
        }
    ) == "failed"
    assert gateway._normalize_operator_status(
        {
            "status": "success",
            "result": {"status": "SUCCESS", "draft_id": "abc"},
        }
    ) == "success"

    bundle_statuses = ["failed"]
    overall = "partial" if any(s in {"failed", "partial"} for s in bundle_statuses) and any(s in {"success", "skipped"} for s in bundle_statuses) else ("failed" if any(s in {"failed", "partial"} for s in bundle_statuses) else "success")
    assert overall == "failed"

    bundle_statuses = ["failed", "skipped"]
    overall = "partial" if any(s in {"failed", "partial"} for s in bundle_statuses) and any(s in {"success", "skipped"} for s in bundle_statuses) else ("failed" if any(s in {"failed", "partial"} for s in bundle_statuses) else "success")
    assert overall == "partial"

    bundle_statuses = ["success"]
    overall = "partial" if any(s in {"failed", "partial"} for s in bundle_statuses) and any(s in {"success", "skipped"} for s in bundle_statuses) else ("failed" if any(s in {"failed", "partial"} for s in bundle_statuses) else "success")
    assert overall == "success"

    print("Gateway status normalization verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
