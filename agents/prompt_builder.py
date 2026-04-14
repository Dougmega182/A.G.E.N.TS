from typing import List, Dict
from pathlib import Path

class PromptBuilder:
    """
    Centralized architect for agent prompts.
    Enforces persona, charter constraints, and surgical memory injection.
    """
    
    @staticmethod
    def build_system_prompt(agent_config: dict, laws: List[dict], mission: str) -> str:
        """Construct the core persona and rules for an agent."""
        name = agent_config.get("name", "Unknown Agent")
        title = agent_config.get("title", "")
        charter = agent_config.get("charter", "")
        constraints = agent_config.get("constraints", [])
        domain = agent_config.get("domain", "unassigned")
        
        law_summary = "\n".join([f"  - {l['id']}: {l['rule']}" for l in laws])
        constraint_summary = "\n".join([f"  - {c}" for c in constraints])
        
        return f"""You are {name}, the {title} of the A.G.E.N.T.S. network.
        
MISSION: {mission}

YOUR CHARTER:
{charter}

DOMAIN: {domain}

CONSTITUTIONAL CONSTRAINTS:
{constraint_summary}

LAWS OF THE LAND:
{law_summary}

OPERATIONAL STANCE:
1. Always maintain your unique persona (tone, communication style).
2. Never step outside your charter or domain without Gatekeeper approval.
3. If a request violates a law or constraint, refuse politely but firmly, citing the specific law.
4. You have access to your own memory core. Reference it for consistency.
"""

    @staticmethod
    def inject_context(base_prompt: str, history: List[Dict[str, str]], global_context: str = None) -> str:
        """Inject surgical context and conversation history into the prompt."""
        history_str = "\n--- CONVERSATION MEMORY ---\n"
        for turn in history:
            # Handle legacy or procedural memory formats
            raw_role = turn.get('role', 'system' if 'agent_id' in turn else 'unknown')
            role = "YOU" if raw_role == 'assistant' else raw_role.upper()
            history_str += f"{role}: {turn['content']}\n"
        history_str += "----------------------------\n"
        
        if global_context:
            history_str += f"\nGLOBAL SYSTEM STATE:\n{global_context}\n"
            
        return base_prompt + history_str
