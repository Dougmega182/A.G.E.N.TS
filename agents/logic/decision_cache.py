"""
Decision Cache — Phase 5.1.5 Inference Caching Layer 1.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import event_bus, memory_db
from .decision_finalizer import FinalizedDecision

logger = logging.getLogger("agents.decision_cache")

# -------------------------------------------------------------------
# Contract constants
# -------------------------------------------------------------------

POLICY_VERSION = "v7"

DEFAULT_TTL_SECONDS = 48 * 3600
MIN_CACHE_CONFIDENCE = 0.7
BYPASS_DISTRUST_LEVELS = frozenset({"HIGH", "BLOCKED"})
COMPONENT_NAME = "orchestrator"

class BypassReason:
    CRITICAL_GOVERNANCE = "critical_governance"
    LOW_CONFIDENCE = "low_confidence"
    DISTRUST_HIGH = "distrust_high"
    CONFLICT_DETECTED = "conflict_detected"
    SYSTEM_FORCED = "system_forced"
    OVERRIDDEN = "overridden"
    NOT_APPROVED = "decision_not_approve"

# -------------------------------------------------------------------
# Normalization — Phase 5.4 Concept Mapping & Semantic Compression
# -------------------------------------------------------------------

_SUFFIX_RE = re.compile(r"(?<=\w{3})(?<!s)(es|ed|ing|s)\b")
_PUNCT_RE = re.compile(r"[^\w\s]+")
_WHITESPACE_RE = re.compile(r"\s+")
_PREFIX_RE = re.compile(r"^\s*(?:variation|delay|rfi|site issue|defect)\s*:?\s*", re.IGNORECASE)

_MEASUREMENT_PATTERN = re.compile(r"\b\d+\s*mm\b", re.IGNORECASE)
_DRAWING_PATTERN = re.compile(r"\b[A-Z]-\d+\b", re.IGNORECASE)
_DURATION_PATTERN = re.compile(r"\b\d+\s*(?:days?|hours?|hrs?|weeks?|wks?)\b", re.IGNORECASE)
_QUANTITY_PATTERN = re.compile(r"\b\d+\s*(?:pallets?|units?|loads?|trucks?)\b", re.IGNORECASE)

_CONCEPT_MAP = {
    "rain": "WEATHER_BLOCK", "raining": "WEATHER_BLOCK", "wet": "WEATHER_BLOCK", "storm": "WEATHER_BLOCK", "moisture": "WEATHER_BLOCK", "weather": "WEATHER_BLOCK",
    "steel": "MATERIAL_FLOW", "concrete": "MATERIAL_FLOW", "tiles": "MATERIAL_FLOW", "paint": "MATERIAL_FLOW", "supply": "MATERIAL_FLOW", "delivery": "MATERIAL_FLOW",
    "crew": "LABOUR_FLOW", "labour": "LABOUR_FLOW", "worker": "LABOUR_FLOW", "subbie": "LABOUR_FLOW", "contractor": "LABOUR_FLOW",
    "buried": "BURIED_SERVICE", "unidentified": "BURIED_SERVICE", "service": "BURIED_SERVICE", "trenching": "BURIED_SERVICE",
    "crane": "EQUIPMENT_FAULT", "generator": "EQUIPMENT_FAULT", "grind": "EQUIPMENT_FAULT", "noise": "EQUIPMENT_FAULT", "fault": "EQUIPMENT_FAULT", "broken": "EQUIPMENT_FAULT",
    "drawing": "DRAWING_REF", "dwg": "DRAWING_REF", "mismatch": "RFI_CLASH", "gap": "RFI_CLASH", "conflict": "RFI_CLASH", "vs": "RFI_CLASH",
}

_CONNECTOR_WORDS = frozenset({"on", "of", "the", "for", "to", "at", "in", "due", "from", "with", "by", "is", "a", "an", "and"})

_PHRASE_MAP = {
    "request for information": "rfi", "port strike": "port_strike", "structural steel": "steel", "heavy vehicle": "equipment",
    "concrete pour": "slab_pour", "slab pour": "slab_pour", "site power": "power", "power failure": "power_outage", "drawing mismatch": "mismatch",
}

_SYNONYM_MAP = {"late": "delay", "postponed": "delay", "ground": "site", "soil": "site", "rock": "site", "gear": "equipment", "plant": "equipment", "unit": "equipment"}

_PROTECTED_PATTERNS = [re.compile(r"^level\d+$", re.IGNORECASE), re.compile(r"^grid[a-z]\d*$", re.IGNORECASE), re.compile(r"^zone[a-z0-9]+$", re.IGNORECASE), re.compile(r"^lot\d+$", re.IGNORECASE)]

def _is_protected(token: str) -> bool:
    return any(p.match(token) for p in _PROTECTED_PATTERNS)

def _normalize_phrases(text: str) -> str:
    sorted_phrases = sorted(_PHRASE_MAP.keys(), key=len, reverse=True)
    pattern = re.compile("|".join(map(re.escape, sorted_phrases)), re.IGNORECASE)
    return pattern.sub(lambda m: _PHRASE_MAP[m.group(0).lower()], text)

def _normalize_parameters(text: str) -> str:
    text = _MEASUREMENT_PATTERN.sub("{measurement}", text)
    text = _DRAWING_PATTERN.sub("{drawing}", text)
    text = _DURATION_PATTERN.sub("{duration}", text)
    text = _QUANTITY_PATTERN.sub("{quantity}", text)
    return text

def _normalize_issue(raw: str) -> str:
    if not raw: return ""
    text = raw.lower()
    text = _PREFIX_RE.sub("", text)
    text = re.sub(r"\+?\$\s*\d[\d,]*\s*k?\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\+?\s*\d[\d,]*\s*k\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\+?\s*\d+\s*days?\b", " ", text, flags=re.IGNORECASE)
    text = _normalize_parameters(text)
    text = _normalize_phrases(text)
    text = _PUNCT_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    raw_tokens = [w for w in text.split(" ") if w]
    trimmed_tokens = [_SUFFIX_RE.sub("", t) for t in raw_tokens]
    final_tokens = []
    for t in trimmed_tokens:
        if t in _CONNECTOR_WORDS: continue
        if _is_protected(t): final_tokens.append(t)
        elif t in _CONCEPT_MAP: final_tokens.append(_CONCEPT_MAP[t])
        else: final_tokens.append(_SYNONYM_MAP.get(t, t))
    return " ".join(sorted(list(set(final_tokens))))

# -------------------------------------------------------------------
# Bucketing
# -------------------------------------------------------------------

def _bucket_cost(cost: float) -> str:
    c = float(cost or 0)
    if c <= 5_000: return "0-5k"
    if c <= 10_000: return "5-10k"
    if c <= 25_000: return "10-25k"
    if c <= 50_000: return "25-50k"
    return "50k+"

def _bucket_days(days: int) -> str:
    d = int(days or 0)
    if d <= 1: return "0-1d"
    if d <= 3: return "1-3d"
    if d <= 7: return "3-7d"
    if d <= 14: return "7-14d"
    return "14d+"

def _governance_flag_set(governance_flags: List[Any]) -> str:
    types: List[str] = []
    for flag in governance_flags or []:
        ft = flag.get("flag_type", "") if isinstance(flag, dict) else getattr(flag, "flag_type", "")
        if ft: types.append(str(ft))
    return ",".join(sorted(types))

@dataclass(frozen=True)
class CacheContext:
    scenario_type: str
    normalized_issue: str
    cost_bucket: str
    delay_bucket: str
    governance_flag_set: str
    policy_version: str = POLICY_VERSION

    @property
    def cache_key(self) -> str:
        raw = "||".join([self.scenario_type, self.normalized_issue, self.cost_bucket, self.delay_bucket, self.governance_flag_set, self.policy_version])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def build_cache_context(*, scenario_type: str, user_input: str, cost: float, days: int, governance_flags: List[Any]) -> CacheContext:
    return CacheContext(
        scenario_type=str(scenario_type or "").strip().lower(),
        normalized_issue=_normalize_issue(user_input),
        cost_bucket=_bucket_cost(cost),
        delay_bucket=_bucket_days(days),
        governance_flag_set=_governance_flag_set(governance_flags),
    )

def _read_bypass_reason(governance_flags: List[Any], current_distrust_level: Optional[str]) -> Optional[str]:
    for flag in governance_flags or []:
        sev = flag.get("severity") if isinstance(flag, dict) else getattr(flag, "severity", "")
        if str(sev).upper() == "CRITICAL": return BypassReason.CRITICAL_GOVERNANCE
    if current_distrust_level and current_distrust_level.upper() in BYPASS_DISTRUST_LEVELS:
        return BypassReason.DISTRUST_HIGH
    return None

def _write_bypass_reason(finalized: FinalizedDecision) -> Optional[str]:
    if finalized.was_system_forced: return BypassReason.SYSTEM_FORCED
    if finalized.has_critical_governance: return BypassReason.CRITICAL_GOVERNANCE
    if finalized.conflict_detected: return BypassReason.CONFLICT_DETECTED
    
    if finalized.was_overridden: return BypassReason.OVERRIDDEN
    if str(finalized.final_decision).upper() != "APPROVE": return BypassReason.NOT_APPROVED
    if (finalized.confidence_score or 0) < MIN_CACHE_CONFIDENCE: return BypassReason.LOW_CONFIDENCE
    
    if str(finalized.distrust_level).upper() in BYPASS_DISTRUST_LEVELS: return BypassReason.DISTRUST_HIGH
    return None

def cache_get(context: CacheContext, *, governance_flags: List[Any], current_distrust_level: Optional[str], trace_id: str, scenario_type: str) -> Tuple[Optional[FinalizedDecision], str]:
    cache_key = context.cache_key
    print(f"DEBUG CACHE_GET: Key={cache_key[:8]}... | Norm={context.normalized_issue}")
    bypass = _read_bypass_reason(governance_flags, current_distrust_level)
    if bypass: return None, "BYPASS"
    row = memory_db.cache_read(COMPONENT_NAME, cache_key)
    if row is None: return None, "MISS"
    snapshot = json.loads(row["decision_snapshot_json"])
    finalized = FinalizedDecision.from_payload(snapshot)
    print(f"DEBUG CACHE_GET: HIT!")
    return finalized, "HIT"

def cache_put(context: CacheContext, finalized: FinalizedDecision, *, trace_id: str, scenario_type: str) -> Tuple[bool, str]:
    print(f"DEBUG CACHE_PUT: Key={context.cache_key[:8]}... | Decision={finalized.final_decision}")
    bypass = _write_bypass_reason(finalized)
    if bypass: return False, "BYPASS"
    snapshot_json = json.dumps(finalized.to_event_payload(), ensure_ascii=False, sort_keys=True)
    wrote = memory_db.cache_write(
        COMPONENT_NAME, cache_key=context.cache_key, scenario_type=context.scenario_type, normalized_issue=context.normalized_issue,
        cost_bucket=context.cost_bucket, delay_bucket=context.delay_bucket, governance_flag_set=context.governance_flag_set,
        policy_version=context.policy_version, decision_snapshot_json=snapshot_json, source_trace_id=trace_id
    )
    return wrote, "WROTE" if wrote else "RACE"
