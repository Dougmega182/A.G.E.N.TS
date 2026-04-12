"""
A.G.E.N.T.S. — Boardroom voting system.
Implements weighted majority voting with audit veto.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .core import GovernanceEngine, Agent, DATA_DIR, ensure_data_dirs
from .llm import LLMProvider


class BoardroomVote:
    """A single voting session on a proposal."""

    def __init__(self, proposal: dict, governance: GovernanceEngine):
        self.proposal = proposal
        self.governance = governance
        self.voting_config = governance.voting["voting_framework"]
        self.votes = {}
        self.audit_veto = False

    def cast_vote(self, agent_id: str, vote: str, reason: str):
        """Cast a vote. vote must be 'YES' or 'NO'."""
        weight = self.voting_config["vote_weights"].get(agent_id, 1.0)
        self.votes[agent_id] = {
            "vote": vote.upper(),
            "reason": reason,
            "weight": weight,
            "timestamp": datetime.utcnow().isoformat()
        }
        # Check for audit veto
        if agent_id == "audit_agent" and vote.upper() == "NO":
            self.audit_veto = True

    def tally(self) -> dict:
        """Count votes and determine the result."""
        yes_weight = sum(v["weight"] for v in self.votes.values() if v["vote"] == "YES")
        no_weight = sum(v["weight"] for v in self.votes.values() if v["vote"] == "NO")
        total_votes = len(self.votes)

        if self.audit_veto:
            decision = "AUDIT_VETO"
            escalation = "gatekeeper_review"
        elif yes_weight > no_weight:
            decision = "APPROVED"
            escalation = None
        elif no_weight > yes_weight:
            decision = "REJECTED"
            escalation = "return_to_planning"
        else:
            decision = "TIE"
            escalation = "ceo_tiebreak"

        result = {
            "proposal_id": self.proposal["proposal_id"],
            "votes": self.votes,
            "yes_weight": yes_weight,
            "no_weight": no_weight,
            "total_votes": total_votes,
            "decision": decision,
            "escalation": escalation,
            "audit_veto_used": self.audit_veto,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Save vote record
        ensure_data_dirs()
        vote_file = DATA_DIR / "votes" / f"{self.proposal['proposal_id']}.json"
        with open(vote_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        return result


class Boardroom:
    """
    The Boardroom orchestrates agent debate and voting on proposals.
    Uses LLM to generate agent opinions based on their system prompts.
    """

    def __init__(self, governance: GovernanceEngine, llm: LLMProvider):
        self.governance = governance
        self.llm = llm
        self.board_agents = ["strategy_agent", "risk_agent", "audit_agent",
                             "ops_agent", "tech_agent", "executive_function_agent"]

    def debate_proposal(self, proposal: dict) -> dict:
        """
        Run a full boardroom debate on a proposal.
        Each board agent evaluates and votes.
        """
        vote_session = BoardroomVote(proposal, self.governance)

        for agent_id in self.board_agents:
            agent = Agent(agent_id, self.governance)

            prompt = f"""You are evaluating a proposal in the A.G.E.N.T.S. boardroom.

PROPOSAL:
  Title: {proposal['title']}
  Description: {proposal['description']}
  Domain: {proposal['domain']}
  Impact: {proposal['impact']}
  Created by: {proposal['created_by']}

Based on your role as {agent.name} ({agent.title}), evaluate this proposal.

Consider:
- Does it align with the Northern Star directive?
- What are the risks?
- Is it feasible?
- Does it violate any constitutional laws?

Respond with JSON:
{{
  "vote": "YES" or "NO",
  "reason": "Your reasoning in 1-2 sentences",
  "concerns": ["any specific concerns"],
  "conditions": ["any conditions for approval"]
}}"""

            try:
                response = self.llm.chat_json(agent.system_prompt, prompt)
                vote_session.cast_vote(
                    agent_id,
                    response.get("vote", "NO"),
                    response.get("reason", "No reason provided")
                )
            except Exception as e:
                # If LLM fails, agent abstains (which counts as NO per constitution)
                vote_session.cast_vote(agent_id, "NO", f"Agent error: {str(e)}")

        result = vote_session.tally()
        return result

    def format_result(self, result: dict) -> str:
        """Format a vote result for display."""
        lines = [
            f"\n{'='*60}",
            f"  BOARDROOM VOTE: {result['proposal_id']}",
            f"{'='*60}\n",
        ]
        for agent_id, vote in result["votes"].items():
            symbol = "✓" if vote["vote"] == "YES" else "✗"
            weight_str = f" (×{vote['weight']})" if vote["weight"] != 1.0 else ""
            lines.append(f"  {symbol} {agent_id}{weight_str}: {vote['vote']}")
            lines.append(f"    → {vote['reason']}\n")

        lines.append(f"{'─'*60}")
        lines.append(f"  YES: {result['yes_weight']:.1f}  |  NO: {result['no_weight']:.1f}")
        lines.append(f"  DECISION: {result['decision']}")
        if result["audit_veto_used"]:
            lines.append(f"  ⚠ AUDIT VETO USED — Escalating to Gatekeeper")
        if result["escalation"]:
            lines.append(f"  ESCALATION: {result['escalation']}")
        lines.append(f"{'='*60}\n")

        return "\n".join(lines)
