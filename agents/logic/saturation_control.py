"""
Saturation Control — Control Layer (Aria)
Prevents operator fatigue and noise amplification by enforcing rate limits,
cooldowns per entity, and burst detection.
"""

import hashlib
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from .memory_db import read_decisions

logger = logging.getLogger("agents.saturation_control")

# --- STATIC POLICIES ---
COOLDOWN_WINDOW_MINUTES = 20
RATE_LIMIT_WINDOW_MINUTES = 10
MAX_ACTIONS_PER_RATE_WINDOW = 3
BURST_WINDOW_SECONDS = 120
BURST_THRESHOLD = 5

class SaturationControl:
    """
    Enforces operational boundaries on decision frequency.
    """

    @staticmethod
    def extract_entity_id(scenario_type: str, user_input: str) -> str:
        """
        Heuristic extraction of an Entity ID from the user input.
        Looks for patterns like 'Site A', 'Job 123', 'Project 45', or fallback to issue hash.
        """
        # 1. Look for explicit Site/Job patterns
        patterns = [
            re.compile(r"(?:site|job|project)\s*[:#-]?\s*([a-z0-9_-]+)", re.IGNORECASE),
            re.compile(r"(?:id|ref)\s*[:#-]?\s*([a-z0-9_-]+)", re.IGNORECASE),
        ]
        
        for p in patterns:
            match = p.search(user_input)
            if match:
                return f"{scenario_type}_{match.group(1).upper()}"
        
        # 2. Fallback: Content fingerprint (minus numbers/costs/dates to group similar issues)
        # We strip numbers to treat "Spill of 10L" and "Spill of 20L" as same entity if text matches
        fingerprint_text = re.sub(r"\d+", "", user_input.lower()).strip()
        # Take first 50 chars for the hash base
        clean_base = "".join(e for e in fingerprint_text[:50] if e.isalnum())
        h = hashlib.sha256(clean_base.encode()).hexdigest()[:8].upper()
        return f"{scenario_type}_SIG_{h}"

    @classmethod
    def check_saturation(
        cls, 
        scenario_type: str, 
        user_input: str, 
        intent_type: str,
        trace_id: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Evaluate all saturation rules.
        Returns: (status, metadata)
        Status: PASS | COOLDOWN_ACTIVE | RATE_LIMIT_EXCEEDED | BURST_DETECTED
        """
        entity_id = cls.extract_entity_id(scenario_type, user_input)
        
        # 1. Fetch recent history (last 60 mins to cover all windows)
        recent_history = read_decisions("orchestrator", limit=100, days_back=None)
        # Filter for last hour manually as timestamp is ISO string
        hour_ago = (datetime.utcnow() - timedelta(minutes=60)).isoformat()
        recent = [d for d in recent_history if d.get("timestamp", "") >= hour_ago]
        
        # 2. Rule: Cooldown per Entity
        cooldown_cutoff = (datetime.utcnow() - timedelta(minutes=COOLDOWN_WINDOW_MINUTES)).isoformat()
        # Explicit check on entity_id field
        entity_matches = [d for d in recent if d.get("timestamp", "") >= cooldown_cutoff and d.get("entity_id") == entity_id]
        
        if entity_matches:
            return "COOLDOWN_ACTIVE", {
                "entity_id": entity_id,
                "reason": f"Entity {entity_id} is in cooldown window ({COOLDOWN_WINDOW_MINUTES}m).",
                "last_match_trace": entity_matches[0].get("trace_id")
            }

        # 3. Rule: Rate Limit per Intent Type
        rate_cutoff = (datetime.utcnow() - timedelta(minutes=RATE_LIMIT_WINDOW_MINUTES)).isoformat()
        intent_matches = [d for d in recent if d.get("timestamp", "") >= rate_cutoff and d.get("scenario") == scenario_type]
        
        if len(intent_matches) >= MAX_ACTIONS_PER_RATE_WINDOW:
            return "RATE_LIMIT_EXCEEDED", {
                "scenario": scenario_type,
                "count": len(intent_matches),
                "window": f"{RATE_LIMIT_WINDOW_MINUTES}m",
                "reason": f"Exceeded {MAX_ACTIONS_PER_RATE_WINDOW} actions per {RATE_LIMIT_WINDOW_MINUTES}m for {scenario_type}."
            }

        # 4. Rule: Burst Detection
        burst_cutoff = (datetime.utcnow() - timedelta(seconds=BURST_WINDOW_SECONDS)).isoformat()
        burst_matches = [d for d in recent if d.get("timestamp", "") >= burst_cutoff]
        
        if len(burst_matches) >= BURST_THRESHOLD:
            return "BURST_DETECTED", {
                "count": len(burst_matches),
                "window": f"{BURST_WINDOW_SECONDS}s",
                "reason": "System-wide burst detected. Forcing operator review."
            }

        return "PASS", {"entity_id": entity_id}
