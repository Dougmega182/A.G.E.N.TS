from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_core.messages import (
    SystemMessage, 
    HumanMessage, 
    AIMessage
)
from langchain_google_genai import ChatGoogleGenerativeAI
from .roster import AGENTS, fast
from .prompt_builder import PromptBuilder
from .core import GovernanceEngine
from .execution_mode import (
    OutputContract,
    build_email_draft_v1_system_prompt,
    build_morning_brief_v1_system_prompt,
    build_plan_v1_system_prompt,
    build_tool_call_v1_system_prompt,
)
from datetime import datetime
import json
import os
from .telemetry import TELEMETRY
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
 
# Model map for specific contracts (Optional but future-proof)
CONTRACT_MODEL_MAP = {
    "morning_brief_v1": fast,
    "email_draft_v1": fast,
    "plan_v1": fast,
    "tool_call_v1": fast,
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
        # Approximate input tokens for routing (initial estimate)
        in_tokens_est = len(message) // 4 + 500 

        
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
            msg_lower = message.lower()
            is_morning_brief = "morning brief" in msg_lower
            is_email_draft = ("draft email" in msg_lower) or ("email draft" in msg_lower)
            is_plan = msg_lower.startswith("plan:") or ("make a plan" in msg_lower) or ("create a plan" in msg_lower)
            is_tool_call = msg_lower.startswith("tool:") or ("tool call" in msg_lower) or ("use tool" in msg_lower)

            required_format_id = None
            contract_prompt_builder = None
            if (key == "jenny") and is_morning_brief:
                required_format_id = "morning_brief_v1"
                contract_prompt_builder = build_morning_brief_v1_system_prompt
            elif is_email_draft:
                required_format_id = "email_draft_v1"
                contract_prompt_builder = build_email_draft_v1_system_prompt
            elif is_plan:
                required_format_id = "plan_v1"
                contract_prompt_builder = build_plan_v1_system_prompt
            elif is_tool_call:
                required_format_id = "tool_call_v1"
                contract_prompt_builder = build_tool_call_v1_system_prompt

            contract_mode = required_format_id is not None

            # Contract mode: hard JSON envelope + zero-noise context (no persona/governance/history).
            if contract_mode:
                final_prompt = contract_prompt_builder()
                messages = [
                    SystemMessage(content=final_prompt),
                    HumanMessage(content=message),
                ]
            else:
                system_prompt = PromptBuilder.build_system_prompt(
                    agent,
                    GovernanceEngine().constitution["laws"],
                    GovernanceEngine().mission["mission"],
                    execution_mode=False,
                )
                final_prompt = PromptBuilder.inject_context(system_prompt, [])
                messages = [SystemMessage(content=final_prompt)]
                for ctx in self.conversation_history[-6:]:
                    messages.append(ctx)
                messages.append(HumanMessage(content=message))
            
            # Decision: Use fast local model for contract mode to ensure zero latency.
            active_llm = agent["llm"]
            if contract_mode:
                # Use override from map if present, otherwise default to fast
                active_llm = CONTRACT_MODEL_MAP.get(required_format_id, fast)
            
            try:
                # For Jenny morning briefs in Execution Mode, buffer full output so we can
                # validate before emitting anything to the UI (prevents meta leakage).
                if contract_mode:
                    print(f"[ORCHESTRATOR] Executing buffered mode for {agent_name} (Contract Mode: {required_format_id}) on Model: {getattr(active_llm, 'model', 'local')}...")
                    resp = active_llm.invoke(messages)
                    response_text = resp.content if hasattr(resp, "content") else str(resp)
                    full_responses[key] = response_text

                    contract = OutputContract()
                    validation = contract.validate(
                        response_text,
                        execution_mode=True,
                        required_format=required_format_id,
                    )
                    if not validation.ok:
                        print(f"[OUTPUT CONTRACT] {agent_name} violation: {validation.reason}")
                        # Enforce contract: emit a deterministic JSON error object (no prose).
                        response_text = json.dumps(
                            {
                                "error": "output_contract_violation",
                                "reason": validation.reason,
                                "expected": required_format_id,
                            },
                            ensure_ascii=False,
                        )
                        full_responses[key] = response_text

                    # Emit as one chunk (still wrapped in the usual SSE framing)
                    yield f"data: [{agent_name}]: {response_text}\n\n"
                else:
                    print(f"[ORCHESTRATOR] Starting stream for {agent_name}...")
                    async for chunk in active_llm.astream(messages):
                        # Token comes from LangChain invoke/stream
                        token_text = chunk.content if hasattr(chunk, 'content') else str(chunk)
                        if token_text:
                            full_responses[key] += token_text
                            yield f"data: [{agent_name}]: {token_text}\n\n"
                        
                # Accurate Token Tracking from Metadata
                usage = {
                    "input_tokens": in_tokens_est, # Default if metadata missing
                    "output_tokens": len(full_responses[key]) // 4,
                    "total_tokens": 0
                }
                
                # Check for LangChain usage metadata (supported by most modern providers)
                # Note: This usually requires specific flags or comes in the final chunk
                # For now, we use a robust fallback and record once.
                
                model_name = getattr(active_llm, 'model', 'default')
                if "Google" in str(type(active_llm)):
                    model_name = "gemini-2.5-flash"
                elif "Anthropic" in str(type(active_llm)):
                    model_name = "claude-3-5-sonnet-20240620"

                # Record once at the end of the agent's turn
                TELEMETRY.record(usage, model_name)
                stats = TELEMETRY.get_stats()
                print(f"[TELEMETRY] {agent_name} Complete | Total Cost: A${stats['cost_aud']:.4f}")
                
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
