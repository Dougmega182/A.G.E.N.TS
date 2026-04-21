"""
External Gateway — The single choke point for all external execution.
Phase 3A: Hardened with replay protection, crash recovery, and operator validation.
"""

import uuid
import logging
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Set, List

from . import event_bus
from . import memory_db
from .. import firewall
from ..contracts import validate_action_intent

logger = logging.getLogger("agents.external_gateway")


class GatewayError(Exception):
    def __init__(self, reason: str, details: Optional[Dict[str, Any]] = None):
        self.reason = reason
        self.details = details or {}
        super().__init__(reason)


class ExternalGateway:
    """
    Hardened gateway with:
    - Replay protection (tracks executed approval IDs)
    - Crash recovery (execution state machine)
    - Rate limiting (configurable burst cap)
    - Operator-level input re-validation
    """

    def __init__(self, max_executions_per_minute: int = 10, approval_engine: Optional[firewall.PreflightApprovalEngine] = None):
        self.approval_engine = approval_engine or firewall.PreflightApprovalEngine()

        # Replay protection: set of approval_ids that have already been executed
        self._executed_approvals: Set[str] = set()

        # Execution ledger: tracks in-flight executions for crash recovery
        # Key: execution_trace_id, Value: state dict
        self._execution_ledger: Dict[str, Dict[str, Any]] = {}

        # Idempotency Protection: hash(trace_id + action + parameters)
        # Note: We exclude approval_id here to block duplicate payloads in the same trace 
        # even if they have different approval records.
        self._executed_idempotency_keys: Set[str] = set()
        
        # Restore persistent state
        self.restore_from_db()

        # Rate limiting
        self._max_per_minute = max_executions_per_minute
        self._recent_executions: list = []  # timestamps

    def _check_rate_limit(self):
        """Enforce execution rate limit. Prunes entries older than 60s."""
        now = datetime.utcnow()
        cutoff = 60  # seconds
        self._recent_executions = [
            ts for ts in self._recent_executions
            if (now - ts).total_seconds() < cutoff
        ]
        if len(self._recent_executions) >= self._max_per_minute:
            raise GatewayError("rate_limit_exceeded", {
                "limit": self._max_per_minute,
                "window": "60s",
                "current": len(self._recent_executions)
            })

    def _record_execution_start(self, execution_trace_id: str, approval_id: str, trace_id: str):
        """Record that an execution has started (for crash recovery)."""
        self._execution_ledger[execution_trace_id] = {
            "approval_id": approval_id,
            "trace_id": trace_id,
            "state": "started",
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "outcome": None,
            "error": None,
        }

    def _record_execution_complete(self, execution_trace_id: str, outcome: Dict[str, Any]):
        """Record successful completion."""
        if execution_trace_id in self._execution_ledger:
            entry = self._execution_ledger[execution_trace_id]
            entry["state"] = "completed"
            entry["completed_at"] = datetime.utcnow().isoformat()
            entry["outcome"] = outcome

    def _record_execution_failed(self, execution_trace_id: str, error: str):
        """Record failure (intent remains retryable)."""
        if execution_trace_id in self._execution_ledger:
            entry = self._execution_ledger[execution_trace_id]
            entry["state"] = "failed"
            entry["completed_at"] = datetime.utcnow().isoformat()
            entry["error"] = error

    def get_execution_state(self, execution_trace_id: str) -> Optional[Dict[str, Any]]:
        """Inspect the state of an execution (for crash recovery / debugging)."""
        return self._execution_ledger.get(execution_trace_id)

    def is_approval_executed(self, approval_id: str) -> bool:
        """Check if an approval has already been executed (replay protection)."""
        return approval_id in self._executed_approvals

    def restore_from_log(self, log_path: Optional[Path] = None):
        """
        Recover Gateway state strictly from the canonical event log.
        Ensures idempotency and replay protection survive system restarts.
        """
        from .event_bus import EVENTS_LOG_PATH
        target_path = log_path or EVENTS_LOG_PATH

        if not target_path.exists():
            logger.info("No event log found to restore gateway state from.")
            return

        logger.info(f"Restoring Gateway state from {target_path}...")
        count = 0
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if event.get("type") == "EXTERNAL_ACTION_EXECUTED":
                        meta = event.get("metadata", {})
                        
                        # Recover Idempotency
                        ikey = meta.get("idempotency_key")
                        if ikey:
                            self._executed_idempotency_keys.add(ikey)
                        
                        # Recover Approval Replay protection
                        # We need the approval_id. Currently it's in EXECUTION_STARTED but 
                        # we should ensure it's in EXECUTED for simpler recovery.
                        # For now, we'll look at EXTERNAL_ACTION_INTENT or similar if needed,
                        # but let's assume we enriched EXTERNAL_ACTION_EXECUTED in the previous step.
                        app_id = meta.get("approval_id")
                        if app_id:
                            self._executed_approvals.add(app_id)
                        
                        count += 1
            logger.info(f"Gateway restoration complete. Recovered {count} execution records.")
        except Exception as e:
            logger.error(f"Failed to restore Gateway state: {e}")

    def validate_and_execute(self, action_intent: Dict[str, Any], approval_id: str) -> Dict[str, Any]:
        """
        Highest security choke point.
        Ensures intent is approved, unchanged, not replayed, and traceable.
        """
        trace_id = action_intent.get("trace_id", "unknown")

        # 1. Rate Limit
        self._check_rate_limit()

        # 2. Basic Schema Validation
        validation = validate_action_intent(action_intent)
        if not validation.ok:
            raise GatewayError("invalid_intent_schema", {"reason": validation.reason})

        # 3. Retrieve Approval Record
        approval = self.approval_engine.get_request(approval_id)
        if not approval:
            raise GatewayError("approval_not_found", {"approval_id": approval_id})

        # 4. Check Approval Status
        if approval.get("status") != "approved":
            raise GatewayError("intent_not_approved", {"status": approval.get("status")})

        # 7. REPLAY PROTECTION — block double execution
        if self.is_approval_executed(approval_id):
            raise GatewayError("replay_blocked", {
                "approval_id": approval_id,
                "reason": "This approval has already been executed. Re-submission blocked."
            })

        # 7.5 INTENT VERSIONING (Guard against stale retries after context shift)
        metadata = action_intent.get("metadata", {})
        impact = metadata.get("impact", {})
        issue = metadata.get("scenario", action_intent.get("scenario", "unknown"))
        cost = impact.get("cost", 0)
        delay = impact.get("days", 0)
        
        incoming_version = hash(f"{issue}|{cost}|{delay}")
        
        # Pull original version from approval metadata if passed or recreate
        orig_metadata = approval.get("original_action_intent", {}).get("metadata", {})
        orig_impact = orig_metadata.get("impact", {})
        orig_issue = orig_metadata.get("scenario", approval.get("original_action_intent", {}).get("scenario", "unknown"))
        stored_version = hash(f"{orig_issue}|{orig_impact.get('cost', 0)}|{orig_impact.get('days', 0)}")
        
        if incoming_version != stored_version:
             raise GatewayError("aborted_stale_intent", {"reason": "Context shifted since intent generation."})

        # 8. Payload Integrity (Hash Check)
        current_hash = self.approval_engine._payload_hash(action_intent.get("parameters", {}))
        approved_hash = approval.get("payload_hash")

        if current_hash != approved_hash:
            raise GatewayError("payload_integrity_violation", {
                "expected": approved_hash,
                "actual": current_hash
            })

        # 9. Handle execution routing
        execution_trace_id = f"EXE-{uuid.uuid4().hex[:12].upper()}"
        self._record_execution_start(execution_trace_id, approval_id, trace_id)

        event_bus.emit_event("EXECUTION_STARTED", trace_id, agent_id="gateway", metadata={
            "execution_trace_id": execution_trace_id,
            "action": action_intent.get("action"),
            "approval_id": approval_id
        })

        intent_action = action_intent.get("action")
        
        if intent_action == "operator_bundle":
            bundle_results = []
            actions = action_intent.get("parameters", {}).get("actions", [])
            for single_action in actions:
                action_type = single_action.get("type", "unknown")
                # create a fake intent to reuse the gateway's key generation
                sub_intent = {
                    "action": action_type,
                    "parameters": single_action.get("payload", single_action)
                }
                
                # Check idempotency per action
                ikey = single_action.get("idempotency_key")
                if not ikey:
                    ikey = self._generate_idempotency_key(sub_intent)
                
                if ikey in self._executed_idempotency_keys:
                    bundle_results.append({
                        "type": action_type, 
                        "status": "skipped", 
                        "idempotency_key": ikey,
                        "reason": "already_executed_in_previous_run"
                    })
                    continue
                
                try:
                    from ..operators.operator_gateway import route_execution
                    res = route_execution(sub_intent, execution_trace_id)
                    
                    # Persist immediate success
                    self._executed_idempotency_keys.add(ikey)
                    memory_db.write_execution_key("orchestrator", ikey, execution_trace_id, trace_id, action_type)
                    
                    if res.get("status") == "SUCCESS":
                        external_id = res.get("draft_id") or res.get("event_id")
                        if external_id:
                            memory_db.enqueue_verification_job(
                                "orchestrator", 
                                action_type, 
                                external_id, 
                                sub_intent["parameters"], 
                                120
                            )

                    bundle_results.append({
                        "type": action_type, 
                        "status": "success", 
                        "idempotency_key": ikey,
                        "result": res
                    })
                except Exception as e:
                    # Fail fast but report all (don't roll back the others, continue with partial failure)
                    bundle_results.append({
                        "id": ikey,
                        "type": action_type, 
                        "status": "failed", 
                        "idempotency_key": ikey,
                        "error": str(e)
                    })
                    # HIGH LEVERAGE: Feed immediate logic/API failures back to Owen
                    from .owen_engine import OwenEngine
                    owen = OwenEngine()
                    owen.ingest_execution_failure({
                        "type": "TRUE_FAILURE", # It crashed before even creating an object
                        "action_type": action_type,
                        "diff_keys": ["api_connection_or_parameters"],
                        "confidence_penalty": 0.15 # High penalty for hard crashes
                    })
            
            # Record composite bundle result
            self._execution_ledger[execution_trace_id]["state"] = "completed"
            self._execution_ledger[execution_trace_id]["result"] = bundle_results
            self._executed_approvals.add(approval_id)
            self._recent_executions.append(datetime.utcnow())
            
            event_bus.emit_event(
                "EXTERNAL_ACTION_EXECUTED", trace_id, agent_id=action_intent.get("agent_id", "SYSTEM"), scenario=action_intent.get("scenario", "unknown"),
                metadata={
                    "execution_trace_id": execution_trace_id,
                    "approval_id": approval_id,
                    "status": "success",
                    "result": bundle_results
                }
            )
            return {
                "status": "success",
                "execution_trace_id": execution_trace_id,
                "result": bundle_results
            }

        else:
            # --- Fallback for old single-intent actions ---
            idempotency_key = self._generate_idempotency_key(action_intent)
            if idempotency_key in self._executed_idempotency_keys:
                raise GatewayError("duplicate_intent_blocked", {
                    "idempotency_key": idempotency_key,
                    "reason": "This identical intent/approval has already been executed successfully. Duplicate blocked."
                })
            
            try:
                from ..operators.operator_gateway import route_execution
                result = route_execution(action_intent, execution_trace_id)

                self._execution_ledger[execution_trace_id]["state"] = "completed"
                self._execution_ledger[execution_trace_id]["result"] = result
                self._executed_approvals.add(approval_id)
                self._executed_idempotency_keys.add(idempotency_key)
                self._recent_executions.append(datetime.utcnow())

                memory_db.write_execution_key("orchestrator", idempotency_key, execution_trace_id, trace_id, action_intent.get("action", "unknown"))

                if result.get("status") == "SUCCESS":
                    external_id = result.get("draft_id") or result.get("event_id")
                    if external_id:
                        memory_db.enqueue_verification_job(
                            "orchestrator", 
                            action_intent.get("action", "unknown"), 
                            external_id, 
                            action_intent.get("parameters", {}), 
                            120
                        )

                event_bus.emit_event(
                    "EXTERNAL_ACTION_EXECUTED", trace_id, agent_id=action_intent.get("agent_id", "SYSTEM"), scenario=action_intent.get("scenario", "unknown"),
                    metadata={
                        "execution_trace_id": execution_trace_id,
                        "approval_id": approval_id,
                        "idempotency_key": idempotency_key,
                        "status": "success",
                        "result": result
                    }
                )

                return {
                    "status": "success",
                    "execution_trace_id": execution_trace_id,
                    "idempotency_key": idempotency_key,
                    "result": result
                }

            except Exception as e:
                self._record_execution_failed(execution_trace_id, str(e))
                event_bus.emit_event("EXECUTION_FAILED", trace_id, agent_id="gateway", metadata={
                    "execution_trace_id": execution_trace_id,
                    "error": str(e)
                })
                raise GatewayError("operator_failure", {"error": str(e)})

    def _normalize_text(self, text: Any) -> str:
        """Aggressively collapse whitespace to prevent invisible duplicates."""
        if not isinstance(text, str):
            return str(text)
        return " ".join(text.strip().split())

    def _generate_idempotency_key(self, intent: Dict[str, Any]) -> str:
        """
        Generate a unique, deterministic hash for an intent.
        Formula: hash(action + recp + subject + body + time_bucket + salt)
        Excludes trace_id to block duplicate outcomes across time/traces.
        """
        action = intent.get("action", "")
        params = intent.get("parameters", {})
        
        # 1. Normalize core fields for Gmail (and fallback for generic)
        recipient = self._normalize_text(params.get("to", ""))
        subject = self._normalize_text(params.get("subject", ""))
        body = self._normalize_text(params.get("body", ""))
        
        # 2. Time Bucketing (ISO Year-Week) to allow periodic repeats
        time_bucket = datetime.utcnow().strftime("%Y-%W")
        
        # 3. Optional Salt for manual override
        salt = intent.get("metadata", {}).get("intent_salt", "")

        # 4. Deterministic Payload
        # For non-gmail actions, we fall back to a full parameter hash but still bucketed
        if not recipient and not subject:
            # Generic action normalization
            stable_params = json.dumps(params, sort_keys=True)
            raw_str = f"{action}:{stable_params}:{time_bucket}:{salt}"
        else:
            # Action specific normalization
            raw_str = f"{action}:{recipient}:{subject}:{body}:{time_bucket}:{salt}"
        
        return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def restore_from_db(self):
        """Load seen idempotency keys from persistent storage on startup."""
        keys = memory_db.read_execution_keys("orchestrator")
        self._executed_idempotency_keys.update(keys)
        logger.info(f"Gateway restored {len(keys)} persistent idempotency keys.")
