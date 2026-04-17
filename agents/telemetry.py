from datetime import datetime
from typing import Dict, Any

class TelemetryManager:
    def __init__(self):
        self.total_tokens = 0
        self.gemini_tokens = 0
        self.ollama_tokens = 0
        
        self.total_cost_aud = 0.0
        self.gemini_cost_aud = 0.0
        self.ollama_saved_aud = 0.0 # Cost avoided by using local models
        
        self.messages_processed = 0
        self.last_updated = datetime.utcnow().isoformat()

    def record(self, usage: Dict[str, int], model_name: str = "default"):
        """
        Record usage for a single request. 
        """
        normalized = self.normalize_usage(usage)
        
        tokens = normalized["total_tokens"]
        self.total_tokens += tokens
        self.messages_processed += 1
        
        costs = self.calculate_cost(normalized, model_name)
        
        # Categorize by model provider
        m_lower = model_name.lower()
        if "gemini" in m_lower:
            self.gemini_tokens += tokens
            self.gemini_cost_aud += costs["aud"]
        elif "ollama" in m_lower or m_lower == "local" or "llama" in m_lower:
            self.ollama_tokens += tokens
            # "Saved" is what it WOULD have cost on a standard paid model
            self.ollama_saved_aud += costs["aud_saved"]
        else:
            # Fallback
            self.gemini_tokens += tokens
            self.gemini_cost_aud += costs["aud"]

        self.total_cost_aud = self.gemini_cost_aud
        self.last_updated = datetime.utcnow().isoformat()

    def normalize_usage(self, raw: Dict[str, Any]) -> Dict[str, int]:
        return {
            "input_tokens": raw.get("input_tokens") or raw.get("prompt_tokens") or 0,
            "output_tokens": raw.get("output_tokens") or raw.get("completion_tokens") or 0,
            "total_tokens": raw.get("total_tokens") or 0
        }

    def calculate_cost(self, usage: Dict[str, int], model_name: str) -> Dict[str, float]:
        # Pricing per 1M tokens (USD) - 2026 Estimates
        rates = {
            "gemini-3-flash-preview": {"in": 0.075, "out": 0.30},
            "default": {"in": 0.10, "out": 0.40}
        }
        
        rate = rates.get(model_name, rates["default"])
        
        in_cost = (usage["input_tokens"] * rate["in"]) / 1_000_000
        out_cost = (usage["output_tokens"] * rate["out"]) / 1_000_000
        
        usd = in_cost + out_cost
        aud = usd * 1.5 
        
        return {
            "usd": usd, 
            "aud": aud,
            "aud_saved": aud # Used for local model savings calculation
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_tokens": self.total_tokens,
            "gemini_tokens": self.gemini_tokens,
            "ollama_tokens": self.ollama_tokens,
            "gemini_cost_aud": round(self.gemini_cost_aud, 4),
            "ollama_saved_aud": round(self.ollama_saved_aud, 4),
            "messages_processed": self.messages_processed,
            "last_updated": self.last_updated
        }

# Global instance
TELEMETRY = TelemetryManager()
