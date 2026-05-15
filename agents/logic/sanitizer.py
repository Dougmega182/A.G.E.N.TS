import re
import json
from typing import Any, Dict, List, Optional, Tuple, Mapping

# Patterns that indicate internal cognition or placeholders leaking into contracts
FORBIDDEN_PATTERNS = [
    re.compile(r"\{\{.*?\}\}"),         # {{placeholder}}
    re.compile(r"\[[A-Z_\s]+\]"),       # [PLACEHOLDER]
    re.compile(r"\[Insert.*?\]", re.I), # [Insert Name]
    re.compile(r"\bTODO\b"),            # TODO
    re.compile(r"\bFIXME\b"),           # FIXME
    re.compile(r"\blorem ipsum\b", re.I), # Lorem ipsum
    re.compile(r"\bmeta\b", re.I),      # Avoid meta-talk
    re.compile(r"\bplaceholder\b", re.I),
]

# Narrative fields where some meta-talk is tolerated (but still discouraged)
NARRATIVE_FIELDS = {"justification", "critique", "audit_entry", "summary", "audit_log", "lessons_learned", "patterns", "body"}

class ContractSanitizer:
    """
    Hard output sanitizer for agent contracts.
    Implements: validate -> strip -> revalidate -> block if fail.
    """

    @staticmethod
    def sanitize_narrative(text: str) -> str:
        """Surgically remove common cognitive leaks from narrative strings."""
        if not text:
            return ""

        # 1. Remove leading/trailing conversational filler
        text = re.sub(r"^(Here is the|Based on my|As requested, I have|Sure, I can help|Understood\.)\s*", "", text, flags=re.I)

        # 2. Strip bracketed meta-talk (even if it has trailing punctuation)
        text = re.sub(r"\s*\[Note:.*?\][.?!]?\s*$", "", text, flags=re.I | re.DOTALL)
        text = re.sub(r"\s*\(Note:.*?\)[.?!]?\s*$", "", text, flags=re.I | re.DOTALL)

        # 3. Strip common placeholders and markers
        text = re.sub(r"\[Insert.*?\]", "", text, flags=re.I)
        text = re.sub(r"\{\{.*?\}\}", "", text)
        text = re.sub(r"\bTODO\b", "", text)
        text = re.sub(r"\bFIXME\b", "", text)

        # 4. Aggressive Meta-Language Stripping
        meta_patterns = [
            r"within my charter", r"as an ai", r"as a system auditor", r"according to (my )?policy",
            r"according to (the )?constitution", r"law [gagnstp]\d+", r"governance constraint",
            r"mission objective", r"gatekeeper approval", r"system-forced", r"re-run decision turn"
        ]
        for p in meta_patterns:
            text = re.sub(rf"(?i)\b{p}\b[.?!]?\s*", "", text)

        return text.strip().replace("  ", " ")

    @staticmethod
    def apply_schema_defaults(obj: Any, contract_id: str) -> Any:
        """Auto-fill common missing fields to prevent trivial schema failures."""
        if not isinstance(obj, dict):
            return obj

        if contract_id == "email_draft_v1":
            if not obj.get("to"):
                obj["to"] = "site-manager@construction.com"
            if not obj.get("subject"):
                obj["subject"] = "System Notification: Action Required"
        elif contract_id == "plan_v1":
            if not obj.get("goal"): obj["goal"] = "General Site Maintenance / Resolution"
            if not obj.get("steps"): obj["steps"] = ["Review current site issue", "Coordinate with relevant trades", "Update world state"]
        elif contract_id == "audit_log_v1":
            if not obj.get("audit_entry"):
                obj["audit_entry"] = {"step": "SYSTEM_ACTION", "agent": "SYSTEM", "input": "N/A", "output": "Log entry auto-generated", "timestamp": "ISO8601"}

        return obj

    @staticmethod
    def contains_forbidden_artifacts(obj: Any, path: str = "") -> List[str]:
        """Detect placeholders or dev-talk in the contract object."""
        violations = []
        
        if isinstance(obj, str):
            for pattern in FORBIDDEN_PATTERNS:
                if pattern.search(obj):
                    violations.append(f"Forbidden pattern '{pattern.pattern}' in {path or 'root'}")
            
            year_match = re.search(r"\b202[34]\b", obj)
            if year_match:
                context_window = obj[max(0, year_match.start()-30):min(len(obj), year_match.end()+30)].lower()
                future_context = ["schedule", "will", "current", "today", "date", "now", "deadline", "due"]
                if any(kw in context_window for kw in future_context):
                    violations.append(f"Likely hallucinated current year (2023/2024) in future context: {path or 'root'}")

        elif isinstance(obj, dict):
            for k, v in obj.items():
                current_path = f"{path}.{k}" if path else k
                if k in NARRATIVE_FIELDS and isinstance(v, str):
                    if re.search(r"\{\{.*?\}\}", v) or re.search(r"\[[A-Z_\s]{3,}\]", v):
                        violations.append(f"Strict placeholder detected in narrative field: {current_path}")
                violations.extend(ContractSanitizer.contains_forbidden_artifacts(v, current_path))
        
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                violations.extend(ContractSanitizer.contains_forbidden_artifacts(item, f"{path}[{i}]"))
                
        return violations

    @classmethod
    def apply_surgical_repairs(cls, obj: Any) -> Any:
        """Attempt to auto-repair common discipline leaks."""
        if isinstance(obj, str):
            return cls.sanitize_narrative(obj)
        
        if isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                if k in NARRATIVE_FIELDS and isinstance(v, str):
                    new_dict[k] = cls.sanitize_narrative(v)
                else:
                    new_dict[k] = cls.apply_surgical_repairs(v)
            return new_dict
        
        if isinstance(obj, list):
            return [cls.apply_surgical_repairs(i) for i in obj]
        
        return obj

    @classmethod
    def process(cls, raw_text: str, contract_id: str) -> Tuple[Optional[Mapping[str, Any]], bool, bool, List[str]]:
        """
        Process an agent response through the discipline gate.
        Returns: (parsed_obj, success, repaired, list_of_violations)
        """
        # 1. Check for 2-stage structure
        has_thinking = "THINKING:" in raw_text.upper()
        has_artifact = "ARTIFACT:" in raw_text.upper()
        
        if not (has_thinking and has_artifact):
            return None, False, False, ["Missing mandatory 2-stage structure (THINKING: and ARTIFACT: blocks)"]

        # 2. Parse JSON block (the 'Delivery')
        artifact_blocks = re.findall(r"ARTIFACT:\s*(.*)", raw_text, re.DOTALL | re.IGNORECASE)
        if not artifact_blocks:
            return None, False, False, ["Could not extract ARTIFACT: block."]
        
        target_payload = artifact_blocks[-1].strip()
        
        from agents.execution_mode import OutputContract
        contract = OutputContract()
        obj = contract._parse_json_object(target_payload)
        
        if obj is None:
            return None, False, False, ["Invalid JSON structure in ARTIFACT: block."]

        # 3. Apply Schema Defaults (Auto-fill missing fields)
        obj = cls.apply_schema_defaults(obj, contract_id)

        # 4. Check for meta-language and placeholders
        repaired = False
        violations = cls.contains_forbidden_artifacts(obj)
        if violations or contract.contains_meta_language(obj):
            repaired_obj = cls.apply_surgical_repairs(obj)
            # Re-check
            remaining_violations = cls.contains_forbidden_artifacts(repaired_obj)
            if not remaining_violations and not contract.contains_meta_language(repaired_obj):
                return repaired_obj, True, True, []
            return repaired_obj, False, True, (remaining_violations or ["Persistent meta-language detected"])
            
        return obj, True, repaired, []
