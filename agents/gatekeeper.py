import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from .leases import MissionLease

# Setup high-fidelity firewall audit log
LOG_ROOT = Path("Agent logs")
LOG_ROOT.mkdir(parents=True, exist_ok=True)
FIREWALL_LOG = LOG_ROOT / "firewall.jsonl"

class FirewallViolation(Exception):
    def __init__(self, reason: str, details: dict):
        self.reason = reason
        self.details = details
        super().__init__(reason)

class ToolFirewall:
    """
    The Elite Enforcement Layer (Control Layer).
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

        # 3. Domain Isolation Check
        if agent_domain.lower() != "executive" and agent_domain.lower() != lease.domain.lower():
            cls.audit_event(agent_id, tool, target, "DENIED", "domain_violation", lease.lease_id)
            raise FirewallViolation(f"Access Denied: Agent domain {agent_domain} does not match mission domain {lease.domain}.", details)

        # 4. Path Canonicalization
        if tool.startswith("file_") or tool == "list_files":
            try:
                path_obj = Path(target).resolve()
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
