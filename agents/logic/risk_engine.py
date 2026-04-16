import re

def calculate_risk_score(scenario_type: str, cost: float, days: int, reason: str) -> float:
    """
    Scaled & Scenario-Aware Risk Engine:
    - variation: cost/50k (max 0.5) + days/10 (max 0.3)
    - delay: days/7 (max 0.5)
    - rfi: uncertainty keywords (+0.2)
    """
    scenario_type = scenario_type.lower()
    cost_risk = 0.0
    delay_risk = 0.0
    keyword_risk = 0.0
    
    if scenario_type == "variation":
        cost_risk = min(cost / 50000.0, 0.5)
        delay_risk = min(days / 10.0, 0.3)
    elif scenario_type == "delay":
        delay_risk = min(days / 7.0, 0.5)
        if reason and any(k in reason.lower() for k in ["rain", "weather", "storm"]):
            keyword_risk += 0.2
    elif scenario_type == "rfi":
        if reason and any(k in reason.lower() for k in ["unclear", "missing", "ambiguous", "contradiction"]):
            keyword_risk += 0.2
        if reason and any(k in reason.lower() for k in ["structural", "foundation", "safety"]):
            keyword_risk += 0.2

    # Baseline keywords
    if reason and "drainage" in reason.lower() and scenario_type != "delay":
        keyword_risk += 0.2
        
    total_score = min(cost_risk + delay_risk + keyword_risk, 1.0)
    return round(total_score, 2)

def calculate_risk_trend(history: list) -> dict:
    """
    Smoothed Risk Trend (5-vs-10 comparison):
    - avg_5: last 5 entries
    - avg_10: last 10 entries
    - threshold: ±0.05
    """
    if not history:
        return {"direction": "stable", "avg_5": 0.0, "avg_10": 0.0}
    
    scores = [h.get("risk_score", 0.0) for h in history]
    
    last_5 = scores[-5:]
    last_10 = scores[-10:]
    
    avg_5 = sum(last_5) / len(last_5)
    avg_10 = sum(last_10) / len(last_10)
    
    direction = "stable"
    if avg_5 > avg_10 + 0.05:
        direction = "increasing"
    elif avg_5 < avg_10 - 0.05:
        direction = "decreasing"
        
    return {
        "direction": direction,
        "avg_5": round(avg_5, 2),
        "avg_10": round(avg_10, 2)
    }
