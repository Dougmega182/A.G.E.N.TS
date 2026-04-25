from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


_COST_PATTERNS = (
    re.compile(r"cost\s+impact\s*:?\s*\$?\s*([+-]?\d[\d,]*(?:\.\d+)?)\s*([km]?)", re.IGNORECASE),
    re.compile(r"\+\$\s*([+-]?\d[\d,]*(?:\.\d+)?)\s*([km]?)", re.IGNORECASE),
)

_DELAY_PATTERNS = (
    re.compile(r"delay\s*:?\s*\+?\s*([+-]?\d[\d,]*(?:\.\d+)?)\s*(minutes?|hours?|days?)", re.IGNORECASE),
    re.compile(r"\+\s*([+-]?\d[\d,]*(?:\.\d+)?)\s*(minutes?|hours?|days?)", re.IGNORECASE),
)

_AMBIGUOUS_DELAY_PATTERNS = (
    re.compile(r"\b\d[\d,]*(?:\.\d+)?\s*(k|m|%)\s*(delay|days?|hours?|minutes?)\b", re.IGNORECASE),
    re.compile(r"\b(delay|schedule)\b[^\n\r]{0,24}\b\d[\d,]*(?:\.\d+)?\s*(k|m|%)\b", re.IGNORECASE),
)

_MAX_ABS_COST = {
    "variation": 5_000_000.0,
    "delay": 5_000_000.0,
    "rfi": 5_000_000.0,
    "site_issue": 5_000_000.0,
}

MAX_DELAY_DAYS_SOFT = 30.0
MAX_DELAY_DAYS_HARD = 40.0

_MAX_DELAY_DAYS = {
    "variation": MAX_DELAY_DAYS_HARD,
    "delay": MAX_DELAY_DAYS_HARD,
    "rfi": MAX_DELAY_DAYS_HARD,
    "site_issue": MAX_DELAY_DAYS_HARD,
}


@dataclass(frozen=True)
class InputSanitisationResult:
    valid: bool
    status: str
    reason: str
    suggestion: str
    severity: str = "NORMAL"
    cost: float = 0.0
    days: int = 0
    cost_source: str = ""
    delay_source: str = ""


def _parse_number(raw: str) -> float:
    return float(str(raw).replace(",", "").strip())


def _parse_cost(raw_value: str, suffix: str) -> float:
    value = _parse_number(raw_value)
    suffix = str(suffix or "").strip().lower()
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    return value


def _convert_to_days(raw_value: str, unit: str) -> float:
    value = _parse_number(raw_value)
    unit = unit.strip().lower()
    if unit.startswith("minute"):
        return value / 1440.0
    if unit.startswith("hour"):
        return value / 24.0
    return value


def _first_match(patterns: tuple[re.Pattern[str], ...], text: str) -> Optional[re.Match[str]]:
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match
    return None


def sanitise_construction_input(scenario_type: str, user_input: str) -> InputSanitisationResult:
    scenario_key = str(scenario_type or "").strip().lower()
    raw_input = str(user_input or "")

    for pattern in _AMBIGUOUS_DELAY_PATTERNS:
        bad = pattern.search(raw_input)
        if bad:
            return InputSanitisationResult(
                valid=False,
                status="INVALID_INPUT",
                reason="AMBIGUOUS_DELAY_UNIT",
                suggestion="RFI_REQUIRED",
            )

    if "%" in raw_input:
        return InputSanitisationResult(
            valid=False,
            status="INVALID_INPUT",
            reason="PERCENTAGE_NOT_ALLOWED",
            suggestion="RFI_REQUIRED",
        )

    cost_match = _first_match(_COST_PATTERNS, raw_input)
    if not cost_match:
        return InputSanitisationResult(
            valid=False,
            status="INVALID_INPUT",
            reason="MISSING_COST_FIELD",
            suggestion="RFI_REQUIRED",
        )

    delay_match = _first_match(_DELAY_PATTERNS, raw_input)
    if not delay_match:
        return InputSanitisationResult(
            valid=False,
            status="INVALID_INPUT",
            reason="MISSING_DELAY_UNIT",
            suggestion="RFI_REQUIRED",
        )

    cost = _parse_cost(cost_match.group(1), cost_match.group(2))
    delay_days = _convert_to_days(delay_match.group(1), delay_match.group(2))

    max_cost = _MAX_ABS_COST.get(scenario_key, 5_000_000.0)
    max_delay = _MAX_DELAY_DAYS.get(scenario_key, 365.0)

    if abs(cost) > max_cost:
        return InputSanitisationResult(
            valid=False,
            status="INVALID_INPUT",
            reason="COST_OUT_OF_BOUNDS",
            suggestion="RFI_REQUIRED",
        )

    if delay_days < 0 or delay_days > max_delay:
        return InputSanitisationResult(
            valid=False,
            status="INVALID_INPUT",
            reason="SCALE_OUT_OF_BOUNDS",
            suggestion="RFI_REQUIRED",
        )

    severity = "HIGH_DELAY" if delay_days > MAX_DELAY_DAYS_SOFT else "NORMAL"

    return InputSanitisationResult(
        valid=True,
        status="PASS",
        reason="OK",
        suggestion="PASS",
        severity=severity,
        cost=cost,
        days=int(round(delay_days)),
        cost_source=cost_match.group(0),
        delay_source=delay_match.group(0),
    )
