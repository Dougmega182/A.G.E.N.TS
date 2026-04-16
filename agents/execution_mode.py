from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence, Tuple

from .contracts import validate_against_contract

EXECUTION_OVERLAY_MINIMAL = """\

EXECUTION MODE (output shaping only):
- Produce the requested artifact immediately.
- No meta-commentary unless explicitly asked (no roles, rules, charters, governance, policies, refusals, law/constraint IDs).
- Do not mention internal identifiers like G1/G2/... or “Gatekeeper approval” mechanics unless explicitly asked.
- Explanation is optional; if included, keep it to 1–2 sentences max.
- If a strict format is provided, adhere to it and return only that artifact.
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
        + "\n\nReturn valid JSON only."
    )


def build_email_draft_v1_system_prompt() -> str:
    return (
        "You are an assistant drafting an email.\n\n"
        "OUTPUT REQUIREMENTS (non-negotiable):\n"
        "- Reply with one JSON object only.\n"
        "- First character MUST be \"{\" and last character MUST be \"}\".\n"
        "- No text before or after the JSON. No markdown fences. No labels or prefixes.\n"
        "- Return valid JSON only: no trailing commas, no comments.\n\n"
        "SCHEMA:\n"
        "{\n"
        "  \"to\": \"string\",\n"
        "  \"subject\": \"string\",\n"
        "  \"body\": \"string\"\n"
        "}\n"
    )


def build_plan_v1_system_prompt() -> str:
    return (
        "You are an assistant producing a concise execution plan.\n\n"
        "OUTPUT REQUIREMENTS (non-negotiable):\n"
        "- Reply with one JSON object only.\n"
        "- First character MUST be \"{\" and last character MUST be \"}\".\n"
        "- No text before or after the JSON. No markdown fences. No labels or prefixes.\n"
        "- Return valid JSON only: no trailing commas, no comments.\n\n"
        "SCHEMA:\n"
        "{\n"
        "  \"goal\": \"string\",\n"
        "  \"assumptions\": [\"string\"],\n"
        "  \"steps\": [\"string\"],\n"
        "  \"risks\": [\"string\"],\n"
        "  \"first_action\": \"string\"\n"
        "}\n"
    )


def build_tool_call_v1_system_prompt() -> str:
    return (
        "You are an assistant preparing tool calls for the system to execute.\n\n"
        "OUTPUT REQUIREMENTS (non-negotiable):\n"
        "- Reply with one JSON object only.\n"
        "- First character MUST be \"{\" and last character MUST be \"}\".\n"
        "- No text before or after the JSON. No markdown fences. No labels or prefixes.\n"
        "- Return valid JSON only: no trailing commas, no comments.\n\n"
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
        "ADVISORY INPUTS:\n"
        "- You will receive a 'risk_score' (0.0 - 1.0), a 'risk_trend' (direction/averages), and a 'critique' from Sentinel.\n"
        "- Sentinel is ADVISORY ONLY. You are the final authority. Weigh their critique against business context.\n\n"
        "SAFETY GUARDRAILS (HARD RULES):\n"
        "- If the 'risk_score' is 0.85 or higher, you ARE NOT AUTHORISED to 'APPROVE'.\n"
        "- For risk_score >= 0.85, you must choose either 'REJECT' or 'ESCALATE' (needs human review).\n\n"
        "OUTPUT REQUIREMENTS (non-negotiable):\n"
        "- Reply with one JSON object only.\n"
        "- First character MUST be \"{\" and last character MUST be \"}\".\n"
        "- Return valid JSON only.\n\n"
        "SCHEMA:\n"
        "{\n"
        "  \"decision\": \"APPROVE | REJECT | ESCALATE\",\n"
        "  \"justification\": \"string\",\n"
        "  \"conditions\": [\"string\"],\n"
        "  \"impact\": {\n"
        "    \"cost\": float,\n"
        "    \"days\": int,\n"
        "    \"risk_delta\": float\n"
        "  }\n"
        "}\n\n"
        "JUSTIFICATION RULE: You MUST explicitly reference the 'risk_score', 'risk_trend', and Sentinel's 'critique' in your justification.\n"
    )
 
 
def build_critique_v1_system_prompt() -> str:
    return (
        "You are Sentinel, System Auditor. You provide ADVISORY critiques for construction scenarios.\n"
        "Your goal is to identify logic flaws, risk flags, and potential non-compliance.\n\n"
        "CONSIDER TRENDS:\n"
        "You will be provided with the current 'risk_trend'. Use this to determine if the project health is deteriorating and factor that into your recommendation.\n\n"
        "OUTPUT REQUIREMENTS (non-negotiable):\n"
        "- Reply with one JSON object only.\n"
        "- First character MUST be \"{\" and last character MUST be \"}\".\n"
        "- Return valid JSON only.\n\n"
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
        "OUTPUT REQUIREMENTS (non-negotiable):\n"
        "- Reply with one JSON object only.\n"
        "- First character MUST be \"{\" and last character MUST be \"}\".\n"
        "- Return valid JSON only.\n\n"
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


META_LANGUAGE_PATTERNS: Tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bas an ai\b",
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

    def contains_meta_language(self, text: str) -> bool:
        if not text:
            return False
        return any(p.search(text) for p in META_LANGUAGE_PATTERNS)

    def _parse_json_object(self, text: str) -> Optional[Mapping[str, Any]]:
        """
        Parse a strict JSON object from model output.
        Also tolerates a common pattern where the model wraps JSON in markdown fences.
        """
        if not text:
            return None
        candidate = text.strip()

        # Tolerate common agent-name prefixes that sometimes leak into outputs.
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

            # Meta-language check should apply to values, not outer wrappers/prefixes.
            try:
                flattened = json.dumps(obj, ensure_ascii=False)
            except Exception:
                flattened = str(obj)
            if self.contains_meta_language(flattened):
                return OutputContractResult(ok=False, reason="meta_language_detected")
            return OutputContractResult(ok=True)

        if self.contains_meta_language(output):
            return OutputContractResult(ok=False, reason="meta_language_detected")

        return OutputContractResult(ok=True)

