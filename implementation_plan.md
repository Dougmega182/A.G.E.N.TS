# Phase 4: External System Orchestration

This phase transitions the A.G.E.N.T.S. platform from internal governance to controlled actuation.
The goal is **hands with contracts**, not hands with freedom.

## Adjusted Plan (Post-Feedback)

> [!IMPORTANT]
> The original plan was missing an **immutable action contract boundary**. All four structural
> corrections from the Gatekeeper review have been incorporated.

---

## Execution Order (non-negotiable)

### Step 1 — `action_intent_v1` Contract [GATE: must pass before Step 2]

#### [NEW] [contracts/action_intent_v1.json](file:///e:/Ai/WORK-IN-PROGRESS/A.G.E.N.T.S/contracts/action_intent_v1.json)
Schema defining the frozen intent object:
- `action` (string) — e.g., `send_email`, `create_event`
- `agent_id` (string) — e.g., `AGT-009`
- `parameters` (object) — the exact payload to be executed
- `trace_id` (string)
- `requires_approval` (bool, always `true`)
- `status` (enum: `pending | approved | rejected`)

#### [MODIFY] [agents/contracts.py](file:///e:/Ai/WORK-IN-PROGRESS/A.G.E.N.T.S/agents/contracts.py)
- Add `validate_action_intent(payload)` — validates & freezes an `action_intent_v1` object.
- Once an intent is created, it is **immutable**. Execution must receive the same object that was approved.

#### [MODIFY] [agents/firewall.py](file:///e:/Ai/WORK-IN-PROGRESS/A.G.E.N.T.S/agents/firewall.py)
- `PreflightApprovalEngine` enriched to store and retrieve `action_intent_v1` objects by `trace_id`.
- `ensure_approved()` now validates the executing payload matches the approved intent hash exactly.

---

### Step 2 — Wire Operators to Contract

#### [MODIFY] [agents/google_operator.py](file:///e:/Ai/WORK-IN-PROGRESS/A.G.E.N.T.S/agents/google_operator.py)
- `GmailOperator.send_draft_for_review()` and `CalendarOperator.create_event()` must:
  1. Create an `action_intent_v1` object via the contract module.
  2. Emit `ACTION_INTENT_CREATED` to the event bus.
  3. Call `PreflightApprovalEngine.ensure_approved()` — blocks if `status != approved`.
  4. Execute **only if** approved, using the **exact frozen parameters**.
  5. Emit `ACTION_EXECUTED` with the intent hash for audit linkage.

---

### Step 3 — SSE Events Endpoint

#### [MODIFY] [agents/api.py](file:///e:/Ai/WORK-IN-PROGRESS/A.G.E.N.T.S/agents/api.py)
- Add `GET /events/stream` — SSE endpoint that tails `events.log.jsonl` in real-time.
- This maps 1:1 with the existing event bus, no polling required.

---

### Step 4 — Command Center Dashboard (Dark, Minimal, Palantir-lite)

#### [MODIFY] [web/index.html](file:///e:/Ai/WORK-IN-PROGRESS/A.G.E.N.T.S/web/index.html)
- Full redesign. Dark mode, clean typography, no sci-fi gimmickry.
- **Chat Panel**: Streaming agent responses.
- **Live Event Feed**: SSE-connected tail of `events.log.jsonl`, color-coded by event type.
- **Approval Queue**: Displays pending `action_intent_v1` objects with Approve/Reject controls.
- **Project Health**: Numerical risk trend display (5-avg vs 10-avg).
- **Agent Roster**: Static grid — names, titles, IDs.

---

### Step 5 — Morning Brief (Data-First Architecture)

#### [MODIFY] [agents/orchestrator.py](file:///e:/Ai/WORK-IN-PROGRESS/A.G.E.N.T.S/agents/orchestrator.py)
- Recognize `morning brief` trigger prefix.
- **Step 5a (Data Layer — System)**: System fetches emails + calendar events from operators.
- **Step 5b (Reasoning — Jenny)**: Jenny receives pre-fetched data as context, builds the brief.
- Jenny does **not** call tools dynamically — inputs are deterministic, output is replayable.

---

## Constraints (Hard Rules)

- No auto-send emails — ever
- No silent calendar writes — ever
- No agent-triggered external execution without `action_intent_v1` approval
- UI aesthetic: dark, clean, minimal — not cyberpunk

## Verification Plan

### Automated
- `python run_telemetry_replay_test.py` — event lineage must remain intact.
- New: `run_phase4_integration_test.py` — validates action_intent creation, blocking, and approval flow.

### Manual
1. Launch via `launch.ps1`, open dashboard.
2. Trigger `Morning Brief` via chat.
3. Verify `ACTION_INTENT_CREATED` appears in the event feed.
4. Confirm the approval queue shows the pending intent.
5. Approve it — verify `ACTION_EXECUTED` appears with matching intent hash.
