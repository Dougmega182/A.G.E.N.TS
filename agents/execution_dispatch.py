from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any, Dict

from . import preflight_validator as firewall
from .logic.event_bus import emit_event
from .logic import pattern_registry


EXECUTION_TASKS: Dict[str, asyncio.Task] = {}


def _update_request_execution_fields(request_id: str, **fields: Any) -> Dict[str, Any] | None:
    store = firewall.DEFAULT_ENGINE._load_store()
    updated = None
    for idx, request in enumerate(store["requests"]):
        if request.get("request_id") == request_id:
            request.update(fields)
            store["requests"][idx] = request
            updated = request
            break
    if updated is not None:
        firewall.DEFAULT_ENGINE._save_store(store)
    return updated


def _get_request(request_id: str) -> Dict[str, Any] | None:
    return firewall.get_request(request_id)


def _resolve_dry_run(request: Dict[str, Any], dry_run_override: bool | None = None) -> bool:
    if dry_run_override is not None:
        return bool(dry_run_override)
    metadata = request.get("metadata", {}) if isinstance(request, dict) else {}
    return bool(metadata.get("dry_run", False))


def _derive_outcome_from_result(result: Any, error: str | None = None) -> str:
    if error:
        return "failure"

    quality = pattern_registry.derive_execution_quality_signal(result)
    if quality in {"success", "partial", "failure"}:
        return quality
    return "success"


def finalize_outcome(request_id: str, outcome: str, error: str | None = None, result: Any = None) -> Dict[str, Any] | None:
    request = _get_request(request_id)
    if not request:
        return None

    trace_id = request.get("trace_id", request_id)
    finalized_request = _update_request_execution_fields(
        request_id,
        execution_status="completed",
        outcome=outcome,
        outcome_error=error,
        outcome_finalized_at=datetime.utcnow().isoformat(),
    )

    severity = request.get("metadata", {}).get("severity")
    approval_note = request.get("decision_reason", "")
    
    # Calculate decision latency (time from request creation to approval)
    created_at_str = request.get("created_at")
    decided_at_str = request.get("decided_at")
    latency_sec = 0.0
    if created_at_str and decided_at_str:
        try:
            def _parse_iso(s: str) -> datetime:
                # Handle 'Z' or offset if present, otherwise assume naive UTC
                if s.endswith("Z"):
                    return datetime.fromisoformat(s.replace("Z", "+00:00"))
                return datetime.fromisoformat(s)

            c = _parse_iso(created_at_str)
            d = _parse_iso(decided_at_str)
            
            # Ensure comparison works even if one is naive and other is aware
            if c.tzinfo is not None and d.tzinfo is None:
                d = d.replace(tzinfo=c.tzinfo)
            elif d.tzinfo is not None and c.tzinfo is None:
                c = c.replace(tzinfo=d.tzinfo)
                
            latency_sec = (d - c).total_seconds()
        except Exception:
            pass

    metadata = {
        "request_id": request_id,
        "outcome": outcome,
        "error": error,
    }

    if str(severity).upper() == "HIGH_DELAY":
        metadata.update({
            "severity": severity,
            "approval_note": approval_note,
            "note_length": len(approval_note),
            "decision_latency_seconds": round(max(0, latency_sec), 2),
        })

    emit_event(
        "OUTCOME_FINALIZED",
        trace_id,
        agent_id="SYSTEM",
        scenario="preflight",
        metadata=metadata,
    )

    quality = pattern_registry.derive_execution_quality_signal(result)
    if quality is None:
        quality = "success" if outcome == "success" else "failure"

    pattern_registry.log_outcome_quality_update(
        trace_id=trace_id,
        outcome_quality_signal=quality,
        signal_source="execution",
        source="execution_completion",
        details={"request_id": request_id, "error": error},
    )
    return finalized_request


async def _run_execution(request_id: str, source: str, dry_run_override: bool | None = None) -> None:
    request = _get_request(request_id)
    if not request:
        emit_event(
            "TASK_EXECUTION_FAILED",
            request_id,
            agent_id="SYSTEM",
            scenario="preflight",
            metadata={"request_id": request_id, "source": source, "error": "approval_request_not_found"},
        )
        return

    trace_id = request.get("trace_id", request_id)
    dry_run = _resolve_dry_run(request, dry_run_override)

    _update_request_execution_fields(
        request_id,
        execution_status="running",
        execution_started_at=datetime.utcnow().isoformat(),
        execution_source=source,
    )
    emit_event(
        "TASK_EXECUTION_STARTED",
        trace_id,
        agent_id="SYSTEM",
        scenario="preflight",
        metadata={"request_id": request_id, "source": source, "dry_run": dry_run},
    )

    try:
        if dry_run:
            result = {
                "status": "dry_run",
                "message": "Execution safety bypass engaged. No real limits or side-effects triggered.",
                "action_target": request.get("action"),
            }
            _update_request_execution_fields(
                request_id,
                status="executed",
                executed_at=datetime.utcnow().isoformat(),
            )
        else:
            result = await firewall.execute_task(request_id)

        emit_event(
            "TASK_EXECUTION_COMPLETED",
            trace_id,
            agent_id="SYSTEM",
            scenario="preflight",
            metadata={"request_id": request_id, "source": source, "dry_run": dry_run},
        )
        finalize_outcome(
            request_id,
            outcome=_derive_outcome_from_result(result),
            result=result,
        )
    except Exception as e:
        _update_request_execution_fields(
            request_id,
            execution_status="failed",
            execution_error=str(e),
            execution_failed_at=datetime.utcnow().isoformat(),
        )
        emit_event(
            "TASK_EXECUTION_FAILED",
            trace_id,
            agent_id="SYSTEM",
            scenario="preflight",
            metadata={"request_id": request_id, "source": source, "error": str(e)},
        )
        finalize_outcome(request_id, outcome="failure", error=str(e))
    finally:
        EXECUTION_TASKS.pop(request_id, None)


def enqueue_execution(request_id: str, source: str, dry_run_override: bool | None = None) -> Dict[str, Any]:
    request = _get_request(request_id)
    if not request:
        raise firewall.PreflightApprovalError("approval_request_not_found", {"request_id": request_id})

    execution_status = str(request.get("execution_status") or "").lower()
    if execution_status in {"queued", "running", "completed"}:
        emit_event(
            "TASK_EXECUTION_SKIPPED_ALREADY_HANDLED",
            request.get("trace_id", request_id),
            agent_id="SYSTEM",
            scenario="preflight",
            metadata={
                "request_id": request_id,
                "execution_status": request.get("execution_status"),
                "source": source,
            },
        )
        return {
            "status": "skipped",
            "request_id": request_id,
            "execution_status": request.get("execution_status"),
        }

    if str(request.get("status", "")).lower() != "approved":
        raise firewall.PreflightApprovalError(
            "task_not_approved",
            {"request_id": request_id, "status": request.get("status")},
        )

    dry_run = _resolve_dry_run(request, dry_run_override)
    updated_request = _update_request_execution_fields(
        request_id,
        execution_status="queued",
        execution_queued_at=datetime.utcnow().isoformat(),
        execution_source=source,
        dry_run=dry_run,
    ) or request

    emit_event(
        "TASK_EXECUTION_QUEUED",
        updated_request.get("trace_id", request_id),
        agent_id="SYSTEM",
        scenario="preflight",
        metadata={"request_id": request_id, "source": source, "dry_run": dry_run},
    )

    try:
        loop = asyncio.get_running_loop()
        EXECUTION_TASKS[request_id] = loop.create_task(_run_execution(request_id, source, dry_run))
        return {
            "status": "queued",
            "request_id": request_id,
            "message": "Execution accepted and queued in background.",
        }
    except RuntimeError:
        asyncio.run(_run_execution(request_id, source, dry_run))
        return {
            "status": "completed",
            "request_id": request_id,
            "message": "Execution completed synchronously.",
        }
