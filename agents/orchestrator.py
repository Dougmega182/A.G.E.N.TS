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
    build_tool_call_v1_system_prompt,
    build_decision_v1_system_prompt,
    build_audit_log_v1_system_prompt,
    build_critique_v1_system_prompt,
)
from .telemetry import TELEMETRY
from .logic.event_bus import emit_event, generate_trace_id
from .logic.event_analytics import get_recent_decisions_from_events, get_risk_trend_from_events
from .operators.construction_op import ConstructionOperator
from .logic.risk_engine import calculate_risk_score
from datetime import datetime
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Generator, Tuple

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
                            emit_event("CONTRACT_VALIDATION_FAILED", trace_id, agent_id=key, metadata={"contract": required_format_id, "reason": validation.reason})
                            
                            if attempt < max_attempts:
                                print(f"[OUTPUT CONTRACT] {agent_name} format violation. Retrying...")
                                emit_event("RETRY_TRIGGERED", trace_id, agent_id=key, metadata={"reason": "format_violation"})
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
                                emit_event("RETRY_TRIGGERED", trace_id, agent_id=key, metadata={"reason": "quality_weak", "hint": quality_res.hint})
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
            emit_event("CONTRACT_VALIDATION_FAILED", trace_id, agent_id=agent_key, metadata={"contract": contract_id, "reason": validation.reason})
            return response_text, False, validation.reason or "validation_failed"
        
        return response_text, True, ""

    async def _run_generic_construction_loop(self, scenario_type: str, user_input: str, trace_id: str) -> Generator[str, None, None]:
        """
        Phase 3.5 Universal Construction Engine (Event-Driven):
        Risk Engine -> Event Analytics (Trend/History) -> Nadia -> Sentinel -> Aria -> Jenny -> Unified Mutation
        """
        scenario_label = scenario_type.upper()
        emit_event("LOOP_STARTED", trace_id, scenario=scenario_type, metadata={"input": user_input})
        yield f"data: [SYSTEM] Initiating {scenario_label} Loop... [Trace: {trace_id[:8]}]\n\n"
        contract_engine = OutputContract()
        
        # 0. LOAD TREND FROM EVENTS
        risk_trend = get_risk_trend_from_events()
        trend_str = f"RISK TREND: {risk_trend['direction'].upper()} (last 5: {risk_trend['avg_5']}, last 10: {risk_trend['avg_10']})"
        yield f"data: [SYSTEM] Current Project Health: {trend_str}\n\n"

        # 1. RISK SCORING (Scenario-Aware)
        cost_match = re.search(r"(\d+)\s*k", user_input.lower())
        days_match = re.search(r"(\d+)\s*day", user_input.lower())
        cost = float(cost_match.group(1)) * 1000 if cost_match else 0
        days = int(days_match.group(1)) if days_match else 0
        
        risk_score = calculate_risk_score(scenario_type, cost, days, user_input)
        yield f"data: [SYSTEM] Calculated Risk Score: {risk_score}\n\n"
        emit_event("RISK_SCORE_CALCULATED", trace_id, scenario=scenario_type, metadata={"risk_score": risk_score})

        # 2. MEMORY LOAD FROM EVENTS
        history = get_recent_decisions_from_events(n=5)
        history_str = "No recent history."
        if history:
            history_str = "\n".join([f"- {h['timestamp']}: {h['decision']} (Type: {h.get('type','N/A')}, Cost: {h['cost']}, Risk: {h['risk_score']})" for h in history])
        
        # 3. NADIA: Generate Plan
        yield f"data: [NADIA] START\n\n"
        nadia_context = f"SCENARIO TYPE: {scenario_label}\nPROJECT HEALTH: {trend_str}\nRECENT HISTORY:\n{history_str}"
        plan_raw, _, _ = await self._execute_contract_turn("nadia", build_plan_v1_system_prompt, user_input, "plan_v1", execution_context=nadia_context, trace_id=trace_id)
        yield f"data: [NADIA]: {plan_raw}\n\n"
        yield f"data: [NADIA] END\n\n"
        emit_event("PLAN_GENERATED", trace_id, agent_id="nadia", scenario=scenario_type, metadata={"plan": plan_raw})

        # 4. SENTINEL: Advisory Critique (Trend-Aware)
        yield f"data: [SENTINEL] START\n\n"
        critique_context = f"SCENARIO TYPE: {scenario_label}\nPROJECT HEALTH: {trend_str}"
        critique_input = f"Proposed Plan: {plan_raw}\n\nInput Details: {user_input}"
        critique_raw, _, _ = await self._execute_contract_turn("sentinel", build_critique_v1_system_prompt, critique_input, "critique_v1", execution_context=critique_context, trace_id=trace_id)
        yield f"data: [SENTINEL]: {critique_raw}\n\n"
        yield f"data: [SENTINEL] END\n\n"
        emit_event("CRITIQUE_GENERATED", trace_id, agent_id="sentinel", scenario=scenario_type, metadata={"critique": critique_raw})

        # 5. ARIA: Justified Final Decision + Impact
        yield f"data: [ARIA] START\n\n"
        safety_alert = ""
        if risk_score >= 0.85:
            safety_alert = "--- SAFETY GATE ACTIVE ---\nACTION RESTRICTED: Risk Score is >= 0.85. You ARE NOT AUTHORISED to 'APPROVE'. You must either 'REJECT' or 'ESCALATE' to human review.\n--------------------------\n"
        
        aria_context = f"{safety_alert}SCENARIO TYPE: {scenario_label}\nRISK SCORE: {risk_score}\nPROJECT HEALTH: {trend_str}\nSENTINEL CRITIQUE: {critique_raw}\nRECENT HISTORY:\n{history_str}"
        decision_input = f"Request: {user_input}\n\nPlan: {plan_raw}"
        decision_raw, decision_valid, decision_error_reason = await self._execute_contract_turn("aria", build_decision_v1_system_prompt, decision_input, "decision_v1", execution_context=aria_context, trace_id=trace_id)
        yield f"data: [ARIA]: {decision_raw}\n\n"
        yield f"data: [ARIA] END\n\n"

        # Conflict Detection + Technical Escalation Enforcement
        decision_data = contract_engine._parse_json_object(decision_raw)
        conflict_flag = ""
        system_forced_escalation = (not decision_valid) or (decision_data is None)

        if system_forced_escalation:
            failure_reason = decision_error_reason or "decision_payload_unparseable"
            if not decision_valid:
                emit_event("CONTRACT_VALIDATION_FAILED", trace_id, agent_id="aria", scenario=scenario_type, metadata={"contract": "decision_v1", "reason": failure_reason, "forced_escalation": "true"})
            decision_data = {
                "decision": "ESCALATE",
                "justification": f"Technical Logic Failure: decision_v1 validation failed ({failure_reason}). System-forced escalation to protect project integrity.",
                "conditions": [
                    "Manual human review required",
                    "Re-run decision turn with valid contract payload"
                ],
                "impact": {"cost": 0, "days": 0, "risk_delta": 0}
            }
            decision_raw = json.dumps(decision_data, ensure_ascii=False)
            yield f"data: [SYSTEM] Technical Logic Failure detected. Decision overridden to ESCALATE.\n\n"
        else:
            try:
                critique_data = contract_engine._parse_json_object(critique_raw)
                if critique_data and decision_data:
                    sentinel_rec = str(critique_data.get("recommendation", "")).upper()
                    aria_dec = str(decision_data.get("decision", "")).upper()
                    if sentinel_rec == "REJECT" and aria_dec == "APPROVE":
                        conflict_flag = " [PLANNING CONFLICT DETECTED: Sentinel recommended REJECT but Aria APPROVED]"
            except:
                pass
        
        emit_event("DECISION_MADE", trace_id, agent_id="aria", scenario=scenario_type, metadata={
            "decision": decision_data.get("decision"),
            "risk_score": risk_score,
            "impact": decision_data.get("impact", {}),
            "justification": decision_data.get("justification", ""),
            "conflict": "true" if conflict_flag else "false",
            "forced_by_system": "true" if system_forced_escalation else "false",
            "validation_ok": "true" if decision_valid else "false",
            "validation_reason": decision_error_reason or ""
        })

        # 6. JENNY: Comms
        yield f"data: [JENNY] START\n\n"
        email_raw, _, _ = await self._execute_contract_turn("jenny", build_email_draft_v1_system_prompt, f"Decision made: {decision_raw}", "email_draft_v1", trace_id=trace_id)
        yield f"data: [JENNY]: {email_raw}\n\n"
        yield f"data: [JENNY] END\n\n"

        # 7. TOOL: Unified State Mutation (update_entity)
        yield f"data: [SYSTEM] Updating project record...\n\n"
        decision_text = str(decision_data.get("decision")).upper()
        status = "approved" if decision_text == "APPROVE" else "rejected"
        if decision_text == "ESCALATE":
            status = "escalated"
        
        # Unified impact data from Aria / fallback impact for forced escalation
        impact = decision_data.get("impact", {"cost": 0, "days": 0, "risk_delta": 0})
        
        tool_call = {
            "trace_id": trace_id,
            "tool_calls": [{
                "tool": "update_entity",
                "arguments": {
                    "type": scenario_type,
                    "risk_score": risk_score,
                    "justification": decision_data.get("justification", "") + conflict_flag,
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
        emit_event("ACTION_INTENT", trace_id, agent_id="SYSTEM", scenario=scenario_type, metadata={
            "tool": "update_entity",
            "status": status,
            "forced_by_system": "true" if system_forced_escalation else "false"
        })
        mutation_ok = ConstructionOperator.handle_tool_call(tool_call)
        if mutation_ok:
            yield f"data: [SYSTEM] Record updated. {conflict_flag}\n\n"
        else:
            yield f"data: [SYSTEM] Record update failed.\n\n"

        # 8. SENTINEL: Audit
        yield f"data: [SENTINEL] START\n\n"
        audit_input = f"Type: {scenario_label}\nRisk: {risk_score}\nTrend: {risk_trend['direction']}\nDecision: {decision_raw}"
        audit_raw, _, _ = await self._execute_contract_turn("sentinel", build_audit_log_v1_system_prompt, audit_input, "audit_log_v1", trace_id=trace_id)
        ConstructionOperator.log_to_sentinel(f"{scenario_label}_LOOP", "SENTINEL", audit_input, audit_raw)
        yield f"data: [SENTINEL]: {audit_raw}\n\n"
        yield f"data: [SENTINEL] END\n\n"
        
        emit_event("LOOP_COMPLETE", trace_id, scenario=scenario_type)
        yield f"data: [SYSTEM] {scenario_label} Loop Complete.\n\n"

