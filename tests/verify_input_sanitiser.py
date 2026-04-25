from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.logic.input_sanitiser import sanitise_construction_input


def main() -> int:
    ok = sanitise_construction_input(
        "variation",
        "Variation: +$12000, +3 days, Roof flashing rework",
    )
    assert ok.valid is True
    assert ok.cost == 12000.0
    assert ok.days == 3

    hours = sanitise_construction_input(
        "delay",
        "Delay: +$0, +48 hours, Crane outage",
    )
    assert hours.valid is True
    assert hours.days == 2

    still_allowed = sanitise_construction_input(
        "site_issue",
        "Issue: roof flashing defect. Cost impact: $2000. Delay: 30 days.",
    )
    assert still_allowed.valid is True
    assert still_allowed.days == 30
    assert still_allowed.severity == "NORMAL"

    high_delay = sanitise_construction_input(
        "site_issue",
        "Issue: roof flashing defect. Cost impact: $2000. Delay: 35 days.",
    )
    assert high_delay.valid is True
    assert high_delay.days == 35
    assert high_delay.severity == "HIGH_DELAY"

    hard_block = sanitise_construction_input(
        "site_issue",
        "Issue: roof flashing defect. Cost impact: $2000. Delay: 45 days.",
    )
    assert hard_block.valid is False
    assert hard_block.reason == "SCALE_OUT_OF_BOUNDS"

    ambiguous = sanitise_construction_input(
        "delay",
        "Delay: +$0, 200000k delay, roof flashing issue",
    )
    assert ambiguous.valid is False
    assert ambiguous.reason == "AMBIGUOUS_DELAY_UNIT"

    percent = sanitise_construction_input(
        "variation",
        "Variation: cost impact $5000 | delay 178% schedule overrun",
    )
    assert percent.valid is False
    assert percent.reason == "PERCENTAGE_NOT_ALLOWED"

    huge = sanitise_construction_input(
        "site_issue",
        "Issue: flashing defect. Cost impact: $50000000. Delay: 2 days.",
    )
    assert huge.valid is False
    assert huge.reason == "COST_OUT_OF_BOUNDS"

    print("Input sanitiser verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
