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
from .google_operator import GmailOperator, CalendarOperator 
from .logic.owen_engine import OwenEngine
from .logic import memory_db
from .logic import memory_cache
from .logic.input_sanitiser import MAX_DELAY_DAYS_SOFT, sanitise_construction_input
from .logic.memory_contract import MemoryDomain
from datetime import datetime
import json
import uuid
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
 
# Model map for specific contracts
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
        
    def _normalize_model_content(self, content: Any) -> str:
        """Collapse provider-specific content blocks into readable plain text."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                res = self._normalize_model_content(item)
                if res:
                    parts.append(res)
            return "\n".join(parts).strip()
        if isinstance(content, dict):
            text = content.get("text")
            if text:
                return str(text)
        return str(content)

    def _build_agent_list(self) -> str:
        lines = []
        for key, agent in AGENTS.items():
            lines.append(f"- {key}: {agent['name']} ({agent['title']})")
        return "\n".join(lines)

    def _construction_acknowledgement(self, scenario_type: str) -> str:
        scenario = scenario_type.lower()
        if scenario in {"variation", "rfi", "delay", "site_issue"}:
            return (
                "Aria: Acknowledge Dale, now engaging: "
                "NADIA (plan_v1), TUCKER (implementation_plan_v1), "
                "WALL-E (critique_v1), Myself (decision_v1), "
                "JENNY (email_draft_v1), WALL-E (audit_log_v1)."
            )
        return "Aria: Acknowledge Dale, now engaging the requested workflow."

    def _summarize_operator_subject(self, scenario_type: str, user_input: str) -> str:
        raw = " ".join(str(user_input or "").split()).strip()
        if not raw:
            return scenario_type.replace("_", " ").title()
        raw = re.sub(r"^\s*(variation|rfi|delay|issue)\s*:\s*", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*Cost impact:\s*\$?[\d,]+(?:\.\d+)?\.?", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s*Delay:\s*\d+\s*days?\.?", "", raw, flags=re.IGNORECASE)
        raw = raw.strip(" .;-")
        if len(raw) > 110:
            raw = raw[:107].rstrip() + "..."
        return raw or scenario_type.replace("_", " ").title()

    def _format_sse(self, agent_label: str, payload: Any) -> str:
        text = str(payload or "")
        lines = text.splitlines() or [""]
        return "\n".join(f"data: [{agent_label}] {line}" for line in lines) + "\n\n"
    
    def _route_message(self, message: str) -> List[str]:
        message_lower = message.lower()
        direct_mentions = []
        for key, agent in AGENTS.items():
            if any(t in message_lower for t in agent["triggers"]):
                if key not in direct_mentions:
                    direct_mentions.append(key)
        if direct_mentions:
            return direct_mentions
        try:
            response = router_llm.invoke([
                SystemMessage(content=ROUTER_PROMPT.format(agent_list=self._build_agent_list())),
                HumanMessage(content=message)
            ])
            if hasattr(response, "usage_metadata"):
                TELEMETRY.record(response.usage_metadata, router_llm.model)
            content = self._normalize_model_content(response.content)
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            agents = json.loads(content)
            return agents if isinstance(agents, list) else ["aria"]
        except Exception as e:
            print(f"Routing Error: {e}. Defaulting to Aria.")
            return ["aria"]

    async def _execute_contract_turn(self, agent_key: str, prompt_builder, input_message: str, contract_id: str, execution_context: str = "", trace_id: str = "N/A") -> Tuple[str, bool, str]:
        agent = AGENTS.get(agent_key)
        if not agent:
            return json.dumps({"error": "agent_not_found"}), False, "agent_not_found"
        agent_name = agent['name'].upper()
        system_prompt = prompt_builder()
        full_input = f"CONTEXT:\n{execution_context}\n\nUSER REQUEST:\n{input_message}" if execution_context else input_message
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=full_input)]
        active_llm = CONTRACT_MODEL_MAP.get(contract_id, gemini)
        print(f"[LOOP] Executing {agent_name} ({contract_id})...")
        resp = active_llm.invoke(messages)
        if hasattr(resp, "usage_metadata"):
            TELEMETRY.record(resp.usage_metadata, getattr(active_llm, "model", "local"))
        response_text = self._normalize_model_content(resp.content)
        contract = OutputContract()
        validation = contract.validate(response_text, execution_mode=True, required_format=contract_id)
        if not validation.ok:
            print(f"[LOOP] {agent_key.upper()} format violation: {validation.reason}")
            event_bus.emit_event("CONTRACT_VALIDATION_FAILED", trace_id, agent_id=agent_key, metadata={"contract": contract_id, "reason": validation.reason})
            return response_text, False, validation.reason or "validation_failed"
        return response_text, True, ""

    async def astream_chat(self, message: str) -> Generator[str, None, None]:
        print(f"[ORCHESTRATOR] Routing message: {message[:50]}...")
        msg_lower = message.lower()
        trace_id = generate_trace_id()
        
        # Phase 5.4: Expanded Triggers for construction loop
        if msg_lower.startswith("variation:") or "variation" in msg_lower:
            async for chunk in self._run_generic_construction_loop("variation", message, trace_id):
                yield chunk
            return
        elif msg_lower.startswith("rfi:") or "rfi" in msg_lower:
            async for chunk in self._run_generic_construction_loop("rfi", message, trace_id):
                yield chunk
            return
        elif msg_lower.startswith("delay:") or any(k in msg_lower for k in ["delay", "late", "behind"]):
            async for chunk in self._run_generic_construction_loop("delay", message, trace_id):
                yield chunk
            return
        elif any(k in msg_lower for k in ["defect:", "site issue:", "shortage", "short", "broken", "fail"]):
            async for chunk in self._run_generic_construction_loop("site_issue", message, trace_id):
                yield chunk
            return
        
        agent_keys = self._route_message(message)
        print(f"[ORCHESTRATOR] Assigned agents: {agent_keys}")
        self.conversation_history.append(HumanMessage(content=message))
        full_responses = {}
        for key in agent_keys:
            agent = AGENTS.get(key)
            if not agent: continue
            agent_name = agent['name'].upper()
            full_responses[key] = ""
            yield f"data: [{agent_name}] START\n\n"
            messages = [SystemMessage(content=PromptBuilder.build_system_prompt(agent, GovernanceEngine().constitution["laws"], GovernanceEngine().mission["mission"], execution_mode=False))]
            for ctx in self.conversation_history[-6:]: messages.append(ctx)
            messages.append(HumanMessage(content=message))
            active_llm = agent["llm"]
            async for chunk in active_llm.astream(messages):
                token_text = self._normalize_model_content(chunk.content)
                if token_text:
                    full_responses[key] += token_text
                    yield self._format_sse(f"{agent_name}:", token_text)
            yield f"data: [{agent_name}] END\n\n"
        combined_response_str = "\n\n".join([f"[{AGENTS[k]['name']}]: {v}" for k, v in full_responses.items()])
        self.conversation_history.append(AIMessage(content=combined_response_str))

    async def _run_generic_construction_loop(self, scenario_type: str, user_input: str, trace_id: str) -> Generator[str, None, None]:
        scenario_label = scenario_type.upper()
        event_bus.emit_event("LOOP_STARTED", trace_id, scenario=scenario_type, metadata={"input": user_input})
        yield f"data: [ARIA] {self._construction_acknowledgement(scenario_type)}\n\n"
        yield f"data: [SYSTEM] Initiating {scenario_label} Loop... [Trace: {trace_id[:8]}]\n\n"
        
        risk_trend = get_risk_trend_from_events()
        trend_str = f"RISK TREND: {risk_trend['direction'].upper()} (last 5: {risk_trend['avg_5']}, last 10: {risk_trend['avg_10']})"
        yield f"data: [SYSTEM] Current Project Health: {trend_str}\n\n"

        sanitised = sanitise_construction_input(scenario_type, user_input)
        if not sanitised.valid:
            event_bus.emit_event("INPUT_INVALIDATED", trace_id, agent_id="SYSTEM", scenario=scenario_type, metadata={"status": sanitised.status, "reason": sanitised.reason})
            yield f"data: [SYSTEM] INPUT VALIDATION FAILED: {sanitised.reason}\n\n"
            return

        cost, days = sanitised.cost, sanitised.days
        risk_score = calculate_risk_score(scenario_type, cost, days, user_input)
        yield f"data: [SYSTEM] Calculated Risk Score: {risk_score}\n\n"
        
        memory = get_relevant_memory(scenario_type, limit=5)
        governance_flags = evaluate_governance(scenario_type, cost, days, risk_score)
        owen_briefing = self.owen_engine.generate_intelligence_briefing(scenario_type, query_text=user_input)
        owen_str = self.owen_engine.format_briefing_for_prompt(owen_briefing)
        yield f"data: [SYSTEM] Owen's Intelligence Briefing loaded for {scenario_label}.\n\n"
        yield f"data: [SYSTEM] Governance Flags: {len(governance_flags)} raised | Memory: {memory['count']} prior decisions loaded\n\n"

        from .logic.decision_finalizer import finalize_decision, compute_current_distrust_level
        from .logic import decision_cache
        
        _cache_penalty, _cache_dpi, _current_distrust_level = compute_current_distrust_level(scenario_type)
        _cache_context = decision_cache.build_cache_context(scenario_type=scenario_type, user_input=user_input, cost=cost, days=days, governance_flags=governance_flags)

        # === PHASE 2 ELI INTEGRATION ===
        from .logic.momentum_engine import analyze_momentum
        from .logic.eli_adapter_v1 import transform_signal_to_actions
        from .logic.task_queue import enqueue_logistics_task
        _momentum_signal = analyze_momentum(_cache_context, trace_id=trace_id)
        _logistics_actions = transform_signal_to_actions(_momentum_signal)
        _logistics_actions["trace_id"] = trace_id
        _logistics_actions["momentum_signal"] = _momentum_signal
        _task_id = enqueue_logistics_task(_logistics_actions)
        yield f"data: [SYSTEM] Eli Logistics Intent Generated: {_logistics_actions['strategy']} (Ref: {_task_id})\n\n"

        _cached_finalized, _cache_outcome = decision_cache.cache_get(_cache_context, governance_flags=governance_flags, current_distrust_level=_current_distrust_level, trace_id=trace_id, scenario_type=scenario_type)
        served_from_cache = _cached_finalized is not None

        if served_from_cache:
            yield f"data: [SYSTEM] ⚡ Decision served from cache (CACHE_HIT) — skipping Nadia → Aria.\n\n"
            finalized = _cached_finalized
            decision_data = {"decision": finalized.final_decision, "justification": finalized.final_justification, "confidence_score": finalized.confidence_score, "impact": {"cost": cost, "days": days, "risk_delta": 0}}
            plan_raw, impl_plan_raw, critique_raw = "", "", ""
        else:
            nadia_context = f"SCENARIO TYPE: {scenario_label}\nPROJECT HEALTH: {trend_str}\n{format_flags_for_agents(governance_flags)}\n{memory['formatted']}\n\n{owen_str}"
            yield f"data: [NADIA] START\n\n"
            plan_raw, _, _ = await self._execute_contract_turn("nadia", build_plan_v1_system_prompt, user_input, "plan_v1", execution_context=nadia_context, trace_id=trace_id)
            yield self._format_sse("NADIA:", plan_raw); yield f"data: [NADIA] END\n\n"

            tucker_context = f"SCENARIO TYPE: {scenario_label}\nNADIA'S PLAN: {plan_raw}\n\n{owen_str}"
            yield f"data: [TUCKER] START\n\n"
            impl_plan_raw, _, _ = await self._execute_contract_turn("tucker", build_implementation_plan_v1_system_prompt, user_input, "implementation_plan_v1", execution_context=tucker_context, trace_id=trace_id)
            yield self._format_sse("TUCKER:", impl_plan_raw); yield f"data: [TUCKER] END\n\n"

            critique_context = f"SCENARIO TYPE: {scenario_label}\nPROJECT HEALTH: {trend_str}\n{format_flags_for_agents(governance_flags)}\n\n{owen_str}"
            yield f"data: [WALL-E] START\n\n"
            critique_raw, _, _ = await self._execute_contract_turn("wall-e", build_critique_v1_system_prompt, f"Proposed Plan: {plan_raw}\nImplementation Plan: {impl_plan_raw}", "critique_v1", execution_context=critique_context, trace_id=trace_id)
            yield self._format_sse("WALL-E:", critique_raw); yield f"data: [WALL-E] END\n\n"

            aria_context = f"SCENARIO TYPE: {scenario_label}\nRISK SCORE: {risk_score}\nPROJECT HEALTH: {trend_str}\n{format_flags_for_agents(governance_flags)}\n{memory['formatted']}\n\n{owen_str}\nWALL-E CRITIQUE: {critique_raw}"
            yield f"data: [ARIA] START\n\n"
            decision_raw, decision_valid, decision_error_reason = await self._execute_contract_turn("aria", build_decision_v1_system_prompt, f"Request: {user_input}\nNadia's Plan: {plan_raw}\nTucker's Plan: {impl_plan_raw}", "decision_v1", execution_context=aria_context, trace_id=trace_id)
            yield self._format_sse("ARIA:", decision_raw); yield f"data: [ARIA] END\n\n"

            decision_data = OutputContract()._parse_json_object(decision_raw)
            finalized = finalize_decision(decision_data=decision_data or {}, decision_valid=decision_valid, decision_error_reason=decision_error_reason, risk_score=risk_score, governance_flags=governance_flags, critique_data=OutputContract()._parse_json_object(critique_raw), memory_count=memory["count"], trace_id=trace_id, scenario_type=scenario_type, momentum_signal=_momentum_signal, outcome_score=0, user_input=user_input)
            decision_cache.cache_put(_cache_context, finalized, trace_id=trace_id, scenario_type=scenario_type)

        yield f"data: [JENNY] START\n\n"
        email_raw, _, _ = await self._execute_contract_turn("jenny", build_email_draft_v1_system_prompt, f"Decision made: {finalized.final_decision}\nJustification: {finalized.final_justification}", "email_draft_v1", trace_id=trace_id)
        yield self._format_sse("JENNY:", email_raw); yield f"data: [JENNY] END\n\n"

        email_data = OutputContract()._parse_json_object(email_raw) or {}
        actions_array = [{"type": "gmail_draft", "priority": "high", "payload": email_data}] if finalized.final_decision == "APPROVE" else [{"type": "audit_log", "reason": "record escalation"}]
        
        # === CONFIDENCE & SATURATION GATE ENFORCEMENT ===
        if finalized.gate_action == "SUPPRESS":
            reason = "saturation_limit" if finalized.saturation_status != "PASS" else "low_confidence"
            yield f"data: [SYSTEM] 🛑 ACTION SUPPRESSED: {reason.replace('_', ' ').title()} ({finalized.confidence_adjusted:.2f}). No proposal created.\n\n"
            event_bus.emit_event("ACTION_SUPPRESSED", trace_id, agent_id="SYSTEM", scenario=scenario_type, metadata={"reason": reason, "confidence": finalized.confidence_adjusted, "saturation_status": finalized.saturation_status})
            return

        requires_approval = True
        shadow_mode_active = os.getenv("AGENTS_SHADOW_MODE", "true").lower() == "true"
        
        if finalized.gate_action == "AUTO_ACT":
            if shadow_mode_active:
                yield f"data: [SYSTEM] 🛡️ SHADOW MODE: Decision is AUTO-ELIGIBLE ({finalized.confidence_adjusted:.2f}) but human approval forced for validation.\n\n"
                requires_approval = True
            else:
                yield f"data: [SYSTEM] ⚡ AUTO-ACT: High confidence decision ({finalized.confidence_adjusted:.2f}). Proceeding to preflight.\n\n"
                requires_approval = False

        action_intent = {
            "action": "operator_bundle", "agent_id": "system", "parameters": {"decision": finalized.final_decision, "confidence": finalized.confidence_score, "actions": actions_array},
            "trace_id": trace_id, "requires_approval": requires_approval, "status": "pending",
            "metadata": {
                "scenario": scenario_type, 
                "risk_score": risk_score, 
                "final_decision": finalized.final_decision, 
                "final_justification": finalized.final_justification,
                "governance_flags": finalized.governance_flags,
                "owen_briefing": owen_briefing,
                "why": finalized.why,
                "shadow_mode": shadow_mode_active,
                "auto_eligible": finalized.gate_action == "AUTO_ACT",
                "risk_level": finalized.risk_level,
                "gate_action": finalized.gate_action
            }
        }
        from . import preflight_validator as firewall
        request = firewall.create_or_get_request(action_intent=action_intent)
        yield f"data: [SYSTEM] PROPOSAL CREATED. Request ID: {request['request_id']}\n\n"

        yield f"data: [WALL-E] START\n\n"
        audit_raw, _, _ = await self._execute_contract_turn("wall-e", build_audit_log_v1_system_prompt, f"Decision: {finalized.final_decision}", "audit_log_v1", trace_id=trace_id)
        ConstructionOperator.log_to_sentinel(f"{scenario_label}_LOOP", "WALL-E", user_input, audit_raw)
        yield self._format_sse("WALL-E:", audit_raw); yield f"data: [WALL-E] END\n\n"
        
        event_bus.emit_event("LOOP_COMPLETE", trace_id, scenario=scenario_type, metadata={"status": "awaiting_approval", "request_id": request['request_id']})
