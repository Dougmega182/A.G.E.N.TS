from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_core.messages import (
    SystemMessage, 
    HumanMessage, 
    AIMessage
)
from langchain_google_genai import ChatGoogleGenerativeAI
from .roster import AGENTS, fast, gemini
from .prompt_builder import PromptBuilder
from .core import GovernanceEngine
from .execution_mode import (
    OutputContract,
    ContentQuality,
    build_email_draft_v1_system_prompt,
    build_morning_brief_v1_system_prompt,
    build_plan_v1_system_prompt,
    build_implementation_plan_v1_system_prompt,
    build_proposal_v1_system_prompt,
    build_tool_call_v1_system_prompt,
    build_decision_v1_system_prompt,
    build_vote_v1_system_prompt,
    build_audit_log_v1_system_prompt,
    build_critique_v1_system_prompt,
)
from .telemetry import TELEMETRY
from .logic import event_bus
from .logic.event_bus import generate_trace_id
from .logic.event_analytics import get_recent_decisions_from_events, get_risk_trend_from_events, get_structured_memory, format_memory_for_agents
from .logic.governance_engine import evaluate_governance, has_critical_flag, format_flags_for_agents
from .logic.history_engine import get_relevant_memory
from .operators.construction_op import ConstructionOperator
from .logic.risk_engine import calculate_risk_score
from .tools import safe_file_write, safe_file_read, safe_list_files, safe_shell_command
from .google_operator import GmailOperator, CalendarOperator # New import
from .logic.owen_engine import OwenEngine
from .logic import memory_db
from .logic import memory_cache
from .logic.memory_contract import MemoryDomain
from datetime import datetime
import json
import os
import re
from pathlib import Path
from typing import Any, List, Dict, Generator, Optional, Tuple

# Orchestrator uses Gemini for high-speed routing to avoid local hardware lag
router_llm = ChatGoogleGenerativeAI(
    model="gemini-3-flash-preview",
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
 
# Model map for specific contracts (Forced to Gemini 2.5 Flash per user request)
CONTRACT_MODEL_MAP = {
    "morning_brief_v1": gemini,
    "email_draft_v1": gemini,
    "plan_v1": gemini,
    "tool_call_v1": gemini,
}



class Orchestrator:
    
    def __init__(self):
        self.conversation_history = []
        self.session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self.data_dir = Path("data")
        self.log_dir = Path("Agent logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.owen_engine = OwenEngine()
        
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

            # Record telemetry
            if hasattr(response, "usage_metadata"):
                TELEMETRY.record(response.usage_metadata, router_llm.model)
            
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

    async def _gather_morning_brief_data(self) -> Dict[str, Any]:
        """Gathers data from various operators for the morning brief."""
        gmail_operator = GmailOperator(agent_id="jenny")
        calendar_operator = CalendarOperator(agent_id="jenny")

        emails = []
        try:
            emails = gmail_operator.list_messages(max_results=5)
            if isinstance(emails, str): # Handle error messages from operator
                emails = [{"error": emails}]
        except Exception as e:
            emails = [{"error": f"Failed to fetch emails: {str(e)}"}]
            
        events = []
        try:
            events = calendar_operator.list_events(max_results=5)
            if isinstance(events, str): # Handle error messages from operator
                events = [{"error": events}]
        except Exception as e:
            events = [{"error": f"Failed to fetch calendar events: {str(e)}"}]

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "emails": emails,
            "calendar_events": events
        }

    async def astream_chat(self, message: str) -> Generator[str, None, None]:
        """
        Main multi-agent routing entry point for streaming.
        Yields tokens with agent metadata: 'data: [AGENT_NAME]: token\n\n'
        """
        # 1. Decide which agents respond
        print(f"[ORCHESTRATOR] Routing message: {message[:50]}...")
        
        # Phase 3: Multi-Scenario Routing
        msg_lower = message.lower()
        trace_id = generate_trace_id()
        
        if msg_lower.startswith("variation:"):
            async for chunk in self._run_generic_construction_loop("variation", message, trace_id):
                yield chunk
            return
        elif msg_lower.startswith("rfi:"):
            async for chunk in self._run_generic_construction_loop("rfi", message, trace_id):
                yield chunk
            return
        elif msg_lower.startswith("delay:"):
            async for chunk in self._run_generic_construction_loop("delay", message, trace_id):
                yield chunk
            return
        elif msg_lower.startswith("morning brief"):
            yield f"data: [SYSTEM] Gathering data for Morning Brief...\n\n"
            brief_data = await self._gather_morning_brief_data()
            
            # Now route to Jenny specifically for the morning brief
            agent_keys = ["jenny"]
            
            # Update thread history with user input
            self.conversation_history.append(HumanMessage(content=message))
            
            full_responses = {}
            
            for key in agent_keys:
                agent = AGENTS.get(key)
                if not agent:
                    continue
                
                agent_name = agent['name'].upper()
                full_responses[key] = ""
                
                yield f"data: [{agent_name}] START\n\n"
                
                # Build prompt for Jenny with morning brief data
                required_format_id = "morning_brief_v1"
                final_prompt = build_morning_brief_v1_system_prompt()
                
                # Inject brief data as execution context
                messages = [
                    SystemMessage(content=final_prompt),
                    HumanMessage(content=f"MORNING BRIEF DATA:\n{json.dumps(brief_data, indent=2, ensure_ascii=False)}\n\nUSER REQUEST: {message}"),
                ]
                
                active_llm = CONTRACT_MODEL_MAP.get(required_format_id, gemini)
                
                max_attempts = 2
                attempt = 0
                while attempt < max_attempts:
                    attempt += 1
                    try:
                        print(f"[ORCHESTRATOR] Executing buffered mode for {agent_name} (Contract Mode: {required_format_id}) on Model: {getattr(active_llm, 'model', 'local')} (Attempt {attempt})...")
                        resp = active_llm.invoke(messages)

                        # Record telemetry
                        if hasattr(resp, "usage_metadata"):
                            TELEMETRY.record(resp.usage_metadata, getattr(active_llm, "model", "local"))

                        response_text = resp.content if hasattr(resp, "content") else str(resp)
                        full_responses[key] = response_text

                        contract = OutputContract()
                        validation = contract.validate(
                            response_text,
                            execution_mode=True,
                            required_format=required_format_id,
                        )
                        
                        if not validation.ok:
                            event_bus.emit_event("CONTRACT_VALIDATION_FAILED", trace_id, agent_id=key, metadata={"contract": required_format_id, "reason": validation.reason})
                            
                            if attempt < max_attempts:
                                print(f"[OUTPUT CONTRACT] {agent_name} format violation. Retrying...")
                                event_bus.emit_event("RETRY_TRIGGERED", trace_id, agent_id=key, metadata={"reason": "format_violation"})
                                continue
                            
                            print(f"[OUTPUT CONTRACT] {agent_name} final format violation: {validation.reason}")
                            response_text = json.dumps(
                                {
                                    "error": "output_contract_violation",
                                    "reason": validation.reason,
                                    "expected": required_format_id,
                                },
                                ensure_ascii=False,
                            )
                            full_responses[key] = response_text
                        else:
                            quality = ContentQuality()
                            quality_res = quality.check(contract._parse_json_object(response_text), required_format_id)
                            
                            if not quality_res.ok and attempt < max_attempts:
                                print(f"[QUALITY PASS] {agent_name} output weak: {quality_res.hint}. Retrying with hint...")
                                event_bus.emit_event("RETRY_TRIGGERED", trace_id, agent_id=key, metadata={"reason": "quality_weak", "hint": quality_res.hint})
                                hint_msg = HumanMessage(content=f"IMPROVE QUALITY: {quality_res.hint}")
                                messages.append(hint_msg)
                                continue
                            elif not quality_res.ok:
                                print(f"[QUALITY PASS] {agent_name} final quality failure: {quality_res.hint}. Using as-is.")

                        # Emit intent creation event for Phase 4 visibility
                        event_bus.emit_event("ACTION_INTENT_CREATED", trace_id, agent_id=key, scenario="preflight", metadata={
                            "action": required_format_id,
                            "intent_payload": contract._parse_json_object(response_text)
                        })

                        yield f"data: [{agent_name}]: {response_text}\n\n"
                        break 
                    except Exception as e:
                        print(f"[ORCHESTRATOR ERROR] {agent_name} failed: {e}")
                        if attempt < max_attempts:
                            print("Retrying...")
                            continue
                        error_msg = f"\n[CONNECTION ERROR] {agent_name} failed. Ensure your API keys are in .env and Ollama is running."
                        yield f"data: [{agent_name}]: {error_msg}\n\n"
                        full_responses[key] = error_msg
                        break
                    
                yield f"data: [{agent_name}] END\n\n"
                self._save_to_agent_memory(key, message, full_responses[key])
            
            # Finalize Global Audit & History
            combined_response_str = "\n\n".join([
                f"[{AGENTS[k]['name']}]: {v}"
                for k, v in full_responses.items()
            ])
            self.conversation_history.append(AIMessage(content=combined_response_str))
            self._log_interaction(message, full_responses)
            return

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
            
            # Attempt generation with optional retry for quality
            max_attempts = 2
            attempt = 0
            while attempt < max_attempts:
                attempt += 1
                try:
                    # For Jenny morning briefs in Execution Mode, buffer full output so we can
                    # validate before emitting anything to the UI (prevents meta leakage).
                    if contract_mode:
                        print(f"[ORCHESTRATOR] Executing buffered mode for {agent_name} (Contract Mode: {required_format_id}) on Model: {getattr(active_llm, 'model', 'local')} (Attempt {attempt})...")
                        resp = active_llm.invoke(messages)

                        # Record telemetry
                        if hasattr(resp, "usage_metadata"):
                            TELEMETRY.record(resp.usage_metadata, getattr(active_llm, "model", "local"))

                        response_text = resp.content if hasattr(resp, "content") else str(resp)
                        full_responses[key] = response_text

                        contract = OutputContract()
                        validation = contract.validate(
                            response_text,
                            execution_mode=True,
                            required_format=required_format_id,
                        )
                        
                        if not validation.ok:
                            # Format failure: 
                            event_bus.emit_event("CONTRACT_VALIDATION_FAILED", trace_id, agent_id=key, metadata={"contract": required_format_id, "reason": validation.reason})
                            
                            if attempt < max_attempts:
                                print(f"[OUTPUT CONTRACT] {agent_name} format violation. Retrying...")
                                event_bus.emit_event("RETRY_TRIGGERED", trace_id, agent_id=key, metadata={"reason": "format_violation"})
                                continue # Short circuit to next attempt
                            
                            # Final fail: emit a deterministic JSON error object (no prose).
                            print(f"[OUTPUT CONTRACT] {agent_name} final format violation: {validation.reason}")
                            response_text = json.dumps(
                                {
                                    "error": "output_contract_violation",
                                    "reason": validation.reason,
                                    "expected": required_format_id,
                                },
                                ensure_ascii=False,
                            )
                            full_responses[key] = response_text
                        else:
                            # Format is valid, now check content quality
                            parsed_obj = contract._parse_json_object(response_text)
                            quality = ContentQuality()
                            quality_res = quality.check(parsed_obj, required_format_id)
                            
                            if not quality_res.ok and attempt < max_attempts:
                                print(f"[QUALITY PASS] {agent_name} output weak: {quality_res.hint}. Retrying with hint...")
                                event_bus.emit_event("RETRY_TRIGGERED", trace_id, agent_id=key, metadata={"reason": "quality_weak", "hint": quality_res.hint})
                                # Inject small hint and continue to retry
                                hint_msg = HumanMessage(content=f"IMPROVE QUALITY: {quality_res.hint}")
                                messages.append(hint_msg)
                                continue
                            
                            elif not quality_res.ok:
                                print(f"[QUALITY PASS] {agent_name} final quality failure: {quality_res.hint}. Using as-is.")

                        # If we reach here, we are done with this agent's turn (either success or final fail)
                        yield f"data: [{agent_name}]: {response_text}\n\n"
                        break 
                    else:
                        print(f"[ORCHESTRATOR] Starting stream for {agent_name}...")
                        async for chunk in active_llm.astream(messages):
                            # Token comes from LangChain invoke/stream
                            token_text = chunk.content if hasattr(chunk, 'content') else str(chunk)
                            if token_text:
                                full_responses[key] += token_text
                                yield f"data: [{agent_name}]: {token_text}\n\n"
                        
                        # Record telemetry for streaming (estimated)
                        input_tokens = len(message) // 4 + 10
                        output_tokens = len(full_responses[key]) // 4 + 1
                        TELEMETRY.record({
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens": input_tokens + output_tokens
                        }, getattr(active_llm, "model", "local"))

                        break # Normal stream doesn't retry currently
                except Exception as e:
                    print(f"[ORCHESTRATOR ERROR] {agent_name} failed: {e}")
                    if attempt < max_attempts:
                        print("Retrying...")
                        continue
                    error_msg = f"\n[CONNECTION ERROR] {agent_name} failed. Ensure your API keys are in .env and Ollama is running."
                    yield f"data: [{agent_name}]: {error_msg}\n\n"
                    full_responses[key] = error_msg
                    break
                
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

    async def _execute_contract_turn(
        self, 
        agent_key: str, 
        prompt_builder, 
        input_message: str,
        contract_id: str,
        execution_context: str = "",
        trace_id: str = "N/A"
    ) -> Tuple[str, bool, str]:
        """Executes a single high-intelligence contract turn and returns raw response + validation status."""
        agent = AGENTS.get(agent_key)
        if not agent:
            return json.dumps({"error": "agent_not_found"}), False, "agent_not_found"

        agent_name = agent['name'].upper()
        system_prompt = prompt_builder()
        
        # Inject execution context if provided (e.g. Risk score or Critique)
        full_input = input_message
        if execution_context:
            full_input = f"CONTEXT:\n{execution_context}\n\nUSER REQUEST:\n{input_message}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=full_input)
        ]
        
        # Contracts always use the designated contract model (Gemini 2.5 Flash)
        active_llm = CONTRACT_MODEL_MAP.get(contract_id, gemini)
        
        print(f"[LOOP] Executing {agent_name} ({contract_id})...")
        resp = active_llm.invoke(messages)

        # Record telemetry
        if hasattr(resp, "usage_metadata"):
            TELEMETRY.record(resp.usage_metadata, getattr(active_llm, "model", "local"))

        response_text = resp.content if hasattr(resp, "content") else str(resp)

        # Basic contract validation
        contract = OutputContract()
        validation = contract.validate(
            response_text,
            execution_mode=True,
            required_format=contract_id
        )
        
        if not validation.ok:
            print(f"[LOOP] {agent_key.upper()} format violation: {validation.reason}")
            event_bus.emit_event("CONTRACT_VALIDATION_FAILED", trace_id, agent_id=agent_key, metadata={"contract": contract_id, "reason": validation.reason})
            return response_text, False, validation.reason or "validation_failed"
        
        return response_text, True, ""

    def _normalize_completion_status(self, mutation_result: Any) -> str:
        if not isinstance(mutation_result, dict):
            return "FAILED"

        status = str(mutation_result.get("completion_status", "")).upper()
        if status in {"EXECUTED", "PARTIALLY_EXECUTED", "FAILED"}:
            return status

        executed_count = mutation_result.get("executed_count", 0)
        failed_count = mutation_result.get("failed_count", 0)
        try:
            executed_count = int(executed_count)
        except Exception:
            executed_count = 0
        try:
            failed_count = int(failed_count)
        except Exception:
            failed_count = 0

        if executed_count > 0 and failed_count == 0:
            return "EXECUTED"
        if executed_count > 0 and failed_count > 0:
            return "PARTIALLY_EXECUTED"
        return "FAILED"

    def _build_construction_executor_task(
        self,
        scenario_type: str,
        trace_id: str,
        risk_score: float,
        justification: str,
        impact: Dict[str, Any],
        status: str,
        user_input: str,
    ) -> Dict[str, Any]:
        return {
            "trace_id": trace_id,
            "tool_calls": [{
                "tool": "update_entity",
                "arguments": {
                    "type": scenario_type,
                    "risk_score": risk_score,
                    "justification": justification,
                    "data": {
                        "cost": impact.get("cost", 0),
                        "days": impact.get("days", 0),
                        "status": status,
                        "reason": user_input,
                        "risk_delta": impact.get("risk_delta", 0)
                    }
                }
            }]
        }

    def _enforce_executor_tool_calls(
        self,
        task_payload: Dict[str, Any],
        trace_id: str,
        scenario_type: str,
    ) -> Tuple[bool, str]:
        contract = OutputContract()
        contract_res = contract.conforms_to_contract(task_payload, "tool_call_v1")
        if not contract_res.ok:
            reason = contract_res.reason or "tool_call_schema_invalid"
            event_bus.emit_event("ACTION_BLOCKED", trace_id, scenario=scenario_type, metadata={
                "reason": reason,
                "completion_status": "FAILED"
            })
            return False, reason

        calls = task_payload.get("tool_calls", [])
        unsupported = [c.get("tool") for c in calls if c.get("tool") != "update_entity"]
        if unsupported:
            reason = f"unsupported_executor_tools:{','.join([str(t) for t in unsupported])}"
            event_bus.emit_event("ACTION_BLOCKED", trace_id, scenario=scenario_type, metadata={
                "reason": reason,
                "completion_status": "FAILED"
            })
            return False, reason

        return True, ""

    def _run_construction_executor_phase(
        self,
        scenario_type: str,
        trace_id: str,
        task_payload: Dict[str, Any],
        status: str,
        system_forced_escalation: bool,
        max_attempts: int = 2,
    ) -> Dict[str, Any]:
        last_result: Dict[str, Any] = {
            "completion_status": "FAILED",
            "executed_count": 0,
            "failed_count": 0,
            "total_calls": 0,
            "results": [],
            "error": "execution_not_started"
        }

        enforce_ok, enforce_reason = self._enforce_executor_tool_calls(task_payload, trace_id, scenario_type)
        if not enforce_ok:
            last_result["error"] = enforce_reason
            return last_result

        for attempt in range(1, max_attempts + 1):
            event_bus.emit_event("ACTION_INTENT", trace_id, agent_id="SYSTEM", scenario=scenario_type, metadata={
                "tool": "update_entity",
                "status": status,
                "forced_by_system": "true" if system_forced_escalation else "false",
                "attempt": attempt
            })

            raw_result = ConstructionOperator.handle_tool_call(task_payload)
            if isinstance(raw_result, dict):
                last_result = dict(raw_result)
            else:
                last_result = {
                    "completion_status": "FAILED",
                    "executed_count": 0,
                    "failed_count": 0,
                    "total_calls": 0,
                    "results": [],
                    "error": "invalid_executor_result"
                }

            completion_status = self._normalize_completion_status(last_result)
            last_result["completion_status"] = completion_status
            last_result["attempt"] = attempt

            if completion_status in {"EXECUTED", "PARTIALLY_EXECUTED"}:
                return last_result

            executed_count = last_result.get("executed_count", 0)
            try:
                executed_count = int(executed_count)
            except Exception:
                executed_count = 0

            if attempt < max_attempts and executed_count == 0:
                event_bus.emit_event("RETRY_TRIGGERED", trace_id, agent_id="SYSTEM", scenario=scenario_type, metadata={
                    "reason": "no_action_executed",
                    "attempt": attempt,
                    "next_attempt": attempt + 1
                })
                continue

            break

        return last_result

    async def _run_generic_construction_loop(self, scenario_type: str, user_input: str, trace_id: str) -> Generator[str, None, None]:
        """
        Phase 3.5 Universal Construction Engine (Event-Driven):
        Risk Engine -> Event Analytics (Trend/History) -> Nadia -> Sentinel -> Aria -> Jenny -> Unified Mutation
        """
        scenario_label = scenario_type.upper()
        event_bus.emit_event("LOOP_STARTED", trace_id, scenario=scenario_type, metadata={"input": user_input})
        yield f"data: [SYSTEM] Initiating {scenario_label} Loop... [Trace: {trace_id[:8]}]\n\n"
        contract_engine = OutputContract()
        
        # 0. LOAD TREND FROM EVENTS
        risk_trend = get_risk_trend_from_events()
        trend_str = f"RISK TREND: {risk_trend['direction'].upper()} (last 5: {risk_trend['avg_5']}, last 10: {risk_trend['avg_10']})"
        yield f"data: [SYSTEM] Current Project Health: {trend_str}\n\n"

        # 1. RISK SCORING (Scenario-Aware)
        # Matches "$12k", "12000", "12,000"
        cost_match = re.search(r"\$?(\d+[\d,]*)\s*k?", user_input.lower())
        days_match = re.search(r"(\d+)\s*day", user_input.lower())
        
        cost_str = cost_match.group(1).replace(",", "") if cost_match else "0"
        is_k = "k" in cost_match.group(0).lower() if cost_match else False
        cost = float(cost_str) * (1000 if is_k else 1)
        days = int(days_match.group(1)) if days_match else 0
        
        risk_score = calculate_risk_score(scenario_type, cost, days, user_input)
        yield f"data: [SYSTEM] Calculated Risk Score: {risk_score}\n\n"
        event_bus.emit_event("RISK_SCORE_CALCULATED", trace_id, scenario=scenario_type, metadata={"risk_score": risk_score})

        # 2. PHASE 2: REASONING CONTEXT ASSEMBLY
        # Build the unified reasoning_context object — single source of truth for all agents
        memory = get_relevant_memory(scenario_type, limit=5)
        governance_flags = evaluate_governance(scenario_type, cost, days, risk_score)
        governance_str = format_flags_for_agents(governance_flags)
        memory_str = memory["formatted"]

        # 2a. OWEN INTELLIGENCE BRIEFING (NEW Phase 2.5 Intelligence Layer)
        owen_briefing = self.owen_engine.generate_intelligence_briefing(scenario_type, query_text=user_input)
        owen_str = self.owen_engine.format_briefing_for_prompt(owen_briefing)
        yield f"data: [SYSTEM] Owen's Intelligence Briefing loaded for {scenario_label}.\n\n"
        
        reasoning_context = {
            "risk_score": risk_score,
            "governance_flags": [f.to_dict() for f in governance_flags],
            "institutional_memory": memory["structured"],
            "trend": risk_trend["direction"],
            "owen_intelligence": owen_briefing
        }
        
        # Cache context in Redis/memory
        memory_cache.cache_reasoning_context("orchestrator", trace_id, reasoning_context)
        
        yield f"data: [SYSTEM] Governance Flags: {len(governance_flags)} raised | Memory: {memory['count']} prior decisions loaded\n\n"
        event_bus.emit_event("REASONING_CONTEXT_ASSEMBLED", trace_id, scenario=scenario_type, metadata={
            "governance_flag_count": len(governance_flags),
            "critical_flags": has_critical_flag(governance_flags),
            "memory_count": memory["count"],
            "trend": risk_trend["direction"],
        })

        # 2b. CRITICAL GOVERNANCE ENFORCEMENT
        # If any governance flag has CRITICAL severity, force ESCALATE before any agent runs
        if has_critical_flag(governance_flags):
            critical_flags_str = ", ".join([f.flag_type for f in governance_flags if f.severity == "CRITICAL"])
            yield f"data: [SYSTEM] ⚠️ CRITICAL GOVERNANCE FLAG(S) DETECTED: {critical_flags_str}. Decision will be forced to ESCALATE.\n\n"
            event_bus.emit_event("GOVERNANCE_CRITICAL_OVERRIDE", trace_id, scenario=scenario_type, metadata={
                "critical_flags": critical_flags_str,
                "action": "forced_escalate"
            })

        # 3. NADIA: Generate Plan (with reasoning context)
        yield f"data: [NADIA] START\n\n"
        nadia_context = f"SCENARIO TYPE: {scenario_label}\nPROJECT HEALTH: {trend_str}\n{governance_str}\n{memory_str}\n\n{owen_str}"
        plan_raw, _, _ = await self._execute_contract_turn("nadia", build_plan_v1_system_prompt, user_input, "plan_v1", execution_context=nadia_context, trace_id=trace_id)
        yield f"data: [NADIA]: {plan_raw}\n\n"
        yield f"data: [NADIA] END\n\n"
        event_bus.emit_event("PLAN_GENERATED", trace_id, agent_id="nadia", scenario=scenario_type, metadata={"plan": plan_raw})

        # 3b. TUCKER: Generate Implementation Plan
        yield f"data: [TUCKER] START\n\n"
        tucker_context = f"SCENARIO TYPE: {scenario_label}\nNADIA'S PLAN: {plan_raw}\n\n{owen_str}"
        impl_plan_raw, _, _ = await self._execute_contract_turn("tucker", build_implementation_plan_v1_system_prompt, user_input, "implementation_plan_v1", execution_context=tucker_context, trace_id=trace_id)
        yield f"data: [TUCKER]: {impl_plan_raw}\n\n"
        yield f"data: [TUCKER] END\n\n"
        event_bus.emit_event("IMPLEMENTATION_PLAN_GENERATED", trace_id, agent_id="tucker", scenario=scenario_type, metadata={"implementation_plan": impl_plan_raw})

        # 4. WALL-E: Advisory Critique (Trend-Aware + Governance-Aware)
        yield f"data: [WALL-E] START\n\n"
        critique_context = f"SCENARIO TYPE: {scenario_label}\nPROJECT HEALTH: {trend_str}\n{governance_str}\n\n{owen_str}"
        critique_input = f"Proposed Plan: {plan_raw}\nImplementation Plan: {impl_plan_raw}\n\nInput Details: {user_input}"
        critique_raw, _, _ = await self._execute_contract_turn("wall-e", build_critique_v1_system_prompt, critique_input, "critique_v1", execution_context=critique_context, trace_id=trace_id)
        yield f"data: [WALL-E]: {critique_raw}\n\n"
        yield f"data: [WALL-E] END\n\n"
        event_bus.emit_event("CRITIQUE_GENERATED", trace_id, agent_id="wall-e", scenario=scenario_type, metadata={"critique": critique_raw})

        # 4b. OWEN: Intelligence Synthesis (Internal only)
        # Owen's intelligence is now injected into other agents as context.
        # No formal vote is cast in the loop.

        # 5. ARIA: Justified Final Decision + Impact (with full reasoning context)
        yield f"data: [ARIA] START\n\n"
        safety_alert = ""
        if risk_score >= 0.85:
            safety_alert = "--- SAFETY GATE ACTIVE ---\nACTION RESTRICTED: Risk Score is >= 0.85. You ARE NOT AUTHORISED to 'APPROVE'. You must either 'REJECT' or 'ESCALATE' to human review.\n--------------------------\n"
        
        aria_context = (
            f"{safety_alert}"
            f"SCENARIO TYPE: {scenario_label}\n"
            f"RISK SCORE: {risk_score}\n"
            f"PROJECT HEALTH: {trend_str}\n"
            f"{governance_str}\n"
            f"{memory_str}\n\n"
            f"{owen_str}\n"
            f"WALL-E CRITIQUE: {critique_raw}"
        )
        decision_input = f"Request: {user_input}\n\nNadia's Plan: {plan_raw}\nTucker's Implementation Plan: {impl_plan_raw}"
        decision_raw, decision_valid, decision_error_reason = await self._execute_contract_turn("aria", build_decision_v1_system_prompt, decision_input, "decision_v1", execution_context=aria_context, trace_id=trace_id)
        yield f"data: [ARIA]: {decision_raw}\n\n"
        yield f"data: [ARIA] END\n\n"

        # --- DECISION FINALIZATION ---
        # All post-decision logic lives in the Decision Finalizer.
        # The orchestrator is the ONLY caller. Everything else is advisory.
        from .logic.decision_finalizer import finalize_decision

        decision_data = contract_engine._parse_json_object(decision_raw)
        critique_data = contract_engine._parse_json_object(critique_raw)
        
        finalized = finalize_decision(
            decision_data=decision_data if decision_data else {},
            decision_valid=decision_valid,
            decision_error_reason=decision_error_reason,
            risk_score=risk_score,
            governance_flags=governance_flags,
            critique_data=critique_data,
            memory_count=memory["count"],
            trace_id=trace_id,
            scenario_type=scenario_type,
            outcome_score=decision_data.get("outcome_score") if decision_data else None,
        )

        # Update decision_raw to reflect final canonical decision
        if decision_data:
            decision_raw = json.dumps(decision_data, ensure_ascii=False)

        # --- Yield system messages for any overrides or warnings ---
        if finalized.was_system_forced:
            yield f"data: [SYSTEM] Technical Logic Failure detected. Decision overridden to ESCALATE.\n\n"

        if finalized.was_overridden and not finalized.was_system_forced:
            for override in finalized.override_chain:
                if override == "GOVERNANCE_CRITICAL_OVERRIDE":
                    critical_types = [f["flag_type"] for f in finalized.governance_flags if f.get("severity") == "CRITICAL"]
                    yield f"data: [SYSTEM] GOVERNANCE OVERRIDE: Aria's {finalized.original_decision} was overridden to ESCALATE due to CRITICAL flag(s): {', '.join(critical_types)}\n\n"
                elif override == "SAFETY_GATE_OVERRIDE":
                    yield f"data: [SYSTEM] SAFETY GATE OVERRIDE: Aria's {finalized.original_decision} was overridden to ESCALATE (risk_score={risk_score}).\n\n"
                elif override == "CONFIDENCE_GATE_OVERRIDE":
                    yield f"data: [SYSTEM] CONFIDENCE GATE OVERRIDE: Aria's {finalized.original_decision} was overridden to ESCALATE (confidence_score={finalized.confidence_score} < 0.6).\n\n"

        if finalized.conflict_detected:
            yield f"data: [SYSTEM] PLANNING CONFLICT: {finalized.conflict_detail}\n\n"

        if finalized.reasoning_quality_warnings:
            yield f"data: [SYSTEM] Reasoning Quality Warning: {', '.join(finalized.reasoning_quality_warnings)}\n\n"

        # --- Emit the ONE canonical event ---
        # DECISION_MADE is kept for backward compatibility with existing analytics
        event_bus.emit_event("DECISION_MADE", trace_id, agent_id="aria", scenario=scenario_type, metadata={
            "decision": finalized.final_decision,
            "risk_score": risk_score,
            "impact": decision_data.get("impact", {}) if decision_data else {},
            "justification": finalized.final_justification,
            "conflict": "true" if finalized.conflict_detected else "false",
            "forced_by_system": "true" if finalized.was_system_forced else "false",
            "governance_overridden": "true" if finalized.was_overridden else "false",
            "reasoning_quality_warnings": finalized.reasoning_quality_warnings,
            "validation_ok": "true" if decision_valid else "false",
            "validation_reason": decision_error_reason or ""
        })

        # This is the DEBUG ANCHOR EVENT — the single source of truth for dashboards
        event_bus.emit_event("DECISION_FINALIZED_V1", trace_id, agent_id="system", scenario=scenario_type, metadata=finalized.to_event_payload())

        # --- TIER 2 MEMORY PERSISTENCE (SQLite) ---
        # Write to structured database for warm lookup and Owen synthesis
        decision_event = {
            "event_id": generate_trace_id(),
            "trace_id": trace_id,
            "scenario": scenario_type,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": finalized.to_event_payload()
        }
        memory_db.write_decision("orchestrator", decision_event)

        # --- OWEN POST-DECISION LEARNING ---
        # Owen extracts lessons and patterns from the canonical decision record
        self.owen_engine.extract_lesson_from_decision(decision_event)


        # 6. JENNY: Comms
        yield f"data: [JENNY] START\n\n"
        email_raw, _, _ = await self._execute_contract_turn("jenny", build_email_draft_v1_system_prompt, f"Decision made: {decision_raw}", "email_draft_v1", trace_id=trace_id)
        yield f"data: [JENNY]: {email_raw}\n\n"
        yield f"data: [JENNY] END\n\n"

        # 7. INTENT GENERATION (for Human Approval)
        # Create the formal ACTION_INTENT_V1 object that will be executed.
        # This object is immutable from this point forward.
        yield f"data: [SYSTEM] Generating formal execution intent...\n\n"
        
        email_data = contract_engine._parse_json_object(email_raw) or {}
        
        # Build the structured Operator Bundle
        delay_days = decision_data.get("impact", {}).get("days", 0) if decision_data else 0
        
        actions_array = []
        if finalized.final_decision == "APPROVE":
            actions_array.append({
                "type": "gmail_draft",
                "priority": "high",
                "reason": "stakeholder notification",
                "payload": email_data
            })
            if delay_days > 0:
                actions_array.append({
                    "type": "calendar_event",
                    "delay_days": delay_days,
                    "title": f"Variation Impact ({delay_days}d delay)",
                    "reason": "schedule impact adjustment"
                })
        else:
            actions_array.append({
                "type": "audit_log",
                "reason": "record escalation"
            })
            
        operator_bundle = {
            "decision": finalized.final_decision,
            "confidence": finalized.confidence_score,
            "actions": actions_array,
            "risks": [f.flag_type for f in governance_flags] if governance_flags else [],
            "owen_refs": owen_briefing.get("patterns", {}).get("dos", []) + owen_briefing.get("patterns", {}).get("donts", [])
        }
        
        # DISCLOSURE: Pack everything into metadata for the Human Gatekeeper
        disclosure_metadata = {
            "scenario": scenario_type,
            "risk_score": risk_score,
            "governance_flags": [f.to_dict() for f in governance_flags],
            "owen_briefing": owen_briefing,
            "final_decision": finalized.final_decision,
            "final_justification": finalized.final_justification,
            "original_decision": finalized.original_decision,
            "conflict_detected": finalized.conflict_detected,
            "plan_summary": (contract_engine._parse_json_object(plan_raw) or {}).get("summary", ""),
        }

        action_intent = {
            "action": "operator_bundle",
            "agent_id": "system",
            "parameters": operator_bundle,
            "trace_id": trace_id,
            "requires_approval": True,
            "status": "pending",
            "summary": f"[{finalized.final_decision}] Confidence: {finalized.confidence_score} | {len(actions_array)} action(s)",
            "metadata": disclosure_metadata
        }

        # Register the intent in the Preflight Approval Engine
        from . import firewall
        request = firewall.create_or_get_request(action_intent=action_intent)
        
        yield f"data: [SYSTEM] PROPOSAL CREATED. Request ID: {request['request_id']}\n\n"
        yield f"data: [SYSTEM] Awaiting human approval. [{len(actions_array)} Action(s) Bundled]\n\n"

        # 8. WALL-E: Audit
        yield f"data: [WALL-E] START\n\n"
        audit_input = f"Type: {scenario_label}\nRisk: {risk_score}\nTrend: {risk_trend['direction']}\nDecision: {decision_raw}"
        audit_raw, _, _ = await self._execute_contract_turn("wall-e", build_audit_log_v1_system_prompt, audit_input, "audit_log_v1", trace_id=trace_id)
        ConstructionOperator.log_to_sentinel(f"{scenario_label}_LOOP", "WALL-E", audit_input, audit_raw)
        yield f"data: [WALL-E]: {audit_raw}\n\n"
        yield f"data: [WALL-E] END\n\n"
        
        event_bus.emit_event("LOOP_COMPLETE", trace_id, scenario=scenario_type, metadata={"status": "awaiting_approval", "request_id": request['request_id'], "action": "operator_bundle"})
        yield f"data: [SYSTEM] {scenario_label} Loop Paused for Approval. [Trace: {trace_id[:8]}]\n\n"

