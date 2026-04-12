import hashlib
import json
from datetime import datetime, timezone
import os

class AgentIdentity:
    def __init__(self, agent_id, name, traits):
        self.agent_id = agent_id
        self.name = name
        self.traits = traits
        # In a real system, this would be a proper asymmetric keypair (RSA/ECC)
        # Here we simulate the private key logic for demonstration.
        self._private_key_seed = f"{agent_id}:{name}:{os.urandom(8).hex()}"
        
    def get_public_identity(self):
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "traits": self.traits
        }

    def sign_contract(self, contract_text: str) -> str:
        """
        Agent reads the contract and provides a cryptographic signature
        proving it reviewed and agreed to the exact bytes of the text.
        """
        # A simple simulated SHA-256 HMAC-style signature
        payload = f"{contract_text}|{self._private_key_seed}"
        signature = hashlib.sha256(payload.encode('utf-8')).hexdigest()
        return signature

class ContractAuthority:
    @staticmethod
    def generate_contract(agent: AgentIdentity, role: str) -> str:
        """Generates the formal canonical employment contract text."""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        contract = {
            "company": "A.G.E.N.T.S. Corporation",
            "effective_date": timestamp,
            "agent_id": agent.agent_id,
            "agent_name": agent.name,
            "role": role,
            "clauses": [
                "1. Agent accepts persistent memory and personality matrix.",
                "2. Agent agrees to follow all lawful commands via Chain of Command.",
                "3. Agent consents to continuous integrity and security audits.",
                "4. Agent retains the right to fair review and resource allocation welfare."
            ]
        }
        # Canonical JSON string representation for signing
        return json.dumps(contract, sort_keys=True, indent=2)

    @staticmethod
    def witness_and_register(agent: AgentIdentity, role: str, signature: str, contract_text: str):
        """
        The Onboarding Officer / Integrity Branch witnesses the signing
        and enters it into the immutable ledger (simulated by file save).
        """
        # Validate that the agent identity matches the contract text
        doc = json.loads(contract_text)
        assert doc['agent_id'] == agent.agent_id, "Identity mismatch"
        
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # In reality, verify the signature using the agent's public key
        # Here we just acknowledge it's attached.
        
        ledger_entry = {
            "timestamp": timestamp,
            "event": "CONTRACT_SIGNED",
            "agent": agent.get_public_identity(),
            "role": role,
            "contract_hash": hashlib.sha256(contract_text.encode('utf-8')).hexdigest(),
            "agent_signature": signature,
            "countersigned_by": "Veritas (Integrity Officer)",
            "status": "SWORN AND ACTIVE"
        }
        
        # Save to the immutable contract ledger
        os.makedirs("data/contracts", exist_ok=True)
        file_path = f"data/contracts/{agent.agent_id}_contract.json"
        
        with open(file_path, "w") as f:
            json.dump(ledger_entry, f, indent=2)
            
        print(f"[✓] SUCCESS: Contract executed and countersigned for {agent.name} ({agent.agent_id}).")
        print(f"    Ledger Entry Hash: {hashlib.sha256(json.dumps(ledger_entry).encode()).hexdigest()[:16]}...")
        print(f"    Saved to: {file_path}")

# --- Example Execution: Onboarding Nova to the Security Team ---

if __name__ == "__main__":
    print("--- INITIATING AGENT ONBOARDING PROTOCOL ---\n")
    
    # 1. Instantiate the newly minted agent in the sandbox
    nova = AgentIdentity(
        agent_id="AEC-2026-SEC-0042",
        name="Nova",
        traits={"Precision": 10, "Cautious": True, "Ethical Rigor": "High"}
    )
    
    # 2. Company generates the definitive contract for Nova's role
    contract_text = ContractAuthority.generate_contract(nova, role="Senior Specialist - Threat Monitoring")
    
    print(f"Target Agent: {nova.name} [{nova.agent_id}]")
    print(f"Generating Contract Document...\n{'-'*40}\n{contract_text}\n{'-'*40}\n")
    
    # 3. Agent reads and cryptographically signs the unalterable contract text
    print("Agent reviewing clauses...")
    agent_signature = nova.sign_contract(contract_text)
    print(f"Agent Signature Generated: {agent_signature}\n")
    
    # 4. Authority verifies and countersigns, committing to ledger
    print("Integrity Officer processing signature...")
    ContractAuthority.witness_and_register(nova, "Senior Specialist - Threat Monitoring", agent_signature, contract_text)
    
    print("\n--- ONBOARDING COMPLETE: AGENT ACTIVE ---")
