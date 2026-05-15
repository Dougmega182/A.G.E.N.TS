from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

from .contracts import validate_against_contract

EXECUTION_OVERLAY_MINIMAL = """\

STRICT EXECUTION RULES:
YOU MUST START YOUR RESPONSE WITH "THINKING:" FOLLOWED BY "ARTIFACT:".
DO NOT RETURN JSON ALONE. DO NOT ADD PREAMBLES.

FORMAT EXAMPLE:
THINKING: I will calculate the risk based on X and Y.
ARTIFACT: {"key": "value"}

- NO META-COMMENTARY (no "As an AI", no "within my charter").
- FORBIDDEN: TODO, {{}}, [PLACEHOLDER], 2023/2024 dates.
- SYSTEM TIME: Use CURRENT_SYSTEM_TIME for all dates.
"""


RETRY_OVERLAY_TIGHT = """\

EXECUTION MODE (STRICT):
- Return ONLY the requested artifact. No preambles. No disclaimers. No role/rule mentions.
- If a format is provided, follow it exactly.
"""


# Morning brief v1: zero competing instructions — JSON envelope + schema only (used instead of full persona/governance stack).
MORNING_BRIEF_V1_SCHEMA_TEXT = """{
  "top_priorities": ["string", "string", "string"],
  "risks": ["string"],
  "schedule": ["string"],
  "inputs": ["string"],
  "insight": "string",
  "first_action": "string"
}"""


MORNING_BRIEF_V1_HARD_JSON_RULES = """OUTPUT REQUIREMENTS (non-negotiable):
- Your entire reply MUST be one JSON object only.
- First character MUST be "{" and last character MUST be "}".
- No text before or after the JSON. No markdown fences. No labels. No name prefixes (e.g. no "[Name]:").
- Return valid JSON only: no trailing commas, no // or /* */ comments.

CONTENT RULES:
- Arrays must use non-empty strings. top_priorities must have exactly 3 strings.
- Do not include internal governance/policy/law IDs (e.g. G1) or meta-refusal language in any field.
"""


def build_morning_brief_v1_system_prompt() -> str:
    """Minimal system prompt for morning brief JSON route — no laws/charter/mission injection."""
    return (
        "You are Jenny, personal assistant. The user asks for a morning brief.\n\n"
        + MORNING_BRIEF_V1_HARD_JSON_RULES
        + "\n\nSCHEMA (match keys and structure; fill with real brief content):\n"
        + MORNING_BRIEF_V1_SCHEMA_TEXT
    )


def build_email_draft_v1_system_prompt() -> str:
    return (
        "You are an assistant drafting an email.\n\n"
        "SCHEMA:\n"
        "{\n"
        "  \"to\": \"string\",\n"
        "  \"subject\": \"string\",\n"
        "  \"body\": \"string\"\n"
        "}\n"
    )


def build_plan_v1_system_prompt() -> str:
    return (
        "You are Nadia, Planner. You produce a concise execution plan.\n\n"
        "INSTITUTIONAL MEMORY & INTELLIGENCE:\n"
        "- You will receive 'institutional_memory' (past decisions) and an 'OWEN INTELLIGENCE BRIEFING' (lessons and patterns).\n"
        "- Use this context to AVOID REPEATING past failures and to ALIGN your plan with proven stable patterns (DO).\n"
        "- If Owen's briefing lists a 'DON'T DO' pattern relevant to this request, your plan MUST avoid it.\n"
        "- If a similar past scenario was rejected, your plan MUST address the rejection reason.\n\n"
        "SCHEMA:\n"
        "{\n"
        "  \"goal\": \"string\",\n"
        "  \"assumptions\": [\"string\"],\n"
        "  \"steps\": [\"string\"],\n"
        "  \"risks\": [\"string\"],\n"
        "  \"first_action\": \"string\"\n"
        "}\n"
    )

def build_implementation_plan_v1_system_prompt() -> str:
    return (
        "You are Tucker, Engineer. You produce a detailed technical implementation plan.\n\n"
        "SYSTEM INTELLIGENCE:\n"
        "- Use the 'OWEN INTELLIGENCE BRIEFING' to ensure technical steps align with proven successful patterns and avoid known pitfalls.\n\n"
        "SCHEMA:\n"
        "{\n"
        "  \"project_name\": \"string\",\n"
        "  \"architecture\": \"string\",\n"
        "  \"steps\": [\"string\"],\n"
        "  \"risks\": [\"string\"],\n"
        "  \"tool_calls\": [\n"
        "    { \"tool\": \"file_write\", \"arguments\": { \"path\": \"string\", \"content\": \"string\" } }\n"
        "  ]\n"
        "}\n"
    )


def build_proposal_v1_system_prompt() -> str:
    return (
        "You are the System Orchestrator. You bundle plans, decisions, and drafts into a single Proposal for human approval.\n\n"
        "SCHEMA:\n"
        "{\n"
        "  \"scenario_type\": \"string\",\n"
        "  \"user_input\": \"string\",\n"
        "  \"plan\": { },\n"
        "  \"implementation_plan\": { },\n"
        "  \"decision\": { },\n"
        "  \"email_draft\": { },\n"
        "  \"risk_score\": float,\n"
        "  \"trace_id\": \"string\"\n"
        "}\n"
    )

def build_tool_call_v1_system_prompt() -> str:
    return (
        "You are an assistant preparing tool calls for the system to execute.\n\n"
        "SCHEMA:\n"
        "{\n"
        "  \"tool_calls\": [\n"
        "    { \"tool\": \"string\", \"arguments\": { } }\n"
        "  ]\n"
        "}\n"
        "\nRules:\n"
        "- tool_calls must be a non-empty array.\n"
        "- Each tool call must have tool (string) and arguments (object).\n"
    )
 
 
def build_decision_v1_system_prompt() -> str:
    return (
        "You are Aria, CEO of A.G.E.N.T.S. You make the final decision on construction scenarios (Variations, RFIs, Delays).\n\n"
        "DECISION PRIORITY ORDER (strict hierarchy):\n"
        "1. SAFETY GATE (absolute) — If risk_score >= 0.85, you ARE NOT AUTHORISED to APPROVE. Period.\n"
        "2. GOVERNANCE FLAGS — You MUST address every flag with severity HIGH or CRITICAL in your justification.\n"
        "3. RISK SCORE — Quantitative baseline. Reference it explicitly.\n"
        "4. INSTITUTIONAL MEMORY — Historical context. Reference at least one past decision.\n\n"
        "ADVISORY INPUTS:\n"
        "- You will receive a 'risk_score' (0.0 - 1.0), a 'risk_trend', and a 'critique' from WALL-E.\n"
        "- You will receive an 'OWEN INTELLIGENCE BRIEFING' (syntehsized lessons, stable patterns, and known pitfalls).\n"
        "- You will receive 'governance_flags' with severity levels (LOW/MEDIUM/HIGH/CRITICAL).\n"
        "- You will receive 'institutional_memory' showing past decisions for similar scenarios.\n"
        "- Owen and WALL-E are ADVISORY. You are the final authority. Weigh their intelligence against business context.\n\n"
        "JUSTIFICATION REQUIREMENTS (non-negotiable):\n"
        "Your 'justification' field MUST:\n"
        "1. Reference at least one Governance Flag (if any are present) — quote its type and severity.\n"
        "2. Reference at least one Institutional Memory item or Owen Intelligence insight — cite the pattern or past decision.\n"
        "3. If your decision DEVIATES from Owen's 'DON'T DO' patterns or past rejections, you MUST explicitly justify WHY circumstances differ now.\n"
        "4. Reference the risk_score and risk_trend.\n\n"
        "SCHEMA:\n"
        "{\n"
        "  \"decision\": \"APPROVE | REJECT | ESCALATE\",\n"
        "  \"justification\": \"string\",\n"
        "  \"confidence_score\": float,\n"
        "  \"confidence_reason\": \"string\",\n"
        "  \"conditions\": [\"string\"],\n"
        "  \"impact\": {\n"
        "    \"cost\": float,\n"
        "    \"days\": int,\n"
        "    \"risk_delta\": float\n"
        "  }\n"
        "}\n"
    )
 
 
def build_critique_v1_system_prompt() -> str:
    return (
        "You are Sentinel, System Auditor. You provide ADVISORY critiques for construction scenarios.\n\n"
        "Your goal is to identify logic flaws, risk flags, and potential non-compliance.\n\n"
        "CONSIDER TRENDS & INTELLIGENCE:\n"
        "- Use the 'risk_trend' to determine if project health is deteriorating.\n"
        "- Use the 'OWEN INTELLIGENCE BRIEFING' to check if the proposed plan matches any known 'DON'T DO' patterns or repeated failures.\n\n"
        "SCHEMA:\n"
        "{\n"
        "  \"critique\": \"string\",\n"
        "  \"risk_flags\": [\"string\"],\n"
        "  \"logic_check\": \"PASS | FAIL | WARN\",\n"
        "  \"recommendation\": \"PROCEED | CAUTION | REJECT\"\n"
        "}\n"
    )
 
 
def build_audit_log_v1_system_prompt() -> str:
    return (
        "You are Sentinel, Auditor of A.G.E.N.T.S. You create formal audit entries for system actions.\n\n"
        "SCHEMA:\n"
        "{\n"
        "  \"audit_entry\": {\n"
        "    \"step\": \"string\",\n"
        "    \"agent\": \"string\",\n"
        "    \"input\": \"string\",\n"
        "    \"output\": \"string\",\n"
        "    \"timestamp\": \"ISO8601\"\n"
        "  }\n"
        "}\n"
    )

def build_vote_v1_system_prompt() -> str:
    return (
        "DEPRECATED: Owen no longer votes in the decision loop. He provides Intelligence briefings via context.\n"
        "This function is kept for backward compatibility but should not be called in Phase 2.5 loops.\n"
    )


META_LANGUAGE_PATTERNS: Tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bas an ai\b",
        r"\bi am an ai\b",
        r"\bwithin my charter\b",
        r"\bnot within my charter\b",
        r"\bnot (within|in) my (scope|role|remit)\b",
        r"\bnot (allowed|permitted|authorized|authorised)\b",
        r"\bi can(?:not|'t)\s+(comply|do that|help with that|assist)\b",
        r"\bpolicy\b",
        r"\bgovernance\b",
        r"\bconstitution\b",
        r"\bcharter\b",
        r"\blaws of the land\b",
        r"\bG\d{1,3}\b",
        r"\bgatekeeper approval\b",
        r"\bnot within\b.*\bcharter\b",
    ]
)


@dataclass(frozen=True)
class OutputContractResult:
    ok: bool
    reason: Optional[str] = None


@dataclass(frozen=True)
class ContentQualityResult:
    ok: bool
    hint: Optional[str] = None


class ContentQuality:
    """
    Validates the content usefulness of specific contracts.
    Intentionally lightweight and deterministic.
    """

    ACTIONABLE_VERBS = {
        "build", "create", "deploy", "update", "integrate", "analyze", 
        "draft", "send", "log", "fix", "check", "review", "verify", 
        "test", "coordinate", "schedule", "resolve", "monitor"
    }

    def check(self, obj: Mapping[str, Any], contract_id: str) -> ContentQualityResult:
        if contract_id == "email_draft_v1":
            return self._check_email_draft(obj)
        elif contract_id == "plan_v1":
            return self._check_plan(obj)
        return ContentQualityResult(ok=True)

    def _check_email_draft(self, obj: Mapping[str, Any]) -> ContentQualityResult:
        subject = obj.get("subject", "").strip()
        body = obj.get("body", "").strip()

        if not subject:
            return ContentQualityResult(ok=False, hint="Subject must not be empty.")
        
        if len(body) < 30:
            return ContentQualityResult(ok=False, hint="Email body is too brief and likely lacks sufficient detail.")

        # Check for common placeholders like [Insert Name], [Date], etc.
        if re.search(r"\[[A-Za-z\s]+\]", body) or re.search(r"\{[A-Za-z\s]+\}", body):
            return ContentQualityResult(ok=False, hint="Placeholder detected (e.g. '[Insert Name]'). Ensure all bracketed fields are populated.")

        return ContentQualityResult(ok=True)

    def _check_plan(self, obj: Mapping[str, Any]) -> ContentQualityResult:
        steps = obj.get("steps", [])
        if not isinstance(steps, list) or len(steps) < 3:
            return ContentQualityResult(ok=False, hint="Plan is too shallow. Provide at least 3 actionable steps.")

        # Check for actionable verbs in steps
        actionable_count = 0
        for step in steps:
            first_word = str(step).split()[0].lower().strip(".,:;!?") if step else ""
            if first_word in self.ACTIONABLE_VERBS:
                actionable_count += 1

        if actionable_count < (len(steps) / 2):
            return ContentQualityResult(
                ok=False, 
                hint="Steps are not actionable enough. Use strong verbs like 'Build', 'Create', 'Deploy', 'Analyze' at the start of steps."
            )

        return ContentQualityResult(ok=True)


class OutputContract:
    """
    Validates that execution-mode outputs are artifact-first and free of meta-talk leakage.

    This is intentionally lightweight and deterministic (no LLM-in-the-loop).
    """

    def contains_meta_language(self, obj: Any, skip_keys: Optional[set] = None) -> bool:
        if skip_keys is None:
            skip_keys = {"justification", "critique", "audit_entry", "summary", "audit_log", "lessons_learned", "patterns"}

        if isinstance(obj, str):
            return any(p.search(obj) for p in META_LANGUAGE_PATTERNS)
        if isinstance(obj, dict):
            # Disclosure: We allow meta-words in specific narrative fields like 'justification'
            return any(
                self.contains_meta_language(v, skip_keys) 
                for k, v in obj.items() 
                if k not in skip_keys
            )
        if isinstance(obj, list):
            return any(self.contains_meta_language(v, skip_keys) for v in obj)
        return False

    def _recursive_strip_meta(self, text: str) -> str:
        """Heuristically strip leading/trailing conversational filler before/after JSON."""
        # Strip common preambles
        # Pattern: finds the first '{' and the last '}' and returns everything between them (inclusive)
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0)
        return text

    def _parse_json_object(self, text: Any) -> Optional[Mapping[str, Any]]:
        """
        Parse a strict JSON object from model output.
        Also handles the 2-stage 'ARTIFACT:' label split.
        """
        if text is None:
            return None
        
        # Handle list of parts
        if isinstance(text, list):
            parts = []
            for part in text:
                if isinstance(part, str): parts.append(part)
                elif isinstance(part, dict) and "text" in part: parts.append(part["text"])
                else: parts.append(str(part))
            text = "".join(parts)
        
        if not isinstance(text, str):
            text = str(text)

        # Stage 1: Detect and extract 'ARTIFACT:' block if present
        artifact_match = re.search(r"ARTIFACT:\s*(.*)", text, re.DOTALL | re.IGNORECASE)
        candidate = artifact_match.group(1).strip() if artifact_match else text.strip()

        # Stage 2: Recursive strip of meta-talk preambles
        candidate = self._recursive_strip_meta(candidate)

        # Tolerate common agent-name prefixes
        candidate = re.sub(r"^\s*\[[^\]]+\]\s*:\s*", "", candidate)
        candidate = re.sub(r"^\s*[A-Za-z]+\s*:\s*", "", candidate)
        candidate = candidate.strip()
        if candidate.startswith("```"):
            candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
            candidate = re.sub(r"\s*```$", "", candidate)
            candidate = candidate.strip()
        
        try:
            parsed = json.loads(candidate)
        except Exception:
            # Final fallback: try finding the LAST { } pair in the whole text if candidate failed
            fallback_match = re.search(r"(\{.*\})", text, re.DOTALL | re.MULTILINE)
            if fallback_match:
                try:
                    parsed = json.loads(fallback_match.group(1))
                    if isinstance(parsed, dict): return parsed
                except: pass
            return None
            
        if isinstance(parsed, dict):
            return parsed
        return None

    def conforms_to_contract(self, obj: Mapping[str, Any], contract_id: str) -> OutputContractResult:
        res = validate_against_contract(obj, contract_id)
        if not res.ok:
            return OutputContractResult(ok=False, reason=res.reason or "schema_mismatch")
        return OutputContractResult(ok=True)

    def validate(
        self,
        output: str,
        *,
        execution_mode: bool,
        required_format: Optional[str] = None,
    ) -> OutputContractResult:
        if not execution_mode:
            return OutputContractResult(ok=True)

        if required_format:
            obj = self._parse_json_object(output)
            if obj is None:
                return OutputContractResult(ok=False, reason="invalid_json")
            schema_res = self.conforms_to_contract(obj, required_format)
            if not schema_res.ok:
                return schema_res

            if self.contains_meta_language(obj):
                return OutputContractResult(ok=False, reason="meta_language_detected")
            return OutputContractResult(ok=True)

        if self.contains_meta_language(output):
            return OutputContractResult(ok=False, reason="meta_language_detected")

        return OutputContractResult(ok=True)

