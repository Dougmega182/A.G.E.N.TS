"""
Memory Database — SQLite persistent storage for the A.G.E.N.T.S. cognitive layer.

This is TIER 2 (warm storage). It is:
    - Derived from events.log.jsonl (can always be rebuilt)
    - Queryable for structured lookups
    - Subject to 90-day active window retention
    - Written to ONLY by orchestrator (decisions) and owen_engine (insights)

Tables:
    decisions       — Structured records from DECISION_FINALIZED_V1 events
    agent_memories  — Per-agent long-term memory (lessons, patterns)
    owen_insights   — Owen's synthesized intelligence
"""

from __future__ import annotations

import json
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .memory_contract import (
    MemoryDomain,
    assert_write_permission,
    assert_read_permission,
    RETENTION,
)

import os
DB_PATH = Path(os.getenv("AGENTS_DB_PATH", str(Path(__file__).parent.parent.parent / "data" / "agents_memory.db")))

logger = logging.getLogger("agents.memory_db")

# =====================================================================
# SCHEMA
# =====================================================================

_SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    scenario TEXT NOT NULL,
    final_decision TEXT NOT NULL,
    original_decision TEXT NOT NULL,
    was_overridden INTEGER NOT NULL DEFAULT 0,
    was_system_forced INTEGER NOT NULL DEFAULT 0,
    risk_score REAL NOT NULL DEFAULT 0.0,
    cost REAL DEFAULT 0,
    days INTEGER DEFAULT 0,
    outcome_score INTEGER DEFAULT 0,
    override_chain TEXT DEFAULT '[]',
    primary_override_reason TEXT,
    governance_flag_count INTEGER DEFAULT 0,
    has_critical_governance INTEGER DEFAULT 0,
    conflict_detected INTEGER DEFAULT 0,
    reasoning_quality_warnings TEXT DEFAULT '[]',
    justification TEXT,
    timestamp TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decisions_trace_id ON decisions(trace_id);
CREATE INDEX IF NOT EXISTS idx_decisions_scenario ON decisions(scenario);
CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON decisions(timestamp);
CREATE INDEX IF NOT EXISTS idx_decisions_final_decision ON decisions(final_decision);

CREATE TABLE IF NOT EXISTS agent_memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    scenario_type TEXT,
    source_trace_id TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_memories_agent_id ON agent_memories(agent_id);
CREATE INDEX IF NOT EXISTS idx_agent_memories_scenario ON agent_memories(scenario_type);

CREATE TABLE IF NOT EXISTS owen_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insight_type TEXT NOT NULL,
    scenario_type TEXT,
    summary TEXT NOT NULL,
    deterministic_key TEXT UNIQUE,
    evidence TEXT DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0.5,
    times_validated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    last_validated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_owen_insights_scenario ON owen_insights(scenario_type);
CREATE INDEX IF NOT EXISTS idx_owen_insights_type ON owen_insights(insight_type);
CREATE INDEX IF NOT EXISTS idx_owen_insights_det_key ON owen_insights(deterministic_key);

CREATE TABLE IF NOT EXISTS execution_keys (
    key TEXT PRIMARY KEY,
    execution_trace_id TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    action TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_execution_keys_trace_id ON execution_keys(trace_id);

CREATE TABLE IF NOT EXISTS execution_verification_queue (
    id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    external_id TEXT NOT NULL,
    expected_state TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    attempts INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_exec_verif_queue_status ON execution_verification_queue(status);
CREATE INDEX IF NOT EXISTS idx_exec_verif_queue_sched ON execution_verification_queue(scheduled_at);

CREATE TABLE IF NOT EXISTS owen_negative_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,
    failure_key TEXT NOT NULL,
    count INTEGER DEFAULT 1,
    last_seen TEXT NOT NULL,
    penalty REAL DEFAULT 0.0,
    UNIQUE(action_type, failure_key)
);
"""


# =====================================================================
# CONNECTION MANAGEMENT
# =====================================================================

def _ensure_db() -> None:
    """Create the database and tables if they don't exist, handling light migrations."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as conn:
        # 1. Basic schema creation
        # We split the schema to handle potential errors in indexes for columns that might need migration
        statements = _SCHEMA.strip().split(";")
        for stmt in statements:
            if not stmt.strip(): continue
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError as e:
                # If index creation fails because of missing column, we'll try to migrate next
                if "no such column" in str(e).lower():
                    logger.warning(f"Schema statement failed (might need migration): {e}")
                else:
                    raise

        # 2. Migration: Add deterministic_key to owen_insights if missing
        try:
            conn.execute("SELECT deterministic_key FROM owen_insights LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("MIGRATION: Adding deterministic_key column to owen_insights...")
            conn.execute("ALTER TABLE owen_insights ADD COLUMN deterministic_key TEXT")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_owen_insights_det_key ON owen_insights(deterministic_key)")


@contextmanager
def _get_conn():
    """Context manager for a database connection."""
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
        import gc
        gc.collect()


# =====================================================================
# DECISIONS — Written by orchestrator ONLY
# =====================================================================

def write_decision(component: str, decision_event: Dict[str, Any]) -> None:
    """
    Persist a DECISION_FINALIZED_V1 event to the decisions table.
    Only the orchestrator is permitted to call this.
    """
    assert_write_permission(component, MemoryDomain.DECISIONS)

    meta = decision_event.get("metadata", {})
    impact = meta.get("impact", {}) if isinstance(meta.get("impact"), dict) else {}

    with _get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO decisions
               (id, trace_id, scenario, final_decision, original_decision,
                was_overridden, was_system_forced, risk_score, cost, days,
                outcome_score, override_chain, primary_override_reason,
                governance_flag_count, has_critical_governance, conflict_detected,
                reasoning_quality_warnings, justification, timestamp, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                decision_event.get("event_id", ""),
                meta.get("trace_id", decision_event.get("trace_id", "")),
                decision_event.get("scenario", ""),
                meta.get("final_decision", ""),
                meta.get("original_decision", ""),
                1 if meta.get("was_overridden") else 0,
                1 if meta.get("was_system_forced") else 0,
                meta.get("risk_score", 0.0),
                impact.get("cost", 0),
                impact.get("days", 0),
                meta.get("outcome_score", 0),
                json.dumps(meta.get("override_chain", [])),
                meta.get("primary_override_reason"),
                meta.get("governance_flag_count", 0),
                1 if meta.get("has_critical_governance") else 0,
                1 if meta.get("conflict_detected") else 0,
                json.dumps(meta.get("reasoning_quality_warnings", [])),
                meta.get("final_justification", ""),
                decision_event.get("timestamp", ""),
                datetime.utcnow().isoformat(),
            )
        )


def read_decisions(
    component: str,
    scenario: Optional[str] = None,
    limit: int = 10,
    days_back: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Read recent decisions from the database."""
    assert_read_permission(component, MemoryDomain.DECISIONS)

    query = "SELECT * FROM decisions"
    params: list = []
    conditions: list = []

    if scenario:
        conditions.append("scenario = ?")
        params.append(scenario)

    if days_back:
        cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        conditions.append("timestamp >= ?")
        params.append(cutoff)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    with _get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


# =====================================================================
# AGENT MEMORIES — Written by orchestrator ONLY
# =====================================================================

def write_agent_memory(
    component: str,
    agent_id: str,
    memory_type: str,
    content: str,
    scenario_type: Optional[str] = None,
    source_trace_id: Optional[str] = None,
) -> None:
    """Persist a long-term memory for an agent."""
    assert_write_permission(component, MemoryDomain.AGENT_MEMORIES)

    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO agent_memories
               (agent_id, memory_type, content, scenario_type, source_trace_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (agent_id, memory_type, content, scenario_type, source_trace_id,
             datetime.utcnow().isoformat())
        )


def read_agent_memories(
    component: str,
    agent_id: Optional[str] = None,
    scenario_type: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Read agent memories from the database."""
    assert_read_permission(component, MemoryDomain.AGENT_MEMORIES)

    query = "SELECT * FROM agent_memories"
    params: list = []
    conditions: list = []

    if agent_id:
        conditions.append("agent_id = ?")
        params.append(agent_id)

    if scenario_type:
        conditions.append("scenario_type = ?")
        params.append(scenario_type)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


# =====================================================================
# OWEN INSIGHTS — Written by owen_engine ONLY
# =====================================================================

def write_owen_insight(
    component: str,
    insight_type: str,
    summary: str,
    scenario_type: Optional[str] = None,
    evidence: Optional[List[str]] = None,
    confidence: float = 0.5,
    deterministic_key: Optional[str] = None,
) -> int:
    """
    Write one of Owen's synthesized insights.
    Only owen_engine is permitted to call this.
    """
    assert_write_permission(component, MemoryDomain.OWEN_INSIGHTS)

    with _get_conn() as conn:
        try:
            cursor = conn.execute(
                """INSERT INTO owen_insights
                (insight_type, scenario_type, summary, deterministic_key, evidence, confidence,
                    times_validated, created_at, last_validated_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, NULL)""",
                (insight_type, scenario_type, summary, deterministic_key,
                json.dumps(evidence or []), confidence,
                datetime.utcnow().isoformat())
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Deterministic key already exists; this is a replay or known insight
            logger.info(f"Owen insight already exists (det_key: {deterministic_key}). Skipping write.")
            return -1


def validate_owen_insight(component: str, insight_id: int) -> None:
    """Increment the validation count for an insight (confirms it still holds)."""
    assert_write_permission(component, MemoryDomain.OWEN_INSIGHTS)

    with _get_conn() as conn:
        conn.execute(
            """UPDATE owen_insights
               SET times_validated = times_validated + 1,
                   last_validated_at = ?
               WHERE id = ?""",
            (datetime.utcnow().isoformat(), insight_id)
        )


def read_owen_insights(
    component: str,
    scenario_type: Optional[str] = None,
    insight_type: Optional[str] = None,
    min_confidence: float = 0.0,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Read Owen's insights from the database."""
    assert_read_permission(component, MemoryDomain.OWEN_INSIGHTS)

    query = "SELECT * FROM owen_insights"
    params: list = []
    conditions: list = []

    if scenario_type:
        conditions.append("scenario_type = ?")
        params.append(scenario_type)

    if insight_type:
        conditions.append("insight_type = ?")
        params.append(insight_type)

    if min_confidence > 0:
        conditions.append("confidence >= ?")
        params.append(min_confidence)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY times_validated DESC, confidence DESC LIMIT ?"
    params.append(limit)

    with _get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


# =====================================================================
# RETENTION — Cleanup old data per retention policy
# =====================================================================

def enforce_retention(component: str = "orchestrator") -> Dict[str, int]:
    """
    Clean up data older than the active window.
    Events are NEVER deleted (immutable truth).
    Owen insights survive if validated >= N times.
    """
    assert_write_permission(component, MemoryDomain.DECISIONS)

    cutoff = (datetime.utcnow() - timedelta(days=RETENTION.active_window_days)).isoformat()
    results = {}

    with _get_conn() as conn:
        # Archive old decisions
        cursor = conn.execute("DELETE FROM decisions WHERE timestamp < ?", (cutoff,))
        results["decisions_archived"] = cursor.rowcount

        # Archive old agent memories
        cursor = conn.execute("DELETE FROM agent_memories WHERE created_at < ?", (cutoff,))
        results["memories_archived"] = cursor.rowcount

        # Archive old Owen insights UNLESS validated enough
        cursor = conn.execute(
            "DELETE FROM owen_insights WHERE created_at < ? AND times_validated < ?",
            (cutoff, RETENTION.insight_min_validations)
        )
        results["insights_archived"] = cursor.rowcount

        # Count surviving insights
        cursor = conn.execute(
            "SELECT COUNT(*) FROM owen_insights WHERE created_at < ? AND times_validated >= ?",
            (cutoff, RETENTION.insight_min_validations)
        )
        results["insights_preserved"] = cursor.fetchone()[0]

    return results


# =====================================================================
# EXECUTION KEY MANAGEMENT
# =====================================================================

def write_execution_key(component: str, key: str, execution_trace_id: str, trace_id: str, action: str):
    """Persist an idempotency key to block duplicate side-effects."""
    assert_write_permission(component, MemoryDomain.DECISIONS)  # Mapping to Decisions domain

    with _get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO execution_keys (key, execution_trace_id, trace_id, action, created_at) VALUES (?, ?, ?, ?, ?)",
                (key, execution_trace_id, trace_id, action, datetime.utcnow().isoformat())
            )
        except sqlite3.IntegrityError:
            # Already exists, which is fine (idempotent)
            pass
        except sqlite3.Error as e:
            logger.error(f"Failed to write execution key: {e}")


def read_execution_keys(component: str) -> List[str]:
    """Retrieve all seen idempotency keys for gateway restoration."""
    assert_read_permission(component, MemoryDomain.DECISIONS)

    with _get_conn() as conn:
        cursor = conn.execute("SELECT key FROM execution_keys")
        return [row["key"] for row in cursor.fetchall()]

# =====================================================================
# VERIFICATION QUEUE (Phase 2 Reality Checks)
# =====================================================================

import uuid

def enqueue_verification_job(component: str, action_type: str, external_id: str, expected_state: Dict[str, Any], execute_after_seconds: int = 120):
    """Enqueue an action for secondary truth-state verification (Drift Detection)."""
    assert_write_permission(component, MemoryDomain.DECISIONS)

    job_id = f"VER-{uuid.uuid4().hex[:12].upper()}"
    scheduled_at = (datetime.utcnow() + timedelta(seconds=execute_after_seconds)).isoformat()
    
    with _get_conn() as conn:
        try:
            conn.execute(
                """INSERT INTO execution_verification_queue
                   (id, action_type, external_id, expected_state, scheduled_at, attempts, status)
                   VALUES (?, ?, ?, ?, ?, 0, 'pending')""",
                (job_id, action_type, external_id, json.dumps(expected_state), scheduled_at)
            )
            return job_id
        except sqlite3.Error as e:
            logger.error(f"Failed to enqueue verification job: {e}")
            return None

def get_due_verification_jobs(component: str, limit: int = 10) -> List[Dict[str, Any]]:
    assert_read_permission(component, MemoryDomain.DECISIONS)
    now_ts = datetime.utcnow().isoformat()
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM execution_verification_queue WHERE status IN ('pending', 'transient') AND scheduled_at <= ? ORDER BY scheduled_at ASC LIMIT ?",
            (now_ts, limit)
        )
        return [dict(row) for row in cursor.fetchall()]

def update_verification_job(component: str, job_id: str, status: str, scheduled_at: Optional[str] = None):
    assert_write_permission(component, MemoryDomain.DECISIONS)
    with _get_conn() as conn:
        if scheduled_at:
            conn.execute(
                "UPDATE execution_verification_queue SET status = ?, scheduled_at = ?, attempts = attempts + 1 WHERE id = ?",
                (status, scheduled_at, job_id)
            )
        else:
            conn.execute(
                "UPDATE execution_verification_queue SET status = ?, attempts = attempts + 1 WHERE id = ?",
                (status, job_id)
            )

# =====================================================================
# OWEN NEGATIVE PATTERNS
# =====================================================================

def get_negative_pattern(component: str, action_type: str, failure_key: str) -> Optional[Dict[str, Any]]:
    assert_read_permission(component, MemoryDomain.OWEN_INSIGHTS)
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM owen_negative_patterns WHERE action_type = ? AND failure_key = ?",
            (action_type, failure_key)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

def get_patterns_for_action(component: str, action_type: str) -> List[Dict[str, Any]]:
    assert_read_permission(component, MemoryDomain.OWEN_INSIGHTS)
    with _get_conn() as conn:
        cursor = conn.execute(
            "SELECT * FROM owen_negative_patterns WHERE action_type = ?",
            (action_type,)
        )
        return [dict(row) for row in cursor.fetchall()]

def upsert_negative_pattern(component: str, action_type: str, failure_key: str):
    assert_write_permission(component, MemoryDomain.OWEN_INSIGHTS)
    now_ts = datetime.utcnow().isoformat()
    existing = get_negative_pattern(component, action_type, failure_key)
    
    with _get_conn() as conn:
        if existing:
            new_count = existing["count"] + 1
            penalty = min(0.05 * new_count, 0.3)
            conn.execute(
                "UPDATE owen_negative_patterns SET count = ?, penalty = ?, last_seen = ? WHERE id = ?",
                (new_count, penalty, now_ts, existing["id"])
            )
        else:
            conn.execute(
                "INSERT INTO owen_negative_patterns (action_type, failure_key, count, penalty, last_seen) VALUES (?, ?, 1, 0.05, ?)",
                (action_type, failure_key, now_ts)
            )
