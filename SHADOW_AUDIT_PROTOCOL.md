# Shadow Audit Protocol (48-Hour Validation)

This protocol defines the strict evaluation criteria for the A.G.E.N.T.S. platform during its initial Production Shadow Mode.

## 1. Operational Hard-Stop Rules (Act Immediately)
If any of the following occur, **pause the system immediately**:
- **Any CRITICAL auto-act**: If a decision classified as `CRITICAL` bypasses human approval.
- **Critical Error Rate > 5%**: If more than 5% of decisions result in a `critical_error` override.
- **Confidence Inflation**: If `CONTROLLED` auto-act eligibility exceeds 35% in the first 24 hours.

---

## 2. Checkpoint Alpha (T+24 Hours)
**Goal:** Identify initial shape and detect early red flags.

### Healthy Pattern
- **SAFE Tier**: Majority `AUTO_ACT`.
- **CONTROLLED Tier**: Mostly `REQUIRE_APPROVAL`.
- **CRITICAL Tier**: 100% `REQUIRE_APPROVAL`.
- **Override Mix**: Dominated by `cosmetic` tweaks; minimal `context_miss`.

### Action
- If patterns are healthy: **Continue Shadow Mode**.
- If red flags detected: **Tighten thresholds or Pause**.

---

## 3. Checkpoint Beta (T+48 Hours)
**Goal:** Binary decision on autonomy graduation.

### Option A: Expand Autonomy
**Criteria:**
- `critical_error` ≤ 2%.
- `CONTROLLED` auto-act rate ≤ 25%.
- `shadow_accuracy` stable and verified (not rubber-stamped).
**Action:** Lower `CONTROLLED` threshold slightly (e.g., 0.85 → 0.82) for a subset of safe intents.

### Option B: Hold (Default)
**Criteria:** Metrics are stable but not yet "clean" or sample size is too low.
**Action:** Maintain current thresholds; run another 48-hour cycle.

### Option C: Tighten
**Criteria:**
- `context_miss` rate is high.
- `CONTROLLED` auto-act rate > 30%.
- `shadow_accuracy` is high but overrides show significant logic gaps.
**Action:** Increase `CONTROLLED` threshold (0.85 → 0.90) and increase `context_miss` penalty weights.

---

## 4. Manual Observation: Decision Hesitation Latency
During the audit, manually monitor the `events.log.jsonl` for:
- **Clustered Approvals**: Are operators being hit with bursts of `REQUIRE_APPROVAL` decisions?
- **Risk Spikes**: Are signals consistently pushing into higher risk tiers unnecessarily?

If bursts are frequent despite saturation control, the next phase must focus on **Queue Smoothing** rather than autonomy expansion.
