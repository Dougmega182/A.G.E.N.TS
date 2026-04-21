"""
Cognitive Boundary Contract — A.G.E.N.T.S. Memory Architecture

This contract defines the ONLY permitted read/write/derive/ephemeral
operations across the entire memory subsystem. No component may
violate these boundaries.

If a future phase requires a new memory path, it MUST be registered
here first. Unregistered writes are a system integrity failure.

Hierarchy (locked, non-negotiable):
    Events  = facts      (immutable)
    DB      = structure   (queryable)
    Owen    = insight     (synthesis only — never influences decisions)
    Aria    = decision    (intent generator)
    Orchestrator = law    (sole enforcement authority)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, Set


class MemoryTier(Enum):
    """The three storage tiers, ordered by temperature."""
    HOT = "redis"       # Ephemeral, per-loop, zero-latency
    WARM = "sqlite"     # Structured, queryable, 90-day active window
    COLD = "events"     # Immutable, append-only, forensic truth


class AccessMode(Enum):
    READ = "read"
    WRITE = "write"
    DERIVE = "derive"   # Computed from other data — never stored directly


class MemoryDomain(Enum):
    """Logical domains within the memory subsystem."""
    EVENTS = "events"                # events.log.jsonl
    DECISIONS = "decisions"          # SQLite decisions table
    AGENT_MEMORIES = "agent_memories"  # SQLite per-agent memories
    OWEN_INSIGHTS = "owen_insights"  # SQLite Owen's insights
    REASONING_CONTEXT = "reasoning_context"  # Ephemeral, per-loop
    CACHE = "cache"                  # Redis / in-memory dict


# =====================================================================
# BOUNDARY DEFINITIONS — The rules. No exceptions.
# =====================================================================

# Who can WRITE to each domain
WRITE_PERMISSIONS: Dict[MemoryDomain, FrozenSet[str]] = {
    MemoryDomain.EVENTS:            frozenset({"event_bus", "migration_scripts"}),
    MemoryDomain.DECISIONS:         frozenset({"orchestrator", "migration_scripts", "system_daemon"}),
    MemoryDomain.AGENT_MEMORIES:    frozenset({"orchestrator"}),
    MemoryDomain.OWEN_INSIGHTS:     frozenset({"owen_engine", "migration_scripts"}),
    MemoryDomain.REASONING_CONTEXT: frozenset({"orchestrator"}),
    MemoryDomain.CACHE:             frozenset({"orchestrator", "owen_engine"}),
}

# Who can READ from each domain
READ_PERMISSIONS: Dict[MemoryDomain, FrozenSet[str]] = {
    MemoryDomain.EVENTS:            frozenset({"event_analytics", "owen_engine", "migration_scripts"}),
    MemoryDomain.DECISIONS:         frozenset({"owen_engine", "orchestrator", "history_engine", "api", "system_daemon"}),
    MemoryDomain.AGENT_MEMORIES:    frozenset({"orchestrator", "history_engine", "api"}),
    MemoryDomain.OWEN_INSIGHTS:     frozenset({"owen_engine", "orchestrator", "history_engine", "api"}),
    MemoryDomain.REASONING_CONTEXT: frozenset({"orchestrator"}),  # Only orchestrator injects into agents
    MemoryDomain.CACHE:             frozenset({"orchestrator", "owen_engine", "api"}),
}

# What is DERIVED (computed, never stored as raw data)
DERIVED_DATA: FrozenSet[str] = frozenset({
    "governance_flags",        # Computed by governance_engine per-loop
    "risk_score",              # Computed by risk_engine per-loop
    "outcome_signal",          # Computed from decisions table
    "memory_conflicts",        # Computed by history_engine per-loop
    "reasoning_quality",       # Computed by decision_finalizer per-loop
    "intelligence_briefing",   # Computed by owen_engine, then cached
})

# What is EPHEMERAL (exists only for one loop, then discarded)
EPHEMERAL_DATA: FrozenSet[str] = frozenset({
    "reasoning_context",       # Built per-loop, garbage collected after
    "cache_entries",           # Redis TTL or cleared after loop
    "agent_turn_outputs",      # Raw LLM outputs, consumed then discarded
})


# =====================================================================
# RETENTION POLICY
# =====================================================================

@dataclass(frozen=True)
class RetentionPolicy:
    """Memory lifecycle rules."""
    # SQLite active window
    active_window_days: int = 90

    # Owen insights persist if validated N+ times
    insight_min_validations: int = 3

    # Events are immutable and never deleted
    events_retention: str = "permanent"

    # Cache TTL
    cache_ttl_seconds: int = 300  # 5 minutes


RETENTION = RetentionPolicy()


# =====================================================================
# OWEN BOUNDARY (the most important constraint)
# =====================================================================

@dataclass(frozen=True)
class OwenBoundary:
    """
    Owen's cognitive boundaries — what he CAN and CANNOT do.

    Owen = "what has happened and what it means"
    Owen ≠ "what should we do"
    """

    # ALLOWED
    can_extract_patterns: bool = True
    can_generate_lessons: bool = True
    can_detect_failures: bool = True
    can_produce_guidance: bool = True     # do / don't-do advisories
    can_compress_history: bool = True
    can_write_insights: bool = True       # To owen_insights table ONLY

    # NOT ALLOWED
    can_make_decisions: bool = False
    can_influence_governance: bool = False
    can_override_orchestrator: bool = False
    can_vote: bool = False                # Owen does NOT vote
    can_store_raw_events: bool = False
    can_compete_with_aria: bool = False

    # EXECUTION CONTEXT
    allowed_in_realtime_loop: bool = True   # Deterministic synthesis only
    allowed_llm_in_loop: bool = False       # NEVER — LLM is batch/scheduled only
    allowed_llm_offline: bool = True        # Morning brief, narrative synthesis


OWEN_BOUNDARY = OwenBoundary()


# =====================================================================
# ENFORCEMENT — Runtime boundary checks
# =====================================================================

class MemoryBoundaryViolation(Exception):
    """Raised when a component attempts an unauthorized memory operation."""
    def __init__(self, component: str, domain: MemoryDomain, mode: AccessMode, message: str = ""):
        self.component = component
        self.domain = domain
        self.mode = mode
        detail = f"BOUNDARY VIOLATION: {component} attempted {mode.value} on {domain.value}"
        if message:
            detail += f" — {message}"
        super().__init__(detail)


def assert_write_permission(component: str, domain: MemoryDomain):
    """Call before ANY write operation. Raises if unauthorized."""
    permitted = WRITE_PERMISSIONS.get(domain, frozenset())
    if component not in permitted:
        raise MemoryBoundaryViolation(
            component, domain, AccessMode.WRITE,
            f"Permitted writers: {sorted(permitted)}"
        )


def assert_read_permission(component: str, domain: MemoryDomain):
    """Call before ANY read operation. Raises if unauthorized."""
    permitted = READ_PERMISSIONS.get(domain, frozenset())
    if component not in permitted:
        raise MemoryBoundaryViolation(
            component, domain, AccessMode.READ,
            f"Permitted readers: {sorted(permitted)}"
        )


def check_owen_boundary(action: str) -> bool:
    """
    Verify Owen is not exceeding his cognitive boundaries.
    Returns True if the action is permitted.
    """
    forbidden_actions = {
        "make_decision", "override_governance", "override_orchestrator",
        "cast_vote", "store_raw_event", "compete_with_aria",
        "llm_call_in_loop",
    }
    return action not in forbidden_actions
