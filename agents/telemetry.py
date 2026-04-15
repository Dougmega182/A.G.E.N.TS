from datetime import datetime
from typing import Dict, Any

class TelemetryManager:
    def __init__(self):
        self.total_tokens = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_cost_aud = 0.0
        self.total_cost_usd = 0.0
        self.messages_processed = 0
        self.last_updated = datetime.utcnow().isoformat()

    def record(self, usage: Dict[str, int], model_name: str = "default"):
        """
        Record usage for a single request. 
        Expected usage format: {"input_tokens": int, "output_tokens": int, "total_tokens": int}
        """
        normalized = self.normalize_usage(usage)
        
        self.input_tokens += normalized["input_tokens"]
        self.output_tokens += normalized["output_tokens"]
        self.total_tokens += normalized["total_tokens"]
        self.messages_processed += 1
        
        costs = self.calculate_cost(normalized, model_name)
        self.total_cost_usd += costs["usd"]
        self.total_cost_aud += costs["aud"]
        
        self.last_updated = datetime.utcnow().isoformat()

    def normalize_usage(self, raw: Dict[str, Any]) -> Dict[str, int]:
        """Normalize usage across different providers."""
        # LangChain often provides usage_metadata with these keys
        return {
            "input_tokens": raw.get("input_tokens") or raw.get("prompt_tokens") or 0,
            "output_tokens": raw.get("output_tokens") or raw.get("completion_tokens") or 0,
            "total_tokens": raw.get("total_tokens") or 0
        }

    def calculate_cost(self, usage: Dict[str, int], model_name: str) -> Dict[str, float]:
        """
        Calculate cost based on 2026 pricing estimates.
        Base rates (USD per 1M tokens):
        - Gemini/Flash: $0.075 in / $0.30 out
        - Default fallback: slightly higher safety margin
        """
        # Pricing per 1M tokens (USD)
        rates = {
            "gemini-2.5-flash": {"in": 0.075, "out": 0.30},
            "gemini-3.1-flash": {"in": 0.075, "out": 0.30},
            "claude-3-5-sonnet-20240620": {"in": 3.00, "out": 15.00}, # SONNET is more expensive
            "default": {"in": 0.10, "out": 0.40}
        }
        
        # Get rate or fallback
        rate = rates.get(model_name, rates["default"])
        
        in_cost = (usage["input_tokens"] * rate["in"]) / 1_000_000
        out_cost = (usage["output_tokens"] * rate["out"]) / 1_000_000
        
        usd = in_cost + out_cost
        aud = usd * 1.5 # 2026 rough conversion factor as requested
        
        return {"usd": usd, "aud": aud}

    def get_stats(self) -> Dict[str, Any]:
        return {
            "tokens": self.total_tokens,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_aud": round(self.total_cost_aud, 4),
            "cost_usd": round(self.total_cost_usd, 4),
            "messages_processed": self.messages_processed,
            "last_updated": self.last_updated
        }

# Global instance
TELEMETRY = TelemetryManager()
