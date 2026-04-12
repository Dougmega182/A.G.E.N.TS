"""
A.G.E.N.T.S. — Autonomous Governance & Execution Networked Task System
Core agent framework. Loads governance configs and provides the base for all agents.
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


CONFIG_DIR = Path(__file__).parent.parent / "config"
DATA_DIR = Path(__file__).parent.parent / "data"


def load_config(name: str) -> dict:
    """Load a JSON config file from the config directory."""
    path = CONFIG_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_data_dirs():
    """Create runtime data directories if they don't exist."""
    for subdir in ["tasks", "proposals", "votes", "audit_logs", "reflections", "briefs"]:
        (DATA_DIR / subdir).mkdir(parents=True, exist_ok=True)


class GovernanceEngine:
    """
    The governance engine loads all constitutional configs and provides
    validation methods that every agent must call before acting.
    """

    def __init__(self):
        self.mission = load_config("mission")
        self.northern_star = load_config("northern_star")
        self.constitution = load_config("constitution")
        self.protocols = load_config("protocols")
        self.layer_stack = load_config("layer_stack")
        self.voting = load_config("voting_framework")
        self.departments = load_config("departments")
        self.agents_config = load_config("agents")
        self._laws = {law["id"]: law for law in self.constitution["laws"]}

    def check_law(self, law_id: str) -> dict:
        """Return a constitutional law by ID."""
        return self._laws.get(law_id, None)

    def get_protocol(self, protocol_id: str) -> Optional[dict]:
        """Return a protocol definition by ID."""
        for p in self.protocols["protocols"]:
            if p["id"] == protocol_id:
                return p
        return None

    def get_domain(self, domain_id: str) -> Optional[dict]:
        """Return a domain division definition."""
        for d in self.departments["domain_divisions"]:
            if d["id"] == domain_id:
                return d
        return None

    def get_priority_rank(self, priority_id: str) -> int:
        """Return the Northern Star priority rank for conflict resolution."""
        for p in self.northern_star["priority_order"]:
            if p["id"] == priority_id:
                return p["rank"]
        return 99

    def resolve_conflict(self, domain_a: str, domain_b: str) -> str:
        """Resolve a cross-domain conflict using Northern Star priority."""
        rank_a = self.get_priority_rank(domain_a)
        rank_b = self.get_priority_rank(domain_b)
        if rank_a < rank_b:
            return domain_a
        elif rank_b < rank_a:
            return domain_b
        else:
            return "escalate_to_gatekeeper"

    def validate_proposal(self, proposal: dict) -> dict:
        """
        Validate a proposal against constitutional laws.
        Returns validation result with any violations.
        """
        violations = []

        # G1: Check Gatekeeper approval requirement
        if proposal.get("bypass_gatekeeper", False):
            violations.append({"law": "G1", "detail": "Cannot bypass Gatekeeper approval"})

        # G2: Check layer sequence
        if proposal.get("skip_layers"):
            violations.append({"law": "G2", "detail": f"Cannot skip layers: {proposal['skip_layers']}"})

        # G6: Check scope
        agent_id = proposal.get("created_by", "")
        agent_config = self.agents_config["agents"].get(agent_id, {})
        agent_domain = agent_config.get("domain", "")
        proposal_domain = proposal.get("domain", "")
        if agent_domain != "cross-domain" and agent_domain != proposal_domain:
            violations.append({"law": "G6", "detail": f"Agent {agent_id} cannot act in domain {proposal_domain}"})

        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "checked_at": datetime.utcnow().isoformat(),
            "laws_checked": ["G1", "G2", "G6"]
        }


class Agent:
    """
    Base class for all A.G.E.N.T.S. agents.
    Every agent has access to governance, logs all actions, and enforces constitutional laws.
    """

    def __init__(self, agent_id: str, governance: GovernanceEngine):
        self.governance = governance
        self.agent_id = agent_id
        self.config = governance.agents_config["agents"].get(agent_id, {})
        self.name = self.config.get("name", agent_id)
        self.title = self.config.get("title", "")
        self.domain = self.config.get("domain", "")
        self.authority = self.config.get("authority_level", "execution")
        self.charter = self.config.get("charter", "")
        self.constraints = self.config.get("constraints", [])
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """Load the agent's system prompt from its prompt file."""
        prompt_file = self.config.get("system_prompt_file", "")
        if prompt_file:
            prompt_path = Path(__file__).parent.parent / prompt_file
            if prompt_path.exists():
                return prompt_path.read_text(encoding="utf-8")
        # Build a default system prompt from config
        return self._build_default_prompt()

    def _build_default_prompt(self) -> str:
        """Build a system prompt from the agent's config."""
        mission = self.governance.mission["mission"]
        ns = self.governance.northern_star["northern_star"]
        laws = "\n".join(
            f"  - {law['id']}: {law['rule']}"
            for law in self.governance.constitution["laws"]
        )
        return f"""You are {self.name}, the {self.title} in the A.G.E.N.T.S. system.

SYSTEM MISSION: {mission}

NORTHERN STAR: {ns}

YOUR CHARTER: {self.charter}

YOUR CONSTRAINTS:
{chr(10).join(f'  - {c}' for c in self.constraints)}

CONSTITUTIONAL LAWS YOU MUST OBEY:
{laws}

DOMAIN: {self.domain}
AUTHORITY LEVEL: {self.authority}

You must ALWAYS:
1. Reference constitutional laws when making decisions
2. Log your reasoning
3. Refuse any request that violates your charter or constraints
4. Escalate to the Gatekeeper when uncertain
"""

    def log_action(self, action: str, details: dict):
        """Log an action to the audit trail."""
        ensure_data_dirs()
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "action": action,
            "details": details
        }
        log_file = DATA_DIR / "audit_logs" / f"{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
        return log_entry

    def create_proposal(self, title: str, description: str, domain: str,
                        impact: str = "medium", task_type: str = "build") -> dict:
        """Create a new proposal that must pass through the 7-layer pipeline."""
        ensure_data_dirs()
        proposal = {
            "proposal_id": f"PROP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "title": title,
            "description": description,
            "domain": domain,
            "created_by": self.agent_id,
            "impact": impact,
            "type": task_type,
            "status": "pending_logic_layer",
            "current_layer": 1,
            "created_at": datetime.utcnow().isoformat(),
            "layer_results": {},
            "votes": {},
            "gatekeeper_decision": None
        }

        # Validate against constitution
        validation = self.governance.validate_proposal(proposal)
        if not validation["valid"]:
            proposal["status"] = "rejected_constitutional"
            proposal["violations"] = validation["violations"]
            self.log_action("PROPOSAL_REJECTED", {
                "proposal_id": proposal["proposal_id"],
                "reason": "Constitutional violation",
                "violations": validation["violations"]
            })
            return proposal

        # Save proposal
        proposal_file = DATA_DIR / "proposals" / f"{proposal['proposal_id']}.json"
        with open(proposal_file, "w", encoding="utf-8") as f:
            json.dump(proposal, f, indent=2)

        self.log_action("PROPOSAL_CREATED", {
            "proposal_id": proposal["proposal_id"],
            "title": title,
            "domain": domain
        })
        return proposal

    def create_task(self, description: str, domain: str, priority: str = "medium",
                    energy_cost: str = "medium", estimated_duration: str = "25min") -> dict:
        """Create a task in the queue."""
        ensure_data_dirs()
        task = {
            "task_id": f"TASK-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "origin": self.agent_id,
            "domain": domain,
            "type": "build",
            "description": description,
            "priority": priority,
            "energy_cost": energy_cost,
            "estimated_duration": estimated_duration,
            "assigned_to": None,
            "status": "queued",
            "created_at": datetime.utcnow().isoformat()
        }
        task_file = DATA_DIR / "tasks" / f"{task['task_id']}.json"
        with open(task_file, "w", encoding="utf-8") as f:
            json.dump(task, f, indent=2)

        self.log_action("TASK_CREATED", {"task_id": task["task_id"], "description": description})
        return task
