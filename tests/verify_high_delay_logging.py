import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

# Add root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents import execution_dispatch

def test_high_delay_logging():
    request_id = "APR-TEST123"
    trace_id = "TRC-TEST123"
    
    # Mock request data
    # Decided 1 hour after creation
    now = datetime.utcnow()
    # Use different formats to test robustness
    created_at = (now - timedelta(hours=1)).isoformat() + "Z"
    decided_at = now.isoformat() # No Z
    
    mock_request = {
        "request_id": request_id,
        "trace_id": trace_id,
        "status": "approved",
        "metadata": {"severity": "HIGH_DELAY"},
        "decision_reason": "Necessary for site safety",
        "created_at": created_at,
        "decided_at": decided_at
    }
    
    captured_events = []
    
    def mock_emit_event(event_type, trace_id, **kwargs):
        captured_events.append({"type": event_type, "trace_id": trace_id, "kwargs": kwargs})

    print(f"Testing with created_at={created_at}, decided_at={decided_at}")

    with patch("agents.execution_dispatch._get_request", return_value=mock_request), \
         patch("agents.execution_dispatch._update_request_execution_fields", return_value=mock_request), \
         patch("agents.execution_dispatch.emit_event", side_effect=mock_emit_event), \
         patch("agents.logic.pattern_registry.derive_execution_quality_signal", return_value="failure"), \
         patch("agents.logic.pattern_registry.log_outcome_quality_update"):
        
        execution_dispatch.finalize_outcome(request_id, "failure", error="System crash")
    
    # Check OUTCOME_FINALIZED event
    outcome_event = next((e for e in captured_events if e["type"] == "OUTCOME_FINALIZED"), None)
    if not outcome_event:
        print("Error: OUTCOME_FINALIZED event not captured")
        sys.exit(1)
        
    metadata = outcome_event["kwargs"]["metadata"]
    print(f"Captured metadata: {metadata}")
    
    assert metadata["severity"] == "HIGH_DELAY"
    assert metadata["approval_note"] == "Necessary for site safety"
    assert metadata["note_length"] == len("Necessary for site safety")
    # 1 hour = 3600 seconds
    assert 3590 < metadata["decision_latency_seconds"] < 3610
    assert metadata["outcome"] == "failure"
    
    print("HIGH_DELAY logging verification passed.")

if __name__ == "__main__":
    try:
        test_high_delay_logging()
    except Exception as e:
        print(f"Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
