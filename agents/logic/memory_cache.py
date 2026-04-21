"""
Memory Cache — Redis-backed hot cache with graceful in-memory fallback.

TIER 1 (hot): Zero-latency lookup during agent execution loops.

Behavior:
    - If Redis is available → use it (distributed, persistent across restarts)
    - If Redis is not available → use in-memory dict (per-process, ephemeral)
    - System NEVER degrades functionality, only performance

This is ephemeral data — can be rebuilt from SQLite or events at any time.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .memory_contract import (
    MemoryDomain,
    assert_write_permission,
    assert_read_permission,
    RETENTION,
)

logger = logging.getLogger("agents.memory_cache")

# Try to import redis; graceful if missing
_redis_client = None
_redis_available = False

try:
    import redis
    _redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
    _redis_client.ping()
    _redis_available = True
    logger.info("[MEMORY_CACHE] Redis connected — using distributed cache")
except Exception:
    _redis_available = False
    logger.info("[MEMORY_CACHE] Redis unavailable — using in-memory fallback")
    from .event_bus import emit_event
    emit_event("CACHE_MODE_FALLBACK", "system", metadata={"backend": "in-memory"})

import os
# In-memory fallback store
_memory_store: Dict[str, Any] = {}

# Key prefix for namespacing — allow override for tests
_PREFIX = os.getenv("REDIS_PREFIX", "agents:")


# =====================================================================
# LOW-LEVEL CACHE OPERATIONS
# =====================================================================

def _set(key: str, value: str, ttl: int = RETENTION.cache_ttl_seconds) -> None:
    """Set a cache value with TTL."""
    full_key = f"{_PREFIX}{key}"
    if _redis_available and _redis_client:
        _redis_client.setex(full_key, ttl, value)
    else:
        _memory_store[full_key] = {
            "value": value,
            "expires": datetime.utcnow().timestamp() + ttl
        }


def _get(key: str) -> Optional[str]:
    """Get a cache value. Returns None if expired or missing."""
    full_key = f"{_PREFIX}{key}"
    if _redis_available and _redis_client:
        return _redis_client.get(full_key)
    else:
        entry = _memory_store.get(full_key)
        if entry is None:
            return None
        if datetime.utcnow().timestamp() > entry["expires"]:
            del _memory_store[full_key]
            return None
        return entry["value"]


def _delete(key: str) -> None:
    """Delete a cache key."""
    full_key = f"{_PREFIX}{key}"
    if _redis_available and _redis_client:
        _redis_client.delete(full_key)
    else:
        _memory_store.pop(full_key, None)


def _delete_pattern(pattern: str) -> None:
    """Delete all keys matching a pattern."""
    full_pattern = f"{_PREFIX}{pattern}"
    if _redis_available and _redis_client:
        for key in _redis_client.scan_iter(full_pattern):
            _redis_client.delete(key)
    else:
        to_delete = [k for k in _memory_store if k.startswith(full_pattern.replace("*", ""))]
        for k in to_delete:
            del _memory_store[k]


# =====================================================================
# PUBLIC API — Boundary-enforced cache operations
# =====================================================================

def cache_reasoning_context(
    component: str, trace_id: str, context: Dict[str, Any]
) -> None:
    """Cache the reasoning context for a specific loop iteration."""
    assert_write_permission(component, MemoryDomain.CACHE)
    _set(f"context:{trace_id}", json.dumps(context))


def get_reasoning_context(component: str, trace_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached reasoning context for a loop."""
    assert_read_permission(component, MemoryDomain.CACHE)
    raw = _get(f"context:{trace_id}")
    return json.loads(raw) if raw else None


def cache_owen_briefing(
    component: str, scenario_type: str, briefing: Dict[str, Any]
) -> None:
    """Cache Owen's intelligence briefing for a scenario type."""
    assert_write_permission(component, MemoryDomain.CACHE)
    _set(f"owen_briefing:{scenario_type}", json.dumps(briefing))


def get_owen_briefing(component: str, scenario_type: str) -> Optional[Dict[str, Any]]:
    """Retrieve Owen's cached intelligence briefing."""
    assert_read_permission(component, MemoryDomain.CACHE)
    raw = _get(f"owen_briefing:{scenario_type}")
    return json.loads(raw) if raw else None


def cache_recent_decisions(
    component: str, scenario_type: str, decisions: list
) -> None:
    """Cache pre-computed recent decisions for fast lookup."""
    assert_write_permission(component, MemoryDomain.CACHE)
    _set(f"recent_decisions:{scenario_type}", json.dumps(decisions))


def get_recent_decisions(component: str, scenario_type: str) -> Optional[list]:
    """Retrieve cached recent decisions."""
    assert_read_permission(component, MemoryDomain.CACHE)
    raw = _get(f"recent_decisions:{scenario_type}")
    return json.loads(raw) if raw else None


def invalidate_loop(component: str, trace_id: str) -> None:
    """Clean up all cache entries for a completed loop."""
    assert_write_permission(component, MemoryDomain.CACHE)
    _delete(f"context:{trace_id}")


def get_cache_status() -> Dict[str, Any]:
    """Return cache backend status for observability."""
    return {
        "backend": "redis" if _redis_available else "memory",
        "connected": _redis_available,
        "fallback_entries": len(_memory_store) if not _redis_available else 0,
    }

def clear_cache(component: str) -> None:
    """Clear all keys in the current namespace. USE WITH CAUTION (primarily for tests)."""
    assert_write_permission(component, MemoryDomain.CACHE)
    _delete_pattern("*")
