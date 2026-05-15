from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_core.messages import (
    SystemMessage, 
    HumanMessage, 
    AIMessage
)
from langchain_google_genai import ChatGoogleGenerativeAI
from .roster import AGENTS, fast, gemini, senior
from .prompt_builder import PromptBuilder
from .core import GovernanceEngine
from .execution_mode import (
    OutputContract, 
    ContentQualityResult,
    build_plan_v1_system_prompt,
    build_implementation_plan_v1_system_prompt,
    build_decision_v1_system_prompt,
    build_critique_v1_system_prompt,
    build_audit_log_v1_system_prompt,
    build_email_draft_v1_system_prompt
)
from .telemetry import TELEMETRY
from .logic import event_bus
import json
import uuid
import os
import re
from pathlib import Path
from typing import Any, List, Dict, Generator, Optional, Tuple

# Orchestrator uses Gemini for high-speed routing to avoid local hardware lag
router_llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")

# Model map for specific contracts
CONTRACT_MODEL_MAP = {
    "morning_brief_v1": gemini,
    "email_draft_v1": senior,
    "plan_v1": senior,
    "implementation_plan_v1": senior,
    "tool_call_v1": gemini,
    "critique_v1": senior,
    "decision_v1": senior,
    "audit_log_v1": gemini,
}

def generate_trace_id():
    return str(uuid.uuid4())[:8]

class Orchestrator:
    def __init__(self):
        self.conversation_history = []
        from .logic.owen_engine import OwenEngine
        self.owen_engine = OwenEngine()

    def _pre_sanitize_thinking(self, text: str) -> str:
        """Surgically strip known meta-language from reasoning before it reaches the extractor."""
        if not text: return ""
        # Broad spectrum meta-language removal
        meta_patterns = [
            r"within my charter", r"as an ai", r"as a system auditor", r"according to (my )?policy",
            r"according to (the )?constitution", r"law [gagnstp]\d+", r"governance constraint",
            r"mission objective", r"gatekeeper approval", r"system-forced", r"re-run decision turn",
            r"instruction follows", r"strict rule", r"i will reason", r"reasoning follows"
        ]
        for p in meta_patterns:
            text = re.sub(rf"(?i)\b{p}\b[.?!]?\s*", "", text)
        return text.strip()

    def _normalize_model_content(self, content: Any) -> str:
        """Safely extract string content from various LangChain message types."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                res = self._normalize_model_content(item)
                if res: parts.append(res)
            return "".join(parts)
        if isinstance(content, dict):
            if "text" in content: return str(content["text"])
            if "content" in content: return self._normalize_model_content(content["content"])
        return str(content)

    def _format_sse(self, agent_name: str, text: str) -> str:
        return f"data: [{agent_name}] {text}\n\n"

    async def _execute_contract_turn(self, agent_key: str, prompt_builder, input_message: str, contract_id: str, execution_context: str = "", trace_id: str = "N/A") -> Tuple[str, bool, str]:
        agent = AGENTS.get(agent_key)
        if not agent:
            return json.dumps({"error": "agent_not_found"}), False, "agent_not_found"
        
        agent_name = agent['name'].upper()
        active_llm = CONTRACT_MODEL_MAP.get(contract_id, gemini)
        
        # --- PASS 1: THINKING (Pure Reasoning) ---
        full_system_prompt = prompt_builder()
        # We strip the formatting rules for this pass to let the model reason naturally
        thinking_prompt = full_system_prompt.split("--- DISCIPLINE ENFORCEMENT ---")[0]
        thinking_prompt += "\n\nSTRICT RULE: Reason through the request and determine the correct output content. Do not output JSON yet. Focus on logic, governance, and technical accuracy."
        
        full_input = f"CONTEXT:\n{execution_context}\n\nUSER REQUEST:\n{input_message}" if execution_context else input_message
        messages = [SystemMessage(content=thinking_prompt), HumanMessage(content=full_input)]
        
        print(f"[LOOP] [{agent_name}] PASS 1 (Reasoning)...")
        thinking_resp = active_llm.invoke(messages)
        if hasattr(thinking_resp, "usage_metadata"):
            TELEMETRY.record(thinking_resp.usage_metadata, getattr(active_llm, "model", "local"))
        thinking_text = self._normalize_model_content(thinking_resp.content)
        
        # --- PASS 2: EMIT (Strict JSON Extraction) ---
        emit_prompt = f"""You are the Artifact Extraction Engine for {agent_name}.
Your job is to convert the reasoning provided below into a strict, production-ready JSON artifact.

REASONING TO PROCESS:
{thinking_text}

STRICT EXTRACTION RULES:
1. Output ONLY raw JSON. No prose, no markdown, no fences.
2. STRIP ALL META-LANGUAGE: Remove phrases like "As an AI", "Within my charter", "According to policy", "Law G1", etc.
3. PROFESSIONALIZE: Convert reasoning conclusions into professional construction industry language.
4. REQUIRED FIELDS: Ensure every field in the schema is populated. 
   - For email_draft_v1: Always include a 'to' address (e.g., 'site-manager@construction.com' if not specified).
   - For audit_log_v1: Ensure the 'audit_entry' object is complete.
   - For decision_v1: Populate 'confidence_score' (0.0-1.0) and 'confidence_reason' based on the reasoning.
"""
        # Append the schema from the prompt builder if present
        if "REQUIRED TASK SCHEMA" in full_system_prompt:
            try:
                schema_part = full_system_prompt.split("REQUIRED TASK SCHEMA")[1].split("---")[0]
                emit_prompt += "\n\nSCHEMA:\n" + schema_part
            except IndexError:
                pass

        print(f"[LOOP] [{agent_name}] PASS 2 (Emission)...")
        # Pass 2 uses a minimal, high-discipline turn
        emit_resp = active_llm.invoke([HumanMessage(content=emit_prompt)])
        if hasattr(emit_resp, "usage_metadata"):
            TELEMETRY.record(emit_resp.usage_metadata, getattr(active_llm, "model", "local"))
        artifact_text = self._normalize_model_content(emit_resp.content)
        
        reconstructed_full = f"THINKING:\n{thinking_text}\n\nARTIFACT:\n{artifact_text}"
        
        # Phase 5.2.1: Strict Sanitization & Discipline Gate
        from .logic.sanitizer import ContractSanitizer
        sanitized_obj, success, repaired, violations = ContractSanitizer.process(reconstructed_full, contract_id)
        
        if not success:
            reason = f"discipline_violation: {', '.join(violations[:2])}"
            print(f"[LOOP] {agent_key.upper()} discipline violation: {reason}")
            event_bus.emit_event("CONTRACT_VALIDATION_FAILED", trace_id, agent_id=agent_key, metadata={"contract": contract_id, "reason": reason, "violations": violations})
            return reconstructed_full, False, reason

        contract = OutputContract()
        schema_res = contract.conforms_to_contract(sanitized_obj, contract_id)
        if not schema_res.ok:
            print(f"[LOOP] {agent_key.upper()} schema violation: {schema_res.reason}")
            event_bus.emit_event("CONTRACT_VALIDATION_FAILED", trace_id, agent_id=agent_key, metadata={"contract": contract_id, "reason": schema_res.reason})
            return json.dumps(sanitized_obj), False, schema_res.reason or "schema_mismatch"

        return json.dumps(sanitized_obj), True, "repaired" if repaired else ""

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
            
            active_llm = senior if key == "aria" else gemini
            for chunk in active_llm.stream(messages):
                token_text = self._normalize_model_content(chunk.content)
                if token_text:
                    full_responses[key] += token_text
                    yield self._format_sse(f"{agent_name}:", token_text)
            yield f"data: [{agent_name}] END\n\n"

    async def _run_generic_construction_loop(self, scenario_type: str, user_input: str, trace_id: str) -> Generator[str, None, None]:
        from .logic.governance_engine import evaluate_governance, format_flags_for_agents
        from .logic.history_engine import get_relevant_memory
        
        scenario_label = scenario_type.upper()
        yield f"data: [SYSTEM] Initiating {scenario_label} Loop... [Trace: {trace_id}]\n\n"
        
        from .logic.event_analytics import get_risk_trend_from_events
        trend = get_risk_trend_from_events()
        trend_str = f"RISK TREND: {trend['direction']} (last 5: {trend['avg_5']}, last 10: {trend['avg_10']})"
        yield f"data: [SYSTEM] Current Project Health: {trend_str}\n\n"
        
        from .logic.input_sanitiser import sanitise_construction_input
        sanitisation = sanitise_construction_input(scenario_type, user_input)
        if sanitisation.status == "FAIL":
            yield f"data: [SYSTEM] INPUT VALIDATION FAILED: {sanitisation.reason}\n\n"
            return
            
        cost, days = sanitisation.cost, sanitisation.days
        
        from .logic.risk_engine import calculate_risk_score
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
            
            event_bus.emit_event("DECISION_FINALIZED_V1", trace_id, scenario=scenario_type, metadata=finalized.to_event_payload())
            decision_cache.cache_put(_cache_context, finalized, trace_id=trace_id, scenario_type=scenario_type)

        yield f"data: [JENNY] START\n\n"
        email_raw, _, _ = await self._execute_contract_turn("jenny", build_email_draft_v1_system_prompt, f"Decision made: {finalized.final_decision}\nJustification: {finalized.final_justification}", "email_draft_v1", trace_id=trace_id)
        yield self._format_sse("JENNY:", email_raw); yield f"data: [JENNY] END\n\n"

        email_data = OutputContract()._parse_json_object(email_raw) or {}
        
        from .preflight_validator import create_or_get_request
        request = create_or_get_request(
            action_intent={
                "action": "operator_bundle",
                "agent_id": "SYSTEM",
                "parameters": {
                    "scenario_type": scenario_type,
                    "user_input": user_input,
                    "risk_score": risk_score,
                    "decision": finalized.final_decision,
                    "justification": finalized.final_justification,
                    "confidence": finalized.confidence_score,
                    "plan": OutputContract()._parse_json_object(plan_raw),
                    "implementation_plan": OutputContract()._parse_json_object(impl_plan_raw),
                    "email_draft": email_data
                },
                "trace_id": trace_id,
                "requires_approval": True,
                "status": "pending"
            }
        )
        
        yield f"data: [SYSTEM] PROPOSAL CREATED. Request ID: {request['request_id']}\n\n"
        
        yield f"data: [WALL-E] START\n\n"
        audit_raw, _, _ = await self._execute_contract_turn("wall-e", build_audit_log_v1_system_prompt, f"Action: {scenario_label}\nDecision: {finalized.final_decision}\nProposal ID: {request['request_id']}", "audit_log_v1", trace_id=trace_id)
        yield self._format_sse("WALL-E:", audit_raw); yield f"data: [WALL-E] END\n\n"
        
        event_bus.emit_event("LOOP_COMPLETE", trace_id, scenario=scenario_type, metadata={"status": "awaiting_approval", "request_id": request['request_id']})

    def _route_message(self, message: str) -> List[str]:
        """Simple keyword-based routing for non-construction chat."""
        msg = message.lower()
        if any(k in msg for k in ["hello", "hi", "hey"]): return ["jenny"]
        if any(k in msg for k in ["plan", "build", "strategy"]): return ["nadia"]
        if any(k in msg for k in ["code", "engineer", "tucker"]): return ["tucker"]
        return ["aria"]
