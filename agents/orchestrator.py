from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_core.messages import (
    SystemMessage, 
    HumanMessage, 
    AIMessage
)
from langchain_google_genai import ChatGoogleGenerativeAI
from .roster import AGENTS
from .prompt_builder import PromptBuilder
from .core import GovernanceEngine
from datetime import datetime
import json
import os
from pathlib import Path
from typing import List, Dict, Generator

# Orchestrator uses Gemini for high-speed routing to avoid local hardware lag
router_llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GOOGLE_API_KEY", "missing"),
    temperature=0
)

ROUTER_PROMPT = """
You are the A.G.E.N.T.S. routing system.
Your job is to read the Gatekeeper's message and 
decide which agent or agents should respond.

Available agents and their roles:
{agent_list}

Rules:
- If the message names an agent directly (e.g. "Owen, analyze..."), route to them.
- If unclear, route to Aria (CEO) as default.
- If message needs multiple agents, list all of them.
- For ADHD/overwhelm signals, always include Eli.
- For any compliance question, always include Marcus.
- Return ONLY a JSON list of agent keys (e.g. ["aria", "owen"]). No explanation.
"""

# Global Telemetry State (Phase 8)
TELEMETRY = {
    "input_tokens": 0,
    "output_tokens": 0,
    "total_cost": 0.0,
    "messages_processed": 0
}

# 2026 Model Pricing (Est.)
PRICING = {
    "claude-3-5-sonnet-20240620": {"in": 0.000003, "out": 0.000015},
    "gemini-2.5-flash": {"in": 0.000000075, "out": 0.0000003},
    "gemini-3.1-flash": {"in": 0.000000075, "out": 0.0000003},
    "default": {"in": 0.0000001, "out": 0.0000005}
}

class Orchestrator:
    
    def __init__(self):
        self.conversation_history = []
        self.session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.data_dir = Path("data")
        self.log_dir = self.data_dir / "audit_logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
    def _build_agent_list(self) -> str:
        lines = []
        for key, agent in AGENTS.items():
            lines.append(
                f"- {key}: {agent['name']} "
                f"({agent['title']})"
            )
        return "\n".join(lines)
    
    def _route_message(self, message: str) -> List[str]:
        """Decide which agents should respond"""
        
        # Fast path: check direct trigger mentions
        message_lower = message.lower()
        direct_mentions = []
        
        for key, agent in AGENTS.items():
            triggers = agent["triggers"]
            if any(t in message_lower for t in triggers):
                if key not in direct_mentions:
                    direct_mentions.append(key)
        
        # If we found direct mentions, use them immediately
        if direct_mentions:
            return direct_mentions
        
        # Otherwise use LLM router for nuanced mapping
        try:
            response = router_llm.invoke([
                SystemMessage(
                    content=ROUTER_PROMPT.format(
                        agent_list=self._build_agent_list()
                    )
                ),
                HumanMessage(content=message)
            ])
            
            # Extract list from string (handles potential LLM markdown/formatting)
            content = response.content.strip()
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
                
            agents = json.loads(content)
            return agents if isinstance(agents, list) else ["aria"]
        except Exception as e:
            print(f"Routing Error: {e}. Defaulting to Aria.")
            return ["aria"]
    
    def _get_agent_response(
        self, 
        agent_key: str, 
        message: str,
        context: List
    ) -> str:
        """Get a response from a specific agent and persist to their specialist memory."""
        
        agent = AGENTS.get(agent_key)
        if not agent:
            return f"Agent {agent_key} not found"
        
        llm = agent["llm"]
        
        # Build messages with conversation context
        messages = [
            SystemMessage(content=agent["profile"])
        ]
        
        # Add limited conversation context (last 6 messages)
        for ctx in context[-6:]:
            messages.append(ctx)
        
        # Add current message
        messages.append(HumanMessage(content=message))
        
        try:
            response = llm.invoke(messages)
            response_text = response.content
            
            # Persist to Specialist's Memory Core (.jsonl)
            self._save_to_agent_memory(agent_key, message, response_text)
            
            return response_text
        except Exception as e:
            return f"[ERROR] {agent['name']} ({agent_key}) failed to respond: {str(e)}"

    def _save_to_agent_memory(self, agent_key: str, user_input: str, assistant_response: str):
        """Perspective: Save interaction to the specialist's individual memory core."""
        agent_name = AGENTS[agent_key]['name']
        memory_path = Path("Individual Contributor Layer") / agent_name / "memory" / "agent_memory.jsonl"
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        
        entries = [
            {"timestamp": datetime.utcnow().isoformat(), "role": "user", "content": user_input},
            {"timestamp": datetime.utcnow().isoformat(), "role": "assistant", "agent_id": AGENTS[agent_key]['id'], "content": assistant_response}
        ]
        
        with open(memory_path, "a", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    def _log_interaction(
        self, 
        message: str, 
        responses: Dict[str, str]
    ):
        """ALRMF compliant interaction logging (Audit Log & Record Management Framework)."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": self.session_id,
            "gatekeeper_message": message,
            "agents_responded": list(responses.keys()),
            "response_summary": {
                k: v[:200] + "..." 
                if len(v) > 200 else v
                for k, v in responses.items()
            }
        }
        
        log_file = self.log_dir / f"{datetime.utcnow().date()}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    
    async def astream_chat(self, message: str) -> Generator[str, None, None]:
        """
        Main multi-agent routing entry point for streaming.
        Yields tokens with agent metadata: 'data: [AGENT_NAME]: token\n\n'
        """
        # 1. Decide which agents respond
        print(f"[ORCHESTRATOR] Routing message: {message[:50]}...")
        TELEMETRY["messages_processed"] += 1
        
        # Approximate input tokens (4 chars/token)
        in_tokens = len(message) // 4 + 500 # +500 for prompt context
        TELEMETRY["input_tokens"] += in_tokens
        
        agent_keys = self._route_message(message)
        print(f"[ORCHESTRATOR] Assigned agents: {agent_keys}")
        
        # Update thread history with user input
        self.conversation_history.append(HumanMessage(content=message))
        
        full_responses = {}
        
        # 2. Sequential Streaming (to keep UI clean)
        for key in agent_keys:
            agent = AGENTS.get(key)
            if not agent:
                continue
            
            agent_name = agent['name'].upper()
            full_responses[key] = ""
            
            # Send initial signal that agent is talking
            yield f"data: [{agent_name}] START\n\n"
            
            # Use PromptBuilder for persona consistency (Elite constraint)
            system_prompt = PromptBuilder.build_system_prompt(
                agent, 
                GovernanceEngine().constitution["laws"],
                GovernanceEngine().mission["mission"]
            )
            # Fetch individual history from specialist's .jsonl
            # Using a simplified history for the orchestrator layer for now
            final_prompt = PromptBuilder.inject_context(system_prompt, []) # History handled by Orchestrator memory
            
            # Build messages with global conversation context
            messages = [SystemMessage(content=final_prompt)]
            for ctx in self.conversation_history[-6:]:
                messages.append(ctx)
            
            # Current turn handled by LLMProvider.astream_chat logic internally, 
            # but we need to pass the context explicitly here for LangChain compatibility.
            # actually, using a more direct approach:
            
            try:
                print(f"[ORCHESTRATOR] Starting stream for {agent_name}...")
                async for chunk in agent["llm"].astream(messages + [HumanMessage(content=message)]):
                    # Token comes from LangChain invoke/stream
                    token_text = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    if token_text:
                        full_responses[key] += token_text
                        yield f"data: [{agent_name}]: {token_text}\n\n"
                        
                # Update output telemetry (approximation for all models)
                out_tokens = len(full_responses[key]) // 4
                TELEMETRY["output_tokens"] += out_tokens
                
                # Update Cost based on model tier
                model_name = getattr(agent["llm"], 'model', 'default')
                # If using fallback, check specific class
                if "Google" in str(type(agent["llm"])):
                    model_name = "gemini-2.5-flash"
                elif "Anthropic" in str(type(agent["llm"])):
                    model_name = "claude-3-5-sonnet-20240620"
                
                # Update Cost based on 2026 AUD conversion (approx 1.51x USD)
                rates = PRICING.get(model_name, PRICING["default"])
                usd_cost = (in_tokens * rates["in"]) + (out_tokens * rates["out"])
                aud_cost = usd_cost * 1.51
                TELEMETRY["total_cost"] += aud_cost
                print(f"[TELEMETRY] Turn Cost: ${aud_cost:.6f} AUD | Total: ${TELEMETRY['total_cost']:.4f}")
                
            except Exception as e:
                print(f"[ORCHESTRATOR ERROR] {agent_name} failed: {e}")
                error_msg = f"\n[CONNECTION ERROR] {agent_name} failed. Ensure your API keys are in .env and Ollama is running."
                yield f"data: [{agent_name}]: {error_msg}\n\n"
                full_responses[key] = error_msg
                
            yield f"data: [{agent_name}] END\n\n"
            
            # Persist to Specialist's Memory Core
            self._save_to_agent_memory(key, message, full_responses[key])

        # 3. Finalize Global Audit & History
        combined_response_str = "\n\n".join([
            f"[{AGENTS[k]['name']}]: {v}"
            for k, v in full_responses.items()
        ])
        self.conversation_history.append(AIMessage(content=combined_response_str))
        self._log_interaction(message, full_responses)
