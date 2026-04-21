import asyncio
import sys
import argparse
import json
import uuid
import re
from datetime import datetime
from pathlib import Path

# Force UTF-8 encoding for stdout to prevent UnicodeEncodeError on Windows (cp1252)
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent))

from agents.orchestrator import Orchestrator
from agents.firewall import decide_request, execute_task

USAGE_LOG_PATH = Path(__file__).parent / "Agent logs" / "usage_feedback.jsonl"


def _prompt_optional(label: str) -> str:
    """Prompt for optional input; empty/EOF/Ctrl+C returns ''."""
    try:
        return input(label).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def _parse_yn(raw: str):
    """Return True/False/None. None means skipped."""
    if not raw:
        return None
    r = raw.strip().lower()
    if r in ("y", "yes", "1", "true"):
        return True
    if r in ("n", "no", "0", "false"):
        return False
    return None


def _parse_minutes(raw: str):
    """Parse minutes as int; returns None if blank or invalid."""
    if not raw:
        return None
    try:
        return int(float(raw))
    except ValueError:
        return None


def capture_usage_feedback(context: dict) -> None:
    """
    Append a single JSONL entry capturing whether this run saved time,
    required manual override, and whether the user would use it again.
    All three inputs are optional; a fully-blank response is NOT logged.
    """
    print_separator("USAGE FEEDBACK")
    print("Three quick inputs. Press Enter to skip any of them.")
    print("(Skipping all three will discard this feedback entry.)\n")

    minutes_raw = _prompt_optional("Time saved vs doing this manually? (minutes): ")
    override_raw = _prompt_optional("Did you need to manually override/redo anything? (y/n): ")
    reuse_raw = _prompt_optional("Would you use this again for a similar issue? (y/n): ")
    notes_raw = _prompt_optional("Notes (optional): ")

    time_saved_minutes = _parse_minutes(minutes_raw)
    manual_override_required = _parse_yn(override_raw)
    would_use_again = _parse_yn(reuse_raw)

    # If the user skipped everything, don't pollute the log
    if time_saved_minutes is None and manual_override_required is None and would_use_again is None and not notes_raw:
        print("[FEEDBACK] Skipped — no entry written.")
        return

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "request_id": context.get("request_id"),
        "trace_id": context.get("trace_id"),
        "scenario": context.get("scenario"),
        "final_decision": context.get("final_decision"),
        "user_action": context.get("user_action"),
        "why": context.get("why"),
        "distrust_level": context.get("distrust_level"),
        "risk_score": context.get("risk_score"),
        "confidence_score": context.get("confidence_score"),
        "confidence_adjusted": context.get("confidence_adjusted"),
        "confidence_penalty": context.get("confidence_penalty"),
        "confidence_threshold": context.get("confidence_threshold"),
        "drift_pressure_index": context.get("drift_pressure_index"),
        "time_saved_minutes": time_saved_minutes,
        "manual_override_required": manual_override_required,
        "would_use_again": would_use_again,
        "notes": notes_raw or None,
    }

    try:
        USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with USAGE_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"[FEEDBACK] Logged to {USAGE_LOG_PATH}")
    except OSError as e:
        print(f"[FEEDBACK] Failed to write feedback log: {e}")

def print_separator(title=""):
    width = 80
    if title:
        padding = (width - len(title) - 2) // 2
        print(f"\n{'=' * padding} {title.upper()} {'=' * padding}\n")
    else:
        print(f"\n{'=' * width}\n")

async def main():
    parser = argparse.ArgumentParser(description="A.G.E.N.T.S Issue Logging CLI")
    parser.add_argument("issue", type=str, help="Description of the issue (e.g. 'Rain delay slab')")
    parser.add_argument("cost", type=str, nargs="?", default="0", help="Estimated cost impact")
    parser.add_argument("days", type=str, nargs="?", default="0", help="Estimated schedule impact in days")
    
    args = parser.parse_args()
    
    # Clean the inputs
    issue = args.issue
    cost = str(args.cost).replace('$', '').replace(',', '')
    days = str(args.days).replace('days', '').strip()
    
    user_input = f"Variation: +${cost}, +{days} days, {issue}"
    
    print_separator("A.G.E.N.T.S. CLI")
    print(f"INPUT STREAM: {user_input}")
    print_separator("AGENT REASONING STREAM")

    orchestrator = Orchestrator()
    request_id = None
    action_intent_payload = None

    # We will buffer the output to provide a clean summary at the end
    # but still show the stream live.
    
    try:
        async for chunk in orchestrator.astream_chat(user_input):
            if chunk.startswith("data: "):
                content = chunk.replace("data: ", "").strip()
                if content:
                    # Capture request ID if it signals proposal creation
                    match = re.search(r"Request ID: (APR-[A-Z0-9]+)", content)
                    if match:
                        request_id = match.group(1)
                    
                    # Print natively
                    print(content)
                    
    except KeyboardInterrupt:
        print("\n\n[SYSTEM] Stream interrupted by user.")
        sys.exit(1)
        
    print_separator("EXECUTION PREVIEW")
    
    if not request_id:
        print("[!] No approval request generated by the system. Interaction complete.")
        sys.exit(0)
        
    # Fetch the full request from firewall
    from agents.firewall import get_request
    request = get_request(request_id)
    if not request:
        print(f"[!] Critical Error: Request {request_id} not found in firewall registry.")
        sys.exit(1)
        
    intent = request.get("original_action_intent", {})
    metadata = intent.get("metadata", {})
    params = intent.get("parameters", {})
    
    print(f"DECISION:   {metadata.get('final_decision', 'UNKNOWN')}")
    print(f"CONFIDENCE: {params.get('confidence', 0.0)}")
    print(f"RISKS FLAG: {', '.join(params.get('risks', [])) or 'None'}")

    # Human-readable single-line explanation (the "WHY" block)
    why_line = metadata.get("why") or ""
    if why_line:
        print(f"\nWHY:        {why_line}")

    print("\nJUSTIFICATION:")
    print(metadata.get('final_justification', 'No justification provided.'))
    
    actions = params.get("actions", [])
    if actions:
        print(f"\nACTIONS ({len(actions)}):")
        for idx, act in enumerate(actions, 1):
            act_type = act.get("type", "unknown")
            print(f"  {idx}. [{act_type.upper()}] - {act.get('reason', '')}")
            
    print_separator()
    
    # The Prompt
    choice = input(f"Approve execution of {request_id}? (y/n): ").strip().lower()

    user_action = "approved" if choice in ['y', 'yes'] else "rejected"

    if choice in ['y', 'yes']:
        print(f"\n[GATEKEEPER] Approved. Routing to External Gateway...")
        try:
            decide_request(request_id, "approve", decided_by="cli_gatekeeper", reason="CLI Approval")
            
            # Note: We now execute the intent via the firewall which delegates securely to the gateway.
            result = await execute_task(request_id)
            
            print_separator("EXECUTION RESULT")
            print(json.dumps(result, indent=2))
            print_separator()
            
        except Exception as e:
            print(f"\n[ERROR] Execution failed: {e}")
            
    else:
        print(f"\n[GATEKEEPER] Rejected.")
        try:
            decide_request(request_id, "reject", decided_by="cli_gatekeeper", reason="CLI Rejection")
        except Exception as e:
            pass

    # Capture lightweight usage feedback so we can tell if this is actually
    # saving time. Fully skippable; no entry is written if all inputs are blank.
    feedback_context = {
        "request_id": request_id,
        "trace_id": request.get("trace_id"),
        "scenario": metadata.get("scenario"),
        "final_decision": metadata.get("final_decision"),
        "user_action": user_action,
        "why": metadata.get("why"),
        "distrust_level": metadata.get("distrust_level"),
        "risk_score": metadata.get("risk_score"),
        "confidence_score": metadata.get("confidence_score", params.get("confidence")),
        "confidence_adjusted": metadata.get("confidence_adjusted"),
        "confidence_penalty": metadata.get("confidence_penalty"),
        "confidence_threshold": metadata.get("confidence_threshold"),
        "drift_pressure_index": metadata.get("drift_pressure_index"),
    }
    try:
        capture_usage_feedback(feedback_context)
    except KeyboardInterrupt:
        print("\n[FEEDBACK] Skipped by user.")

if __name__ == "__main__":
    asyncio.run(main())
