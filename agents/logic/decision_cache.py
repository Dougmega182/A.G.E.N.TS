"""
Decision Cache \u2014 Phase 5.1.5 Inference Caching Layer 1.

Purpose
-------
Stop paying for the same thinking on repeat inputs. On a cache hit the
orchestrator skips Nadia \u2192 Tucker \u2192 Sentinel \u2192 Aria \u2192 finalize_decision and
reuses a previously-produced FinalizedDecision. Jenny still runs (email
content depends on exact cost/days which may differ within a cost bucket).

Contract (aligned with PLANNING.md Phase 5.1.5)
-----------------------------------------------
- Deterministic cache key = hash(
      scenario_type || normalized_issue || cost_bucket ||
      delay_bucket || governance_flag_set || policy_version
  )
- policy_version bumps whenever governance thresholds or scoping logic
  change; old entries then cease to match new keys and quietly age out.
- TTL (seconds) controls staleness \u2014 construction context is
  time-sensitive (subcontractor performance, site conditions, pricing).
  Defaults to 48h; override via AGENTS_DECISION_CACHE_TTL env var.
- STRICT+ normalization: light canonicalization, NOT semantic matching.
  Lowercase, punctuation stripped, whitespace collapsed, conservative
  verb stem trim (delay/delays/delayed/delaying \u2192 delay).
- Bypass matrix is enforced on BOTH read and write so unsafe decisions
  neither poison the cache nor are replayed if the live context has
  deteriorated since.
- Writes use INSERT OR IGNORE on a UNIQUE(cache_key) constraint so
  concurrent writers are race-safe.

Telemetry
---------
Every cache interaction emits exactly one of:
    CACHE_HIT    \u2014 key, source_trace_id, age_seconds, hit_count, distrust_level
    CACHE_MISS   \u2014 key, reason="no_entry" | "expired" | "snapshot_invalid",
                   miss_classification for no_entry only
    CACHE_BYPASS \u2014 key, reason=<one of BypassReason.*>
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from . import event_bus, memory_db
from .decision_finalizer import FinalizedDecision

# -------------------------------------------------------------------
# Contract constants
# -------------------------------------------------------------------

# Bump whenever governance thresholds or scoping logic change so old
# cache rows stop matching new keys. Keep as a simple string.
POLICY_VERSION = "v5"

# Time-to-live for a cache row. Construction conditions drift; don't let
# a 2-week-old decision be replayed as fresh.
DEFAULT_TTL_SECONDS = 48 * 3600

# Minimum confidence to permit caching on the write side.
MIN_CACHE_CONFIDENCE = 0.7

# Distrust levels at which the cache must bypass (both read and write).
BYPASS_DISTRUST_LEVELS = frozenset({"HIGH", "BLOCKED"})

# Component id used for memory-contract permission checks.
COMPONENT_NAME = "orchestrator"


class BypassReason:
    """Stable string codes so downstream analytics can aggregate."""

    CRITICAL_GOVERNANCE = "critical_governance"
    LOW_CONFIDENCE = "low_confidence"
    DISTRUST_HIGH = "distrust_high"
    CONFLICT_DETECTED = "conflict_detected"
    SYSTEM_FORCED = "system_forced"
    OVERRIDDEN = "overridden"
    NOT_APPROVED = "decision_not_approve"


# -------------------------------------------------------------------
# Normalization — Phase 5.3.6 Parameter Abstraction & Phrase Mapping
# -------------------------------------------------------------------

# Conservative verb-suffix trimmer.
_SUFFIX_RE = re.compile(r"(?<=\w{3})(?<!s)(es|ed|ing|s)\b")
_PUNCT_RE = re.compile(r"[^\w\s]+")
_WHITESPACE_RE = re.compile(r"\s+")

# Scenario prefix — only stripped when anchored at the start of input.
_PREFIX_RE = re.compile(r"^\s*(?:variation|delay|rfi|site issue|defect)\s*:?\s*", re.IGNORECASE)

# Cost/days tokens that appear in user_input and MUST be stripped.
_DOLLAR_AMOUNT_RE = re.compile(r"\+?\$\s*\d[\d,]*\s*k?\b", re.IGNORECASE)
_K_AMOUNT_RE = re.compile(r"\+?\s*\d[\d,]*\s*k\b", re.IGNORECASE)
_DAYS_RE = re.compile(r"\+?\s*\d+\s*days?\b", re.IGNORECASE)

_CONNECTOR_WORDS = frozenset({"on", "of", "the", "for", "to", "at", "in", "due", "from", "with", "by", "is", "a", "an", "and"})

# Phase 5.3.6: Parameter Abstraction Patterns (Layer 2.6)
# These replace specific variable values with stable placeholders.
_MEASUREMENT_PATTERN = re.compile(r"\b\d+\s*mm\b", re.IGNORECASE)
_DRAWING_PATTERN = re.compile(r"\b[A-Z]-\d+\b", re.IGNORECASE)

# Phase 5.3.5: Multi-word phrase mapping. 
# Applied BEFORE tokenization to prevent meaning fragmentation.
_PHRASE_MAP = {
    "request for information": "rfi",
    "port strike": "port_strike",
    "structural steel": "steel",
    "heavy vehicle": "equipment",
    "concrete pour": "slab_pour",
    "slab pour": "slab_pour",
    "wet weather": "rain",
    "site power": "power",
    "power failure": "power_outage",
    "drawing mismatch": "mismatch",
}

# One-way canonical mapping for Semantic Layer 2.
_SYNONYM_MAP = {
    "late": "delay",
    "postponed": "delay",
    "weather": "rain",
    "storm": "rain",
    "wet": "rain",
    "ground": "site",
    "soil": "site",
    "rock": "site",
    "gear": "equipment",
    "plant": "equipment",
    "unit": "equipment",
}

# Protected terms that should NEVER be mapped or stripped of specificity.
_PROTECTED_PATTERNS = [
    re.compile(r"^level\d+$", re.IGNORECASE),
    re.compile(r"^grid[a-z]\d*$", re.IGNORECASE),
    re.compile(r"^zone[a-z0-9]+$", re.IGNORECASE),
    re.compile(r"^lot\d+$", re.IGNORECASE),
]


def _is_protected(token: str) -> bool:
    """Check if a token matches any protected patterns (location/id)."""
    return any(p.match(token) for p in _PROTECTED_PATTERNS)


def _normalize_phrases(text: str) -> str:
    """Perform multi-word phrase replacements before tokenization."""
    # Use re.sub with a function or a sorted alternation list to avoid partial matches
    # Sorting by length descending ensures "structural steel" matches before "steel"
    sorted_phrases = sorted(_PHRASE_MAP.keys(), key=len, reverse=True)
    pattern = re.compile("|".join(map(re.escape, sorted_phrases)), re.IGNORECASE)
    
    return pattern.sub(lambda m: _PHRASE_MAP[m.group(0).lower()], text)


def _normalize_parameters(text: str) -> str:
    """Replace measurements and drawing refs with stable placeholders (Layer 2.6)."""
    text = _MEASUREMENT_PATTERN.sub("{measurement}", text)
    text = _DRAWING_PATTERN.sub("{drawing}", text)
    return text


def _normalize_issue(raw: str) -> str:
    """STRICT+ v5 canonicalization with Parameter Abstraction.

    1. Clean prefixes and metrics.
    2. Parameter Abstraction (150mm -> {measurement}).
    3. Phrase Normalization.
    4. Suffix trim and connector removal.
    5. Synonym Expansion.
    6. Token sorting.
    """
    if not raw:
        return ""
    text = raw.lower()
    # 1. Clean prefixes and metrics
    text = _PREFIX_RE.sub("", text)
    text = _DOLLAR_AMOUNT_RE.sub(" ", text)
    text = _K_AMOUNT_RE.sub(" ", text)
    text = _DAYS_RE.sub(" ", text)
    
    # 2. Parameter Abstraction (Layer 2.6)
    text = _normalize_parameters(text)
    
    # 3. Phrase Normalization (Phase 5.3.5)
    text = _normalize_phrases(text)
    
    # 4. Punctuation and Whitespace
    text = _PUNCT_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    
    # 5. Tokenize and suffix trim
    raw_tokens = [w for w in text.split(" ") if w]
    trimmed_tokens = [_SUFFIX_RE.sub("", t) for t in raw_tokens]
    
    # 6. Filter connectors and apply Semantic Expansion
    final_tokens = []
    for t in trimmed_tokens:
        if t in _CONNECTOR_WORDS:
            continue
        # Semantic Step (Layer 2)
        if _is_protected(t):
            final_tokens.append(t)
        else:
            canonical = _SYNONYM_MAP.get(t, t)
            final_tokens.append(canonical)
    # 7. Sort for bag-of-words stability
    return " ".join(sorted(final_tokens))


# -------------------------------------------------------------------
# Bucketing \u2014 thresholds aligned with governance_engine
# -------------------------------------------------------------------


def _bucket_cost(cost: float) -> str:
    """Tiered bucket aligned with governance_engine thresholds."""
    c = float(cost or 0)
    if c <= 5_000:
        return "0-5k"
    if c <= 10_000:
        return "5-10k"
    if c <= 25_000:
        return "10-25k"
    if c <= 50_000:
        return "25-50k"
    return "50k+"


def _bucket_days(days: int) -> str:
    """Tiered bucket aligned with governance_engine schedule thresholds."""
    d = int(days or 0)
    if d <= 1:
        return "0-1d"
    if d <= 3:
        return "1-3d"
    if d <= 7:
        return "3-7d"
    if d <= 14:
        return "7-14d"
    return "14d+"


def _governance_flag_set(governance_flags: List[Any]) -> str:
    """Sorted, comma-joined flag types for stable hashing.

    Accepts either GovernanceFlag dataclasses or dicts (post-serialization).
    """
    types: List[str] = []
    for flag in governance_flags or []:
        if isinstance(flag, dict):
            ft = flag.get("flag_type", "")
        else:
            ft = getattr(flag, "flag_type", "")
        if ft:
            types.append(str(ft))
    return ",".join(sorted(types))


# -------------------------------------------------------------------
# Centralized key builder (ONE source of truth for read + write)
# -------------------------------------------------------------------


@dataclass(frozen=True)
class CacheContext:
    """All inputs required to derive a cache key. Build once, reuse twice."""

    scenario_type: str
    normalized_issue: str
    cost_bucket: str
    delay_bucket: str
    governance_flag_set: str
    policy_version: str = POLICY_VERSION

    @property
    def cache_key(self) -> str:
        raw = "||".join(
            [
                self.scenario_type,
                self.normalized_issue,
                self.cost_bucket,
                self.delay_bucket,
                self.governance_flag_set,
                self.policy_version,
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_cache_context(
    *,
    scenario_type: str,
    user_input: str,
    cost: float,
    days: int,
    governance_flags: List[Any],
) -> CacheContext:
    """Construct a CacheContext from raw loop inputs. Used by read and write."""
    return CacheContext(
        scenario_type=str(scenario_type or "").strip().lower(),
        normalized_issue=_normalize_issue(user_input),
        cost_bucket=_bucket_cost(cost),
        delay_bucket=_bucket_days(days),
        governance_flag_set=_governance_flag_set(governance_flags),
    )


# -------------------------------------------------------------------
# Read / Write
# -------------------------------------------------------------------


def _ttl_seconds() -> int:
    raw = os.environ.get("AGENTS_DECISION_CACHE_TTL")
    if not raw:
        return DEFAULT_TTL_SECONDS
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_TTL_SECONDS


def _age_seconds(created_at_iso: str) -> int:
    try:
        created = datetime.fromisoformat(created_at_iso)
    except ValueError:
        return 0
    delta = datetime.utcnow() - created
    return int(delta.total_seconds())


def _has_critical_governance(governance_flags: List[Any]) -> bool:
    for flag in governance_flags or []:
        sev = flag.get("severity") if isinstance(flag, dict) else getattr(flag, "severity", "")
        if str(sev).upper() == "CRITICAL":
            return True
    return False


def _read_bypass_reason(
    governance_flags: List[Any],
    current_distrust_level: Optional[str],
) -> Optional[str]:
    """Decide whether a cache READ should bypass given current context.

    We don't cache when the live context is risky \u2014 even if the key
    matches a safely-cached decision, the world may have changed.
    """
    if _has_critical_governance(governance_flags):
        return BypassReason.CRITICAL_GOVERNANCE
    if current_distrust_level and current_distrust_level.upper() in BYPASS_DISTRUST_LEVELS:
        return BypassReason.DISTRUST_HIGH
    return None


def _write_bypass_reason(finalized: FinalizedDecision) -> Optional[str]:
    """Decide whether a cache WRITE should be skipped for a fresh decision.

    Ordered by severity so the most important signal surfaces first.
    """
    if finalized.was_system_forced:
        return BypassReason.SYSTEM_FORCED
    if finalized.has_critical_governance:
        return BypassReason.CRITICAL_GOVERNANCE
    if finalized.conflict_detected:
        return BypassReason.CONFLICT_DETECTED
    if finalized.was_overridden:
        return BypassReason.OVERRIDDEN
    if str(finalized.final_decision).upper() != "APPROVE":
        return BypassReason.NOT_APPROVED
    if (finalized.confidence_score or 0) < MIN_CACHE_CONFIDENCE:
        return BypassReason.LOW_CONFIDENCE
    if str(finalized.distrust_level).upper() in BYPASS_DISTRUST_LEVELS:
        return BypassReason.DISTRUST_HIGH
    return None


def _tokenize_issue(normalized_issue: str) -> Tuple[set[str], set[str]]:
    """Split normalized text into content tokens and entity-like tokens."""
    content: set[str] = set()
    entity: set[str] = set()
    for token in (normalized_issue or "").split():
        if not token:
            continue
        if any(ch.isdigit() for ch in token) or (len(token) == 1 and token.isalpha()):
            entity.add(token)
        else:
            content.add(token)
    return content, entity


def _classify_no_entry_miss(context: CacheContext) -> str:
    """Classify a no-entry miss for telemetry only.

    Categories are intentionally coarse:
      - wording_variation
      - same_intent_different_entity
      - insufficient_context
      - new_intent
    """
    rows = memory_db.cache_list_candidates(
        COMPONENT_NAME,
        scenario_type=context.scenario_type,
        policy_version=context.policy_version,
    )
    if not rows:
        return "new_intent"

    same_norm_any = [
        row for row in rows
        if row.get("normalized_issue") == context.normalized_issue
    ]
    if same_norm_any:
        return "insufficient_context"

    scoped_rows = [
        row for row in rows
        if row.get("cost_bucket") == context.cost_bucket
        and row.get("delay_bucket") == context.delay_bucket
        and row.get("governance_flag_set") == context.governance_flag_set
    ]
    if not scoped_rows:
        return "new_intent"

    target_content, target_entity = _tokenize_issue(context.normalized_issue)
    for row in scoped_rows:
        row_content, row_entity = _tokenize_issue(str(row.get("normalized_issue", "")))
        if target_content == row_content and target_entity != row_entity and (target_entity or row_entity):
            return "same_intent_different_entity"

    for row in scoped_rows:
        row_content, row_entity = _tokenize_issue(str(row.get("normalized_issue", "")))
        content_floor = min(len(target_content), len(row_content))
        if content_floor == 0:
            continue
        overlap = len(target_content & row_content)
        if overlap >= max(1, content_floor - 1) and target_entity == row_entity:
            return "wording_variation"

    return "new_intent"


def cache_get(
    context: CacheContext,
    *,
    governance_flags: List[Any],
    current_distrust_level: Optional[str],
    trace_id: str,
    scenario_type: str,
) -> Tuple[Optional[FinalizedDecision], str]:
    """Attempt a cache read.

    Returns (finalized_or_none, outcome) where outcome is one of
    "HIT", "MISS", or "BYPASS". Telemetry is emitted as a side effect.
    """
    cache_key = context.cache_key

    # Read-side bypass: risky live context \u2014 never replay.
    bypass = _read_bypass_reason(governance_flags, current_distrust_level)
    if bypass is not None:
        event_bus.emit_event(
            "CACHE_BYPASS",
            trace_id,
            agent_id=COMPONENT_NAME,
            scenario=scenario_type,
            metadata={
                "cache_key": cache_key,
                "reason": bypass,
                "stage": "read",
            },
        )
        return None, "BYPASS"

    row = memory_db.cache_read(COMPONENT_NAME, cache_key)
    if row is None:
        miss_classification = _classify_no_entry_miss(context)
        event_bus.emit_event(
            "CACHE_MISS",
            trace_id,
            agent_id=COMPONENT_NAME,
            scenario=scenario_type,
            metadata={
                "cache_key": cache_key,
                "reason": "no_entry",
                "miss_classification": miss_classification,
                "policy_version": context.policy_version,
            },
        )
        return None, "MISS"

    age = _age_seconds(row.get("created_at", ""))
    if age > _ttl_seconds():
        event_bus.emit_event(
            "CACHE_MISS",
            trace_id,
            agent_id=COMPONENT_NAME,
            scenario=scenario_type,
            metadata={
                "cache_key": cache_key,
                "reason": "expired",
                "age_seconds": age,
                "ttl_seconds": _ttl_seconds(),
            },
        )
        return None, "MISS"

    try:
        snapshot = json.loads(row["decision_snapshot_json"])
        finalized = FinalizedDecision.from_payload(snapshot)
    except (ValueError, KeyError, TypeError):
        event_bus.emit_event(
            "CACHE_MISS",
            trace_id,
            agent_id=COMPONENT_NAME,
            scenario=scenario_type,
            metadata={"cache_key": cache_key, "reason": "snapshot_invalid"},
        )
        return None, "MISS"

    memory_db.cache_touch_hit(COMPONENT_NAME, cache_key)
    
    # Derived metric: effective_savings_ms = avg_miss_latency - lookup_cost
    # We use a recent baseline from event analytics if available.
    from .event_analytics import get_avg_miss_latency
    avg_miss = get_avg_miss_latency()
    
    # Note: decision_phase_ms (hit latency) is recorded by the orchestrator
    # at the macro level, but here we can provide the theoretical savings.
    effective_savings = max(0, avg_miss - 200) # 200ms is a conservative lookup+replay cost

    event_bus.emit_event(
        "CACHE_HIT",
        trace_id,
        agent_id=COMPONENT_NAME,
        scenario=scenario_type,
        metadata={
            "cache_key": cache_key,
            "source_trace_id": row.get("source_trace_id", ""),
            "age_seconds": age,
            "hit_count": int(row.get("hit_count", 0)) + 1,
            "distrust_level": current_distrust_level or "LOW",
            "policy_version": row.get("policy_version", ""),
            "effective_savings_ms": effective_savings,
        },
    )
    return finalized, "HIT"


def cache_put(
    context: CacheContext,
    finalized: FinalizedDecision,
    *,
    trace_id: str,
    scenario_type: str,
) -> Tuple[bool, str]:
    """Attempt to write a fresh decision to the cache.

    Returns (wrote, outcome) where outcome is one of "WROTE", "BYPASS",
    or "RACE" (another writer got there first).
    """
    bypass = _write_bypass_reason(finalized)
    if bypass is not None:
        event_bus.emit_event(
            "CACHE_BYPASS",
            trace_id,
            agent_id=COMPONENT_NAME,
            scenario=scenario_type,
            metadata={
                "cache_key": context.cache_key,
                "reason": bypass,
                "stage": "write",
            },
        )
        return False, "BYPASS"

    snapshot_json = json.dumps(
        finalized.to_event_payload(),
        ensure_ascii=False,
        sort_keys=True,  # deterministic serialization
    )
    wrote = memory_db.cache_write(
        COMPONENT_NAME,
        cache_key=context.cache_key,
        scenario_type=context.scenario_type,
        normalized_issue=context.normalized_issue,
        cost_bucket=context.cost_bucket,
        delay_bucket=context.delay_bucket,
        governance_flag_set=context.governance_flag_set,
        policy_version=context.policy_version,
        decision_snapshot_json=snapshot_json,
        source_trace_id=trace_id,
    )
    return wrote, ("WROTE" if wrote else "RACE")
