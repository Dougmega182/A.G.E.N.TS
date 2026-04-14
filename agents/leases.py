import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class MissionLease(BaseModel):
    """
    A cryptographic-style lease that grants an agent surgical permissions
    to execute specific tool actions within a single execution context.
    """
    lease_id: str
    execution_id: str
    agent_id: str
    domain: str
    # capabilities maps target_id (e.g. "path/to/file") to the expected intent_hash
    capabilities: Dict[str, str] = Field(default_factory=dict)
    expiry: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expiry

    def check_permission(self, tool: str, target: str, action: str, payload: bytes = b"") -> bool:
        """
        Validates if the current lease covers the specific tool call.
        """
        if self.is_expired():
            return False
            
        intent_hash = generate_intent_hash(tool, target, action, payload)
        # Check if this specific intent was pre-approved
        return self.capabilities.get(target) == intent_hash

def generate_intent_hash(tool: str, target: str, action: str, payload: bytes | str = b"") -> str:
    """
    Generates a unique hash representing a specific 'Intent'.
    Includes the tool, target, action, and a fingerprint of the payload.
    """
    if isinstance(payload, str):
        payload = payload.encode("utf-8")

    # Use a separator to prevent 'collision' attacks (e.g. tool="ab", target="c" vs tool="a", target="bc")
    components = [
        tool.encode(),
        b"|",
        target.encode(),
        b"|",
        action.encode(),
        b"|",
        hashlib.sha256(payload).digest()
    ]
    hasher = hashlib.sha256()
    for part in components:
        hasher.update(part)
    return hasher.hexdigest()

def create_mission_lease(agent_id: str, domain: str, execution_id: str, 
                         approved_intents: List[dict], ttl_hours: int = 1) -> MissionLease:
    """
    Factory to create a lease from approved proposal intents.
    approved_intents: List of {"tool": str, "target": str, "action": str, "payload": bytes}
    """
    lease_id = f"LEASE-{hashlib.md5(f'{execution_id}-{agent_id}'.encode()).hexdigest()[:8]}"
    
    capabilities = {}
    for intent in approved_intents:
        target = intent["target"]
        h = generate_intent_hash(
            intent["tool"], 
            target, 
            intent["action"], 
            intent.get("payload", b"")
        )
        capabilities[target] = h
        
    return MissionLease(
        lease_id=lease_id,
        execution_id=execution_id,
        agent_id=agent_id,
        domain=domain,
        capabilities=capabilities,
        expiry=datetime.utcnow() + timedelta(hours=ttl_hours)
    )
