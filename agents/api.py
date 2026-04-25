from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse, FileResponse
from pydantic import BaseModel
from typing import Optional, Dict
from pathlib import Path
import json
from .roster import AGENTS
from .orchestrator import Orchestrator
from .telemetry import TELEMETRY
from . import firewall
from .firewall import PreflightApprovalError
from .execution_dispatch import enqueue_execution
from .logic.event_bus import EVENTS_LOG_PATH
from .logic.event_bus import emit_event
import os
import asyncio
from datetime import datetime

app = FastAPI(title="A.G.E.N.T.S. Interactive API")

# Enable CORS for the local web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Orchestrator
orc = Orchestrator()

@app.get("/")
async def root():
    return RedirectResponse(url="/operator")

@app.get("/operator")
async def get_operator_app():
    return FileResponse("web/index.html")

class ChatRequest(BaseModel):
    message: str

class ApprovalDecisionRequest(BaseModel):
    request_id: str
    decision: str
    decided_by: Optional[str] = "gatekeeper"
    reason: Optional[str] = ""

class DraftSummaryUpdateRequest(BaseModel):
    draft_id: str
    summary: str

class TaskExecuteRequest(BaseModel):
    request_id: str
    dry_run: bool = False

class OperatorRunRequest(BaseModel):
    issue: str
    cost: float
    delay: int
    dry_run: bool = True

class OperatorFeedbackRequest(BaseModel):
    execution_trace_id: str
    trace_id: str
    outcome: str
    notes: str
    delay_actual: int
    cost_actual: float

@app.get("/status")
async def get_status():
    return {
        "status": "orchestration_active",
        "session_id": orc.session_id,
        "agents_total": len(AGENTS)
    }

@app.get("/agents")
async def list_agents():
    """List all available agents in the roster."""
    return [
        {"id": v["id"], "name": v["name"], "title": v["title"], "triggers": v["triggers"]}
        for k, v in AGENTS.items()
    ]

@app.get("/telemetry")
async def get_telemetry():
    """Return live token and cost stats in the new structured format."""
    return TELEMETRY.get_stats()

@app.get("/telemetry/miss-clusters")
async def get_miss_clusters():
    """Analyze the event log to return the top 5 cache miss clusters for Layer 2 Semantic Cache feeding."""
    if not EVENTS_LOG_PATH.exists():
        return {"clusters": []}

    from collections import Counter
    miss_clusters = Counter()
    total_lookups = 0
    cache_hits = 0

    with open(EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                event = json.loads(line)
                event_type = event.get("type")
                metadata = event.get("metadata", {})

                if event_type == "CACHE_HIT":
                    cache_hits += 1
                    total_lookups += 1
                elif event_type == "CACHE_MISS":
                    total_lookups += 1
                    if "normalized_issue" in metadata:
                        miss_clusters[metadata["normalized_issue"]] += 1
            except json.JSONDecodeError:
                continue

    top_clusters = [{"issue": issue, "count": count} for issue, count in miss_clusters.most_common(5)]
    hit_rate = (cache_hits / total_lookups) * 100 if total_lookups > 0 else 0

    return {
        "hit_rate_percent": round(hit_rate, 2),
        "total_lookups": total_lookups,
        "clusters": top_clusters
    }

@app.get("/preflight/approvals")
async def get_preflight_approvals(status: Optional[str] = None, limit: int = 100):
    return {
        "items": firewall.list_requests(status=status, limit=limit),
        "count": len(firewall.list_requests(status=status, limit=limit))
    }

@app.get("/preflight/approvals/{request_id}")
async def get_preflight_approval(request_id: str):
    item = firewall.get_request(request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="approval_request_not_found")
    return item

@app.post("/preflight/approvals/decide")
async def decide_preflight_approval(req: ApprovalDecisionRequest):
    try:
        return firewall.decide_request(
            request_id=req.request_id,
            decision=req.decision,
            decided_by=req.decided_by or "gatekeeper",
            reason=req.reason or "",
        )
    except PreflightApprovalError as e:
        status_code = 404 if e.reason == "approval_request_not_found" else 400
        raise HTTPException(status_code=status_code, detail={"reason": e.reason, "details": e.details})

@app.get("/preflight/drafts")
async def get_preflight_drafts(action: Optional[str] = None, limit: int = 100):
    items = firewall.list_drafts(action=action, limit=limit)
    return {
        "items": items,
        "count": len(items)
    }

@app.get("/preflight/drafts/{draft_id}")
async def get_preflight_draft(draft_id: str):
    item = firewall.get_draft(draft_id)
    if item is None:
        raise HTTPException(status_code=404, detail="preflight_draft_not_found")
    return item

@app.post("/preflight/drafts/summary")
async def update_preflight_draft_summary(req: DraftSummaryUpdateRequest):
    try:
        return firewall.update_draft_summary(draft_id=req.draft_id, summary=req.summary)
    except PreflightApprovalError as e:
        raise HTTPException(status_code=404, detail={"reason": e.reason, "details": e.details})

@app.post("/preflight/tasks/execute")
async def execute_preflight_task(req: TaskExecuteRequest):
    """Manually enqueue a task that has already been approved."""
    try:
        return enqueue_execution(
            request_id=req.request_id,
            source="manual_api",
            dry_run_override=req.dry_run,
        )
    except PreflightApprovalError as e:
        raise HTTPException(status_code=400, detail={"reason": e.reason, "details": e.details})

@app.post("/operator/run")
async def operator_run(req: OperatorRunRequest):
    """Runs the Orchestrator loop specifically configured by the Operator Form."""
    async def event_generator():
        trace_id = f"UI-OP-{datetime.now().strftime('%M%S')}"
        user_input = f"Issue: {req.issue}. Cost impact: ${req.cost}. Delay: {req.delay} days."
        issue_label = " ".join(str(req.issue or "").split()).strip()
        
        try:
            yield (
                "data: [ARIA] "
                f"Aria: Acknowledge Dale, request received for {issue_label or 'operator submission'}. "
                "Now engaging the site issue workflow.\n\n"
            )
            # Note: We aren't cleanly injecting dry_run into the strict orchestration 
            # loop right here because orchestrator builds the action_intent.
            # However, for simplicity, we append it to the user_input context or
            # rely on the fact that execution is manually routed. Actually, we 
            # can't easily inject metadata into `_run_generic_construction_loop` without modifying it.
            # But the gateway parses `dry_run` from metadata. Let's just pass it in string.
            if req.dry_run:
                 user_input += " [DRY RUN ACTIVE: DO NOT EXECUTE SIDE EFFECTS]"
                 
            async for data in orc._run_generic_construction_loop("site_issue", user_input, trace_id):
                yield data + "\n"
        except Exception as e:
            yield f"data: [ORCHESTRATOR ERROR] {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/operator/feedback")
async def operator_feedback(req: OperatorFeedbackRequest):
    """Logs post-execution intelligence back into the system."""
    try:
        emit_event(
            "POST_EXECUTION_REVIEW_V1",
            req.trace_id,
            agent_id="OPERATOR",
            scenario="post_execution",
            metadata={
                "execution_trace_id": req.execution_trace_id,
                "outcome": req.outcome,
                "notes": req.notes,
                "delay_actual": req.delay_actual,
                "cost_actual": req.cost_actual
            }
        )
        
        from .logic.owen_engine import OwenEngine
        om = OwenEngine()
        om.extract_lesson_from_feedback(req.trace_id, req.outcome, req.notes)

        from .logic import pattern_registry
        outcome = str(req.outcome).strip().lower()
        if outcome in {"success", "passed", "verified_success"}:
            quality = "success"
        elif outcome in {"partial", "degraded_success", "warning"}:
            quality = "partial"
        elif outcome in {"failure", "failed", "drift_confirmed", "true_failure"}:
            quality = "failure"
        else:
            quality = outcome or "unknown"
        pattern_registry.log_outcome_quality_update(
            trace_id=req.trace_id,
            outcome_quality_signal=quality,
            signal_source="operator",
            source="operator_feedback",
            details={
                "execution_trace_id": req.execution_trace_id,
                "notes": req.notes,
                "delay_actual": req.delay_actual,
                "cost_actual": req.cost_actual,
            },
        )
        
        return {"status": "success", "message": "Feedback integrated into events log and Owen Engine."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# State for Phase 2.3 Task Queue (Visual Dispatch)
from .logic.task_queue import (
    enqueue_logistics_task as queue_task,
    list_logistics_tasks,
    get_logistics_task,
    resolve_logistics_task
)

@app.get("/logistics/tasks")
async def get_logistics_tasks():
    """Returns the queue of pending logistics dispatch intents."""
    tasks = list_logistics_tasks()
    return {"items": tasks, "count": len(tasks)}

@app.post("/logistics/tasks/{task_id}/decide")
async def decide_logistics_task(task_id: str, decision: str):
    """Approve or reject a logistics task intent."""
    task = get_logistics_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if decision.lower() == "approve":
        # 1. Physically execute the Gmail Draft if present
        if "gmail_draft" in task:
            from .operators.gmail_operator import execute_gmail_draft
            # Simulated trace id
            exe_trace = f"EXE-ELI-{uuid.uuid4().hex[:8].upper()}"
            execute_gmail_draft(task["gmail_draft"], exe_trace)
        
        task["status"] = "approved"
        event_bus.emit_event("LOGISTICS_TASK_APPROVED", task["trace_id"], agent_id="gatekeeper", metadata={"task_id": task_id})
    else:
        task["status"] = "rejected"
        event_bus.emit_event("LOGISTICS_TASK_REJECTED", task["trace_id"], agent_id="gatekeeper", metadata={"task_id": task_id})

    # Remove from pending queue
    resolve_logistics_task(task_id)
    
    return {"status": "success", "task_id": task_id, "decision": decision}

@app.post("/logistics/tasks/enqueue")
async def enqueue_logistics_task(task: Dict[str, Any]):
    """Internal endpoint for Orchestrator to push logistics intents."""
    task_id = queue_task(task)
    return {"status": "success", "task_id": task_id}

@app.get("/preflight/events")
async def get_preflight_events(limit: int = 200):
    if not EVENTS_LOG_PATH.exists():
        return {"items": [], "count": 0}

    rows = []
    with open(EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except Exception:
                continue
            if str(event.get("scenario", "")).lower() == "preflight" or str(event.get("type", "")).startswith("APPROVAL_") or str(event.get("type", "")).startswith("ACTION_") or str(event.get("type", "")).startswith("EXTERNAL_ACTION_"):
                rows.append(event)

    rows = list(reversed(rows))[:max(1, limit)]
    return {"items": rows, "count": len(rows)}

@app.get("/events/stream")
async def event_stream():
    """SSE endpoint that tails events.log.jsonl in real-time."""
    async def event_generator():
        last_position = 0
        while True:
            if not EVENTS_LOG_PATH.exists():
                await asyncio.sleep(1) # Wait if file doesn't exist yet
                continue

            with open(EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
                f.seek(last_position)
                new_events = f.readlines()
                last_position = f.tell()

                for event_line in new_events:
                    event_line = event_line.strip()
                    if event_line:
                        yield f"data: {event_line}\n\n"
            await asyncio.sleep(0.1) # Short delay to prevent busy-waiting

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/project/health")
async def get_project_health():
    """Returns real project health derived from the event stream."""
    from .logic.event_analytics import get_risk_trend_from_events, get_outcome_signal

    trend = get_risk_trend_from_events()
    variation_signal = get_outcome_signal("variation", limit=5)
    
    return {
        "risk_trend": trend,
        "outcome_signal": variation_signal,
    }


@app.get("/decisions/latest")
async def get_latest_decisions(limit: int = 5, scenario: Optional[str] = None):
    """Returns latest DECISION_FINALIZED_V1 events — the canonical decision record."""
    if not EVENTS_LOG_PATH.exists():
        return {"items": [], "count": 0}

    events = []
    with open(EVENTS_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except Exception:
                continue
            if event.get("type") == "DECISION_FINALIZED_V1":
                if scenario and event.get("scenario", "").lower() != scenario.lower():
                    continue
                events.append(event)

    latest = list(reversed(events))[:max(1, limit)]
    return {"items": latest, "count": len(latest)}


@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """The unified multi-agent chat endpoint via Orchestrated streaming."""
    async def event_generator():
        try:
            async for token in orc.astream_chat(req.message):
                yield token
        except Exception as e:
            yield f"data: [ORCHESTRATOR ERROR] {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
