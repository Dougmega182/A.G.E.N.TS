import os
import json
import logging
import hashlib
import uuid
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from .leases import MissionLease, generate_intent_hash
from agents.contracts import validate_action_intent, ContractValidationResult

# Setup high-fidelity firewall audit log
LOG_ROOT = Path("Agent logs")
LOG_ROOT.mkdir(parents=True, exist_ok=True)

FIREWALL_LOG = LOG_ROOT / "firewall.jsonl"
PREFLIGHT_STORE = Path(os.getenv("AGENTS_PREFLIGHT_STORE", str(LOG_ROOT / "preflight_approvals.json")))
PREFLIGHT_DRAFT_STORE = Path(os.getenv("AGENTS_PREFLIGHT_DRAFT_STORE", str(LOG_ROOT / "preflight_drafts.json")))

class FirewallViolation(Exception):
    def __init__(self, reason: str, details: dict):
        self.reason = reason
        self.details = details
        super().__init__(reason)

class PreflightApprovalError(Exception):
    def __init__(self, reason: str, details: Optional[dict] = None):
        self.reason = reason
        self.details = details or {}
        super().__init__(reason)

class PreflightApprovalEngine:
    def __init__(self, store_path: Optional[Path] = None, draft_store_path: Optional[Path] = None):
        # Dynamically evaluate store paths to allow test isolation via env vars
        self.store_path = store_path or Path(os.getenv("AGENTS_PREFLIGHT_STORE", str(PREFLIGHT_STORE)))
        self.draft_store_path = draft_store_path or Path(os.getenv("AGENTS_PREFLIGHT_DRAFT_STORE", str(PREFLIGHT_DRAFT_STORE)))
        self._store: Optional[Dict[str, Any]] = None
        self._draft_store: Optional[Dict[str, Any]] = None

    @staticmethod
    def _default_store() -> Dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "updated_at": datetime.utcnow().isoformat(),
            "requests": []
        }

    def _load_store(self) -> Dict[str, Any]:
        if not self.store_path.exists():
            return self._default_store()
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = self._default_store()
            if not isinstance(data.get("requests"), list):
                data["requests"] = []
            self._store = data
            return self._store
        except Exception:
            self._store = self._default_store()
            return self._store

    def _save_store(self, store: Dict[str, Any]):
        self._store = store
        self._store["updated_at"] = datetime.utcnow().isoformat()
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(self._store, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _default_draft_store() -> Dict[str, Any]:
        return {
            "schema_version": "1.0.0",
            "updated_at": datetime.utcnow().isoformat(),
            "drafts": []
        }

    def _load_draft_store(self) -> Dict[str, Any]:
        if self._draft_store is not None:
            return self._draft_store

        if not self.draft_store_path.exists():
            self._draft_store = self._default_draft_store()
            return self._draft_store
        try:
            with open(self.draft_store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = self._default_draft_store()
            if not isinstance(data.get("drafts"), list):
                data["drafts"] = []
            self._draft_store = data
            return self._draft_store
        except Exception:
            self._draft_store = self._default_draft_store()
            return self._draft_store

    def _save_draft_store(self, store: Dict[str, Any]):
        self._draft_store = store
        self._draft_store["updated_at"] = datetime.utcnow().isoformat()
        with open(self.draft_store_path, "w", encoding="utf-8") as f:
            json.dump(self._draft_store, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _payload_snapshot(payload: Any) -> Any:
        if payload is None:
            return {}
        if isinstance(payload, bytes):
            return payload.decode("utf-8", errors="replace")
        if isinstance(payload, (dict, list, str, int, float, bool)):
            return payload
        return str(payload)

    def _payload_hash(self, payload: Any) -> str:
        payload_snapshot = self._payload_snapshot(payload)
        payload_json = json.dumps(payload_snapshot, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()

    @staticmethod
    def _fingerprint(agent_id: str, action: str, target: str, payload_hash: str) -> str:
        raw = f"{agent_id}|{action}|{target}|{payload_hash}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def create_or_get_request(
        self,
        action_intent: Dict[str, Any],
    ) -> Dict[str, Any]:
        validation_result = validate_action_intent(action_intent)
        if not validation_result.ok:
            raise PreflightApprovalError(
                "invalid_action_intent_schema",
                {"reason": validation_result.reason, "intent": action_intent}
            )
        
        store = self._load_store()
        
        # Use fields from the validated action_intent
        action = action_intent["action"]
        agent_id = action_intent["agent_id"]
        parameters = action_intent["parameters"]
        trace_id = action_intent["trace_id"]
        
        # Recalculate payload hash and fingerprint based on the *validated* intent's parameters
        payload_hash = self._payload_hash(parameters)
        fingerprint = self._fingerprint(agent_id, action, json.dumps(parameters, sort_keys=True), payload_hash)

        # Look for existing pending requests with the same fingerprint
        for request in reversed(store["requests"]):
            if request.get("fingerprint") == fingerprint and request.get("status") == "pending":
                return request

        # Create a new request based on the action_intent
        request = {
            "request_id": f"APR-{uuid.uuid4().hex[:12].upper()}",
            "status": "pending",
            "execution_status": None,
            "outcome": None,
            "action": action,
            "agent_id": agent_id,
            "trace_id": trace_id,
            "summary": action_intent.get("summary", ""), # Allow summary to be passed, or default
            "metadata": action_intent.get("metadata", {}), # Allow metadata to be passed, or default
            "payload": parameters, # Store the actual parameters from the intent
            "payload_hash": payload_hash,
            "fingerprint": fingerprint,
            "created_at": datetime.utcnow().isoformat(),
            "decided_at": None,
            "decided_by": None,
            "decision_reason": "",
            "original_action_intent": action_intent # Store the full intent for auditing
        }
        store["requests"].append(request)
        self._save_store(store)

        from .logic import event_bus
        event_bus.emit_event("APPROVAL_REQUESTED", trace_id, agent_id=agent_id, scenario="preflight", metadata={
            "request_id": request["request_id"],
            "action": action,
            "target": action, # Target is the action itself for action_intent
            "status": "pending"
        })
        return request

    def list_requests(self, status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        store = self._load_store()
        items = list(reversed(store["requests"]))
        if status:
            items = [r for r in items if str(r.get("status", "")).lower() == status.lower()]
        return items[:max(1, limit)]

    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        store = self._load_store()
        for request in reversed(store["requests"]):
            if request.get("request_id") == request_id:
                return request
        return None

    def decide_request(
        self,
        request_id: str,
        decision: str,
        decided_by: str = "gatekeeper",
        reason: str = "",
        trace_id: str = "N/A"
    ) -> Dict[str, Any]:
        store = self._load_store()
        normalized = decision.strip().lower()
        status = "approved" if normalized in {"approve", "approved"} else "rejected"
        target_request = None
        for idx, request in enumerate(store["requests"]):
            if request.get("request_id") == request_id:
                request_metadata = request.get("metadata", {}) or {}
                if (
                    status == "approved"
                    and str(request_metadata.get("severity", "")).upper() == "HIGH_DELAY"
                    and not str(reason or "").strip()
                ):
                    raise PreflightApprovalError(
                        "approval_justification_required",
                        {
                            "request_id": request_id,
                            "severity": "HIGH_DELAY",
                            "reason": "Approval justification is required for HIGH_DELAY requests.",
                        },
                    )
                request["status"] = status
                request["decided_at"] = datetime.utcnow().isoformat()
                request["decided_by"] = decided_by
                request["decision_reason"] = str(reason or "").strip()
                store["requests"][idx] = request
                target_request = request
                break

        if target_request is None:
            raise PreflightApprovalError("approval_request_not_found", {"request_id": request_id})

        self._save_store(store)

        from .logic import event_bus
        event_trace_id = target_request.get("trace_id") or trace_id or "N/A"
        event_bus.emit_event("APPROVAL_DECIDED", event_trace_id, agent_id=decided_by, scenario="preflight", metadata={
            "request_id": target_request.get("request_id"),
            "action": target_request.get("action"),
            "target": target_request.get("target"),
            "decision": status,
            "reason": reason
        })

        if status == "approved":
            from .execution_dispatch import enqueue_execution
            enqueue_execution(
                request_id=target_request.get("request_id"),
                source="approval_server",
            )
        return target_request

    def ensure_approved(
        self,
        action: str,
        parameters: Any, # Now directly take parameters as they would be from action_intent
        agent_id: str = "SYSTEM",
        trace_id: str = "N/A",
    ) -> Dict[str, Any]:
        store = self._load_store()
        
        current_payload_hash = self._payload_hash(parameters)
        
        # Find the latest approved request for this trace_id (if available) or by matching action/agent_id
        latest_match = None
        for request in reversed(store["requests"]):
            # For action_intent, 'target' is the 'action' itself
            if request.get("action") == action and request.get("agent_id") == agent_id:
                if trace_id != "N/A" and request.get("trace_id") == trace_id:
                    latest_match = request
                    break
                elif trace_id == "N/A": # If no trace_id, match by action and agent_id
                    latest_match = request
                    break
        
        from .logic import event_bus

        if latest_match and latest_match.get("status") == "approved":
            approved_intent = latest_match.get("original_action_intent", {})
            approved_payload_hash = self._payload_hash(approved_intent.get("parameters", {}))
            
            if current_payload_hash == approved_payload_hash:
                event_bus.emit_event("ACTION_APPROVED", trace_id, agent_id=agent_id, scenario="preflight", metadata={
                    "request_id": latest_match.get("request_id"),
                    "action": action,
                    "target": action, # Target is the action itself for action_intent
                })
                return latest_match
            else:
                event_bus.emit_event("ACTION_BLOCKED", trace_id, agent_id=agent_id, scenario="preflight", metadata={
                    "request_id": latest_match.get("request_id"),
                    "action": action,
                    "target": action,
                    "status": "payload_mismatch",
                    "reason": "Executing payload hash does not match approved intent hash."
                })
                raise PreflightApprovalError("executing_payload_mismatch", {
                    "request_id": latest_match.get("request_id"),
                    "status": "payload_mismatch",
                    "action": action,
                    "target": action,
                    "approved_hash": approved_payload_hash,
                    "executing_hash": current_payload_hash
                })

        if latest_match and latest_match.get("status") == "rejected":
            event_bus.emit_event("ACTION_BLOCKED", trace_id, agent_id=agent_id, scenario="preflight", metadata={
                "request_id": latest_match.get("request_id"),
                "action": action,
                "target": action,
                "status": "rejected"
            })
            raise PreflightApprovalError("external_action_rejected", {
                "request_id": latest_match.get("request_id"),
                "status": "rejected",
                "action": action,
                "target": action
            })

        # If no approved or rejected request, or if pending, create a new request if needed
        # Note: create_or_get_request now expects an action_intent dict.
        # We need to construct a basic action_intent to create a new approval request.
        # This will be handled by the operator calling this method, passing a full action_intent.
        # For now, let's assume the calling context provides a complete action_intent.
        # This part of `ensure_approved` needs to be carefully integrated with how operators call it.

        # For the purpose of ensure_approved, if no approved or rejected intent is found,
        # it means the action requires approval.
        # We need to create a placeholder action_intent to request approval for.
        placeholder_action_intent = {
            "action": action,
            "agent_id": agent_id,
            "parameters": parameters,
            "trace_id": trace_id,
            "requires_approval": True,
            "status": "pending",
            "summary": "Auto-generated approval request for external action.",
            "metadata": {"auto_generated": True}
        }
        
        request = self.create_or_get_request(action_intent=placeholder_action_intent)

        event_bus.emit_event("ACTION_BLOCKED", trace_id, agent_id=agent_id, scenario="preflight", metadata={
            "request_id": request.get("request_id"),
            "action": action,
            "target": action,
            "status": "pending"
        })
        raise PreflightApprovalError("external_action_requires_approval", {
            "request_id": request.get("request_id"),
            "status": "pending",
            "action": action,
            "target": action
        })

    async def execute_task(self, request_id: str) -> Dict[str, Any]:
        """Execute a task that has already been approved."""
        request = self.get_request(request_id)
        if not request:
            raise PreflightApprovalError("task_not_found", {"request_id": request_id})
        
        if request.get("status") != "approved":
            raise PreflightApprovalError("task_not_approved", {"request_id": request_id, "status": request.get("status")})

        action = request["action"]
        agent_id = request["agent_id"]
        trace_id = request["trace_id"]
        action_intent = request["original_action_intent"]
        
        # Execute based on action type
        try:
            if action.startswith("gmail_"):
                from .google_operator import GmailOperator
                op = GmailOperator(agent_id=agent_id)
                result = await op.execute_intent(action_intent)
            elif action.startswith("calendar_"):
                from .google_operator import CalendarOperator
                op = CalendarOperator(agent_id=agent_id)
                result = await op.execute_intent(action_intent)
            elif action.startswith("construction_"):
                result = await self.execute_construction_intent(action_intent)
            elif action == "audit_log":
                from .operators.construction_op import ConstructionOperator
                executor_task = {
                    "trace_id": trace_id,
                    "tool_calls": [{
                        "tool": "audit_log",
                        "arguments": action_intent["parameters"]
                    }]
                }
                result = ConstructionOperator.handle_tool_call(executor_task)
            elif action == "operator_bundle":
                from .logic.external_gateway import ExternalGateway
                gateway = ExternalGateway(approval_engine=self)
                result = gateway.validate_and_execute(action_intent, request_id)
            else:
                raise PreflightApprovalError("unsupported_task_action", {"action": action})

            # Mark as executed in the store after successful execution
            store = self._load_store()
            for idx, req in enumerate(store["requests"]):
                if req.get("request_id") == request_id:
                    req["status"] = "executed"
                    req["executed_at"] = datetime.utcnow().isoformat()
                    store["requests"][idx] = req
                    break
            self._save_store(store)
            
            return result

        except Exception as e:
            from .logic import event_bus
            event_bus.emit_event("TASK_EXECUTION_FAILED", trace_id, agent_id=agent_id, scenario="preflight", metadata={
                "request_id": request_id,
                "error": str(e)
            })
            raise e

    async def execute_construction_intent(self, action_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an approved construction proposal intent."""
        parameters = action_intent["parameters"]
        scenario_type = parameters["scenario_type"]
        user_input = parameters["user_input"]
        decision_data = parameters["decision"]
        risk_score = parameters["risk_score"]
        trace_id = parameters["trace_id"]
        
        decision_text = str(decision_data.get("decision", "ESCALATE")).upper()
        status = "approved" if decision_text == "APPROVE" else "rejected"
        if decision_text == "ESCALATE":
            status = "escalated"

        impact = decision_data.get("impact", {"cost": 0, "days": 0, "risk_delta": 0})
        
        base_type = scenario_type.replace("construction_", "")
        
        # Build the executor task payload based on the decision
        tool_calls = []
        if decision_text == "APPROVE":
            tool_calls.append({
                "tool": "update_entity",
                "arguments": {
                    "type": base_type,
                    "risk_score": risk_score,
                    "justification": decision_data.get("justification", ""),
                    "data": {
                        "cost": impact.get("cost", 0),
                        "days": impact.get("days", 0),
                        "status": status,
                        "reason": user_input,
                        "risk_delta": impact.get("risk_delta", 0)
                    }
                }
            })
        else: # Handle REJECT or ESCALATE
            tool_calls.append({
                "tool": "audit_log",
                "arguments": {
                    "step": f"{base_type.upper()}_DECISION_LOG",
                    "agent": "ARIA",
                    "input": f"Decision: {decision_text}, Justification: {decision_data.get('justification', '')}",
                    "output": f"State not mutated for {base_type} due to {decision_text}."
                }
            })

        # Add any file_write calls from the implementation plan
        impl_plan = parameters.get("implementation_plan", {})
        if "tool_calls" in impl_plan and isinstance(impl_plan["tool_calls"], list):
            for call in impl_plan["tool_calls"]:
                if call.get("tool") == "file_write":
                    tool_calls.append(call)

        executor_task = {
            "trace_id": trace_id,
            "tool_calls": tool_calls
        }

        from .operators.construction_op import ConstructionOperator
        raw_result = ConstructionOperator.handle_tool_call(executor_task)
        
        from .logic import event_bus
        event_bus.emit_event("ACTION_EXECUTED", trace_id, agent_id="aria", scenario="preflight", metadata={
            "action": f"construction_{scenario_type}",
            "target": scenario_type,
            "status": status,
            "impact": impact
        })
        
        return raw_result

    def create_or_get_draft(
        self,
        action: str,
        target: str,
        payload: Any,
        agent_id: str = "SYSTEM",
        trace_id: str = "N/A",
        summary: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        store = self._load_draft_store()
        payload_hash = self._payload_hash(payload)
        fingerprint = self._fingerprint(agent_id, action, target, payload_hash)

        for draft in reversed(store["drafts"]):
            if draft.get("fingerprint") == fingerprint:
                return draft

        payload_snapshot = self._payload_snapshot(payload)
        draft = {
            "draft_id": f"DRF-{uuid.uuid4().hex[:12].upper()}",
            "action": action,
            "target": target,
            "agent_id": agent_id,
            "trace_id": trace_id,
            "summary": summary,
            "metadata": metadata or {},
            "payload": payload_snapshot,
            "payload_hash": payload_hash,
            "fingerprint": fingerprint,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        store["drafts"].append(draft)
        self._save_draft_store(store)
        return draft

    def list_drafts(self, action: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        store = self._load_draft_store()
        items = list(reversed(store["drafts"]))
        if action:
            items = [d for d in items if str(d.get("action", "")).lower() == action.lower()]
        return items[:max(1, limit)]

    def get_draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        store = self._load_draft_store()
        for draft in reversed(store["drafts"]):
            if draft.get("draft_id") == draft_id:
                return draft
        return None

    def update_draft_summary(self, draft_id: str, summary: str) -> Dict[str, Any]:
        store = self._load_draft_store()
        target_draft = None
        for idx, draft in enumerate(store["drafts"]):
            if draft.get("draft_id") == draft_id:
                draft["summary"] = summary
                draft["updated_at"] = datetime.utcnow().isoformat()
                store["drafts"][idx] = draft
                target_draft = draft
                break
        if target_draft is None:
            raise PreflightApprovalError("preflight_draft_not_found", {"draft_id": draft_id})
        self._save_draft_store(store)
        return target_draft

# Static compatibility wrappers
DEFAULT_ENGINE = PreflightApprovalEngine()

def create_or_get_request(action_intent: Dict[str, Any]) -> Dict[str, Any]:
    return DEFAULT_ENGINE.create_or_get_request(action_intent)

def list_requests(status: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    return DEFAULT_ENGINE.list_requests(status, limit)

def get_request(request_id: str) -> Optional[Dict[str, Any]]:
    return DEFAULT_ENGINE.get_request(request_id)

def decide_request(request_id: str, decision: str, decided_by: str = "gatekeeper", reason: str = "", trace_id: str = "N/A") -> Dict[str, Any]:
    return DEFAULT_ENGINE.decide_request(request_id, decision, decided_by, reason, trace_id)

async def execute_task(request_id: str) -> Dict[str, Any]:
    return await DEFAULT_ENGINE.execute_task(request_id)

def ensure_approved(action: str, parameters: Any, agent_id: str = "SYSTEM", trace_id: str = "N/A") -> Dict[str, Any]:
    return DEFAULT_ENGINE.ensure_approved(action, parameters, agent_id, trace_id)

def create_or_get_draft(action: str, target: str, payload: Any, agent_id: str = "SYSTEM", trace_id: str = "N/A", summary: str = "", metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return DEFAULT_ENGINE.create_or_get_draft(action, target, payload, agent_id, trace_id, summary, metadata)

def list_drafts(action: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    return DEFAULT_ENGINE.list_drafts(action, limit)

def get_draft(draft_id: str) -> Optional[Dict[str, Any]]:
    return DEFAULT_ENGINE.get_draft(draft_id)

def update_draft_summary(draft_id: str, summary: str) -> Dict[str, Any]:
    return DEFAULT_ENGINE.update_draft_summary(draft_id, summary)


class ToolFirewall:
    """
    The Elite Enforcement Layer.
    Intercepts every tool request and validates it against the Mission Lease,
    Domain boundaries, and Payload integrity.
    """

    @staticmethod
    def audit_event(agent_id: str, tool: str, target: str, result: str, 
                    reason: Optional[str] = None, lease_id: Optional[str] = None):
        """Permanent record of every firewall decision."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": agent_id,
            "lease_id": lease_id,
            "tool": tool,
            "target": target,
            "result": result,
            "reason": reason
        }
        with open(FIREWALL_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    @classmethod
    def validate(cls, agent_id: str, agent_domain: str, lease: Optional[MissionLease], 
                 tool: str, target: str, action: str, payload: bytes = b"", 
                 current_execution_id: str = ""):
        """
        The Zero-Trust Checkpoint.
        """
        details = {
            "agent_id": agent_id,
            "tool": tool,
            "target": target,
            "lease_id": lease.lease_id if lease else None
        }

        # 1. Lease Presence Check
        if not lease:
            cls.audit_event(agent_id, tool, target, "DENIED", "no_active_lease")
            raise FirewallViolation("Access Denied: No active mission lease.", details)

        # 2. Execution Context Check
        if lease.execution_id != current_execution_id:
            cls.audit_event(agent_id, tool, target, "DENIED", "execution_id_mismatch", lease.lease_id)
            raise FirewallViolation("Access Denied: Lease is not valid for this execution context.", details)

        # 3. Domain Isolation Check (G9)
        # Executive agents (v2.0 CEO) have cross-domain coordination authority
        if agent_domain.lower() != "executive" and agent_domain.lower() != lease.domain.lower():
            cls.audit_event(agent_id, tool, target, "DENIED", "domain_violation", lease.lease_id)
            raise FirewallViolation(f"Access Denied: Agent domain {agent_domain} does not match mission domain {lease.domain}.", details)

        # 4. Path Canonicalization (Anti-Traversal/Symlink)
        # Note: For shell tools, 'target' might not be a path, so we handle accordingly
        real_target = target
        if tool.startswith("file_") or tool == "list_files":
            try:
                # Resolve the path to its physical location
                path_obj = Path(target).resolve()
                real_target = str(path_obj)
                
                # Enforce workspace boundary (cannot escape PROJECT root)
                root = Path(".").resolve()
                if not str(path_obj).startswith(str(root)):
                    cls.audit_event(agent_id, tool, target, "DENIED", "path_escape", lease.lease_id)
                    raise FirewallViolation("Access Denied: Target path escapes workspace boundary.", details)
            except Exception as e:
                cls.audit_event(agent_id, tool, target, "DENIED", f"path_resolution_error: {str(e)}", lease.lease_id)
                raise FirewallViolation(f"Access Denied: Could not resolve target path: {str(e)}", details)

        # 5. Intent Locking & Content Fingerprinting
        if not lease.check_permission(tool, target, action, payload):
            cls.audit_event(agent_id, tool, target, "DENIED", "intent_hash_mismatch", lease.lease_id)
            raise FirewallViolation("Access Denied: Intent hash mismatch. Target or Payload not approved in proposal.", details)

        # 6. Audit Success
        cls.audit_event(agent_id, tool, target, "ALLOWED", lease_id=lease.lease_id)
        return True
