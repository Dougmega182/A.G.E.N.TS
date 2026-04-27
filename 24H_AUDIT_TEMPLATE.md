# 24-Hour Shadow Audit Decision Template

Fill this out at the 24-hour checkpoint (Checkpoint Alpha). Use a mechanical read of the data from `events.log.jsonl` and `SHADOW_AUDIT_SUMMARY` events.

---

```text
[24H SHADOW AUDIT SNAPSHOT]

AUTO_ACT_RATE:
- SAFE: ___%
- CONTROLLED: ___%

OVERRIDE MIX:
- cosmetic: ___%
- context_miss: ___%
- critical_error: ___%

APPROVAL_RATIO: ___%

SAFETY FLAGS:
- critical_auto_act_detected: YES / NO
- critical_error >5%: YES / NO

PATTERN READ:
- (one line only: STABLE / OVERCONFIDENT / TOO TIMID / UNSTABLE)

ACTION:
- CONTINUE / TIGHTEN / PAUSE
```

---

## Decision Logic (Fast Execution)

### 1. PAUSE Immediately
- **Condition:** Any safety flag is **YES** or system behavior is chaotic/inconsistent.
- **Action:** Set `AGENTS_SHADOW_MODE=true` (force) and halt autonomy logic.

### 2. TIGHTEN
- **Condition:** CONTROLLED auto-act > 30% OR `context_miss` noticeably high OR `approval_ratio` dropping too fast.
- **Action:** Increase CONTROLLED threshold (e.g., 0.85 -> 0.90) and increase `context_miss` penalty weights.

### 3. CONTINUE (Default)
- **Condition:** Metrics within expected bands, no safety flags, behavior feels consistent.
- **Action:** Do nothing. Let it run to Checkpoint Beta (48h).

### 4. TOO TIMID
- **Condition:** `approval_ratio` > 85% OR `SAFE` tier not auto-acting enough.
- **Action:** Wait for Checkpoint Beta (48h) before lowering thresholds.
