import pytest
from datetime import datetime
from agents.leases import MissionLease, generate_intent_hash
from agents.firewall import ToolFirewall, FirewallViolation

def test_firewall_unauthorized_target():
    """
    Ensures that if a lease allows 'hello.txt', it rejects 'evil.txt'.
    """
    payload = b"hello world"
    h = generate_intent_hash("file_write", "data/hello.txt", "write", payload)
    
    lease = MissionLease(
        lease_id="L1",
        execution_id="E1",
        agent_id="A1",
        domain="OPS",
        capabilities={"data/hello.txt": h},
        expiry=datetime(2099, 1, 1)
    )
    
    # 1. Valid call to allowed target
    assert ToolFirewall.validate(
        agent_id="A1",
        agent_domain="OPS",
        lease=lease,
        tool="file_write",
        target="data/hello.txt",
        action="write",
        payload=payload,
        current_execution_id="E1"
    ) is True
    
    # 2. Denied call to unauthorized target (same tool, different file)
    with pytest.raises(FirewallViolation) as excinfo:
        ToolFirewall.validate(
            agent_id="A1",
            agent_domain="OPS",
            lease=lease,
            tool="file_write",
            target="data/evil.txt",
            action="write",
            payload=payload,
            current_execution_id="E1"
        )
    assert "intent_hash_mismatch" in excinfo.value.reason or "mismatch" in excinfo.value.reason

def test_firewall_content_fingerprint():
    """
    Ensures that if the content changes, the hash mismatch triggers a denial.
    """
    approved_payload = b"safe content"
    evil_payload = b"malicious content"
    h = generate_intent_hash("file_write", "data/hello.txt", "write", approved_payload)
    
    lease = MissionLease(
        lease_id="L1",
        execution_id="E1",
        agent_id="A1",
        domain="OPS",
        capabilities={"data/hello.txt": h},
        expiry=datetime(2099, 1, 1)
    )
    
    # Try to write DIFFERENT content to same target
    with pytest.raises(FirewallViolation):
        ToolFirewall.validate(
            agent_id="A1",
            agent_domain="OPS",
            lease=lease,
            tool="file_write",
            target="data/hello.txt",
            action="write",
            payload=evil_payload,
            current_execution_id="E1"
        )

def test_firewall_domain_isolation():
    """
    Ensures that an agent cannot use a lease meant for a different domain.
    """
    lease = MissionLease(
        lease_id="L1",
        execution_id="E1",
        agent_id="A1",
        domain="FINANCE",
        capabilities={"target": "hash"},
        expiry=datetime(2099, 1, 1)
    )
    
    # OPS agent trying to use a FINANCE lease
    with pytest.raises(FirewallViolation) as excinfo:
        ToolFirewall.validate(
            agent_id="A1",
            agent_domain="OPS",
            lease=lease,
            tool="tool",
            target="target",
            action="action",
            current_execution_id="E1"
        )
    assert "domain" in excinfo.value.reason
