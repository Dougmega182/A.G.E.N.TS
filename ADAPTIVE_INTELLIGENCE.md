# Adaptive Decision Intelligence (BUILD REV 3.5.0)

This document defines the **Self-Correction Layer** of the A.G.E.N.T.S. platform. It shifts the system from "Blind Execution" to "Deterministic Skepticism" by closing the loop between execution reality and agent decision-making.

---

## 1. The Drift Pressure Index (DPI)
(Calculated per scenario type since Build 3.2.0)

The DPI is the primary unit of system skepticism. It is a dynamic multiplier that throttles the confidence required for an agent to move from `APPROVE` to `EXECUTE`.

---

## 5. Inference Caching (Layer 1 & 2)

As of Phase 5.1.5, the system implements **deterministic inference caching** to minimize cost and latency while preserving safety.

### Layer 1: Deterministic Context Matching
The cache is keyed on the **Abstracted Hash**:
`Key = SHA256(Scenario || Normalized_Issue || Cost_Bucket || Delay_Bucket || Gov_Flags || Policy_Version)`

### Layer 2: Semantic Expansion (The "Honest Baseline")
To increase recall without sacrificing precision, we use:
*   **Parameter Abstraction**: Specific numbers (150mm) and drawing refs (A-102) are replaced with `{measurement}` and `{drawing}` placeholders.
*   **Phrase Mapping**: Multi-word terms (e.g., "port strike") are canonicalized before tokenization.
*   **Token Sorting**: Cache keys are bag-of-words stable (e.g., "rain delay" == "delay rain").

**Bypass Matrix:** The cache is automatically bypassed if the **DPI > 0.3** or **CRITICAL** governance flags are active.

---

## 6. Momentum Engine (Phase 2 Logistics)

The Momentum Engine translates abstracted issues into **Operational Vectors**.

### The Handshake (momentum_signal_v1)
*   **Velocity Impact**: Predicted change in project speed (-1.0 to +1.0).
*   **Trend Direction**: `STALL | DRAG | STABLE | ACCEL`.
*   **Confidence Score**: Heuristic based on domain alignment and signal clarity.

### Deterministic Actuation (Eli Adapter)
Eli consumes these signals to generate **Action Intents**:
*   `DRAG` → `STABILISE` (Dispatched to Foreman for efficiency audit)
*   `ACCEL` → `PRIORITISE` (Dispatched to Executive for fast-track)

**Safety Protocol:** No logistics intent is executed until it passes the **Operator Dispatch Gate**.

---

### The Formula
$$DPI = \frac{\sum{Penalties_{Component}}}{ConfidenceThreshold}$$

*   **Penalty**: A localized score (0.01 - 0.30) assigned to specific failure modes (e.g., `gmail_draft.subject`).
*   **Threshold**: The baseline confidence (usually 0.60).
*   **Effect**: As DPI approachs 1.0, the system enters **Force-Escalation Mode**, where even high-confidence agent decisions are blocked for safety.

---

## 2. The Truth Model (3-Phase Validation)

We no longer trust "API SUCCESS" as a signal of reality. Every actuation must pass a 3-phase truth check:

| Phase | Metric | Truth Level | Description |
|---|---|---|---|
| **1** | `api_ack` | **Low** | The service acknowledged the request (HTTP 200). |
| **2** | `read_back` | **Medium** | The object (Draft/Event) was successfully retrieved via GET after creation. |
| **3** | `semantic_match` | **High** | The internal fields (Subject, Recipient, Body) match the agent's intent. |

**Execution Drift** is defined as the delta between Phase 1 and Phase 3.

---

## 3. Failure Taxonomy

The verification daemon classifies every execution outcome into one of four states:

1.  **TRANSIENT**: Object not found initially (potential eventual consistency). Retried automatically.
2.  **DEGRADED_SUCCESS**: Object found and matched, but required multiple attempts or experienced high latency.
3.  **DRIFT_CONFIRMED**: Object exists but its data does not match the intent (e.g., Subject was truncated or Recipient was altered by the API).
4.  **TRUE_FAILURE**: The object was never created or the API returned a hard error.

---

## 4. The Intelligence Loop (Case Study)

The "Moat" of A.G.E.N.T.S. is the **Approve → Fail → Learn → Block** loop.

### Scenario: The Gmail subject drift
1.  **Approve**: Aria approves a draft creation with 0.95 confidence.
2.  **Fail**: The Gmail API silently truncates the subject due to an encoding quirk.
3.  **Learn**: The Verification Daemon detects `DRIFT_CONFIRMED` and feeds the `subject` failure key back to **Owen**.
4.  **Block**: In the next turn, Owen injects a **Reliability Alert** into the briefing. The DPI for Gmail actions rises to `0.25`. Aria produces 0.90 confidence, but the **Threshold Shift (0.60 -> 0.85)** forces an `ESCALATE` to human oversight.

---
> [!TIP]
> This layer ensures that the system doesn't "hallucinate success." If a tool becomes unreliable, the system effectively "unplugs" itself until reliability is restored.
