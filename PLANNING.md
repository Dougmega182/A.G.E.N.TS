Recommendation: **don’t try to build the “AI factory + satellite ops centre” all at once — turn A.G.E.N.T.S into a single, audit-ready construction case study first, then scale it into a factory.**

Right now your risk isn’t capability — it’s **scope explosion**.

So we’re going to anchor everything to one thing:

> **A construction AI capability lifecycle that proves planning + reasoning + execution end-to-end**

Once that works → you replicate it into a factory.

---

# 🧠 The architecture you’re actually building

Forget buzzwords. This is the real structure:

```
STRATEGY → PLANNING → EXECUTION → MONITORING → AUDIT → IMPROVEMENT
```

Your agents sit inside that loop.

---

# 🔧 PHASE 1 — Define the Capability (this week)

### Goal:

Turn A.G.E.N.T.S into a **construction project intelligence system**

---

## Step 1 — Define your use case (lock this)

Pick ONE:

> “AI system that manages construction project decisions, risks, comms, and reporting”

Do NOT expand beyond this yet.

---

## Step 2 — Define agent roles (your org chart)

Keep it tight:

```text
Aria → Strategy / decision making  
Nadia → Planning / scheduling  
Jenny → Comms (email, calendar, briefs)  
Ops Agent → Execution tracking (site data, logs)
```

---

## Step 3 — Define outputs (contracts)

You already started this — now formalise:

* morning_brief_v1
* email_draft_v1
* plan_v1
* tool_call_v1

These = your **operational language**

---

## Step 4 — Map to AI planning concepts (this is your uni alignment)

Tie your system to theory:

| Concept     | Your System                              |
| ----------- | ---------------------------------------- |
| State       | Project status (budget, timeline, risks) |
| Actions     | Agent outputs (plans, emails, decisions) |
| Goals       | Project completion, cost control         |
| Planning    | Nadia generating plans                   |
| Multi-agent | Aria + Nadia + Jenny collaboration       |
| Uncertainty | Risks, delays, site issues               |

This is how you turn it into a **formal case study**

---

# ⚙️ PHASE 2 — Planning & Reasoning Engine (next)

### Goal:

Make agents actually **plan**, not just respond

---

## Step 5 — Introduce Planning Loop

Add this inside orchestrator:

```python
state = get_project_state()

plan = planner.generate_plan(goal, state)

for step in plan:
    execute(step)
    update_state()
```

---

## Step 6 — Add heuristic decision making

Example:

```python
if delay_risk > 0.7:
    prioritise("schedule recovery")
```

This = **heuristic search in practice**

---

## Step 7 — Add probabilistic thinking (simple version)

```python
risk_score = weighted_sum([
    weather_risk,
    supplier_delay,
    labour_shortage
])
```

Now you’ve implemented:

> **probabilistic planning (basic but real)**

---

# 🏗️ PHASE 3 — Execution System (you’re halfway here)

### Goal:

Agents don’t talk — they **act**

---

## Step 8 — Expand tool_call_v1

Turn tools into real actions:

* create report
* send email (still gated)
* update schedule
* log incident

---

## Step 9 — Add “state updates”

Every action must update:

```json
{
  "project_status": "...",
  "risks": [...],
  "progress": 65
}
```

This is your **world model**

---

# 📊 PHASE 4 — Monitoring & Audit (this is your edge)

### Goal:

Make it audit-ready (this is where you win)

---

## Step 10 — Add audit logs

Every action:

```json
{
  "agent": "Nadia",
  "action": "create_plan",
  "timestamp": "...",
  "input": "...",
  "output": "...",
  "reasoning_summary": "..."
}
```

---

## Step 11 — Map to standards (keep it simple)

Don’t overcomplicate:

* ISO 42001 (AI management)
* ISO 9001 (quality)
* Basic governance logging

You don’t need full compliance — just **traceability**

---

# 🏭 PHASE 5 — The “Factory” (only AFTER above works)

### Goal:

Repeatable agent deployment

---

## Step 12 — Template system

Create:

```
/templates/
  agent_template/
  contract_template/
  tool_template/
```

---

## Step 13 — Agent generator

Input:

```json
{
  "industry": "construction",
  "role": "scheduler"
}
```

Output:

* agent config
* contracts
* tools

That’s your **factory**

---

# 🚀 PHASE 6 — Stretch goal (satellite ops idea)

Only AFTER everything works:

You swap:

* construction → satellite ops
* risks → orbital risks
* schedule → mission timeline

Same system.

---

# ⚠️ Hard truths (you need this)

* You’re trying to build **3 startups at once**
* Without constraint → this collapses
* Your advantage = execution discipline, not ideas

---

# 🧠 What makes this powerful

You’re combining:

* AI planning theory ✅
* real-world execution ✅
* audit/compliance thinking ✅

Most people only do one of these.

---

# 🎯 What this becomes (realistically)

If done right:

* internal AI operating system
* construction decision engine
* repeatable agent factory

Not hype — actual leverage.

---

# Your next move

Define **ONE construction use case + 4 agent roles (Aria, Nadia, Jenny, Ops) and write the first “project state model” JSON that your planning loop will operate on.**

Recommendation: **build this in 3 layers, in sequence — (1) your AI team, (2) one working construction loop, (3) replication into PA + trading.**
If you mix these, you won’t hit end-of-year.

I’m going to give you a **brutal, execution-first roadmap** — no fluff, no theory.

---

# 🧠 THE TARGET (by Dec)

You have:

1. ✅ **A.G.E.N.T.S core system (stable)**
2. ✅ **1 construction workflow fully autonomous**
3. ✅ **PA agent actually managing your day**
4. ✅ **Trading assistant (decision support, not auto trading yet)**
5. ✅ **Reusable agent + contract factory**

Not “ideas” — working loops.

---

# ⚙️ PHASE 0 — BUILD YOUR AI TEAM (WEEK 1–2)

### Goal:

Agents that help you build — not just exist

---

## Step 0.1 — Lock your core builder team

Create these agents:

```text
Aria → CEO / decision authority  
Nadia → Planner / system designer  
Jenny → PA / comms / coordination  
Atlas → Engineer (writes code, reviews architecture)  
Sentinel → Auditor (logs, compliance, validation)
```

---

## Step 0.2 — Define their responsibilities (hard boundaries)

* Aria → decides
* Nadia → plans
* Atlas → builds
* Jenny → communicates
* Sentinel → checks

No overlap. No fluff.

---

## Step 0.3 — Give them contracts (critical)

Each must output structured results:

* Nadia → `plan_v1`
* Atlas → `implementation_plan_v1`
* Jenny → `email_draft_v1`
* Sentinel → `audit_log_v1`

---

## Step 0.4 — Force execution behavior

All builder agents:

* run in execution mode when building
* no explanations
* output artifacts only

---

## Milestone ✅

You can say:

> “Build feature X”

And:

* Nadia plans
* Atlas outputs code steps
* Sentinel validates

---

# 🏗️ PHASE 1 — FIRST WORKING SYSTEM (WEEK 3–6)

### Goal:

One **complete construction workflow**

---

## Step 1.1 — Pick the workflow (lock it)

**Variation Approval Process**

Do NOT change this.

---

## Step 1.2 — Define state model

```json
{
  "project_id": "",
  "variation": {
    "cost": 0,
    "impact_days": 0,
    "reason": ""
  },
  "status": "pending",
  "risks": [],
  "history": []
}
```

---

## Step 1.3 — Define outputs

* plan_v1 → how to handle variation
* decision_v1 → approve/reject
* email_draft_v1 → notify stakeholders
* tool_call_v1 → update system

---

## Step 1.4 — Build the loop

```text
Input → Nadia (plan)  
→ Aria (decision)  
→ Jenny (email)  
→ Tool call (update project)  
→ Sentinel (audit log)
```

---

## Step 1.5 — Enforce contracts

Every step:

* must pass validation
* or gets rejected

---

## Milestone ✅

You input:

> “Variation: +$15k, +3 days due to drainage issue”

System outputs:

* plan
* decision
* email
* state update
* audit log

ALL automatically

---

# 🧠 PHASE 2 — PLANNING & REASONING (WEEK 6–10)

### Goal:

Make it **intelligent**, not scripted

---

## Step 2.1 — Add heuristics

```python
if cost > 10000:
    escalate = True
```

---

## Step 2.2 — Add risk scoring

```python
risk_score = cost_weight + delay_weight + complexity_weight
```

---

## Step 2.3 — Multi-agent reasoning

Nadia proposes
Aria evaluates
Sentinel flags risks

---

## Step 2.4 — Memory

Store:

* past variations
* outcomes

Use for future decisions

---

## Milestone ✅

System adapts decisions based on:

* past data
* risk patterns

---

# 🏢 PHASE 3 — REAL-WORLD INTEGRATION (WEEK 10–16)

### Goal:

Make it useful in your actual life

---

## Step 3.1 — Connect tools

* Outlook (emails)
* Calendar
* File storage

---

## Step 3.2 — Jenny becomes real PA

* schedules your day
* drafts emails
* gives morning brief

---

## Step 3.3 — Add input channels

* web UI
* simple form
* voice later (optional)

---

## Milestone ✅

You actually use this daily

---

# 💰 PHASE 4 — TRADING AGENT (WEEK 16–22)

### Goal:

Decision support, not autopilot

---

## Step 4.1 — Define scope

NOT:

* auto trading

YES:

* trade analysis
* risk breakdown
* suggestions

---

## Step 4.2 — Add contracts

* trade_analysis_v1
* risk_report_v1

---

## Step 4.3 — Add data inputs

* market data
* your portfolio

---

## Milestone ✅

You ask:

> “Should I take this trade?”

You get structured, reasoned output

---

# 🏭 PHASE 5 — AGENT FACTORY (WEEK 22–30)

### Goal:

Repeatability

---

## Step 5.1 — Template system

* agent template
* contract template
* tool template

---

## Step 5.2 — Generator

Input:

```json
{
  "role": "scheduler",
  "industry": "construction"
}
```

Output:

* full agent config

---

## Step 5.3 — Deployment pattern

* local (dev)
* cloud (prod)

---

## Milestone ✅

You can spin up new agents in minutes

---

# 🛰️ PHASE 6 — STRETCH (WEEK 30+)

Now:

* replicate system
* change domain

Construction → Satellite ops

Same engine.

---

# ⚠️ NON-NEGOTIABLE RULES

1. **One workflow at a time**
2. **Contracts everywhere**
3. **No explanation outputs in execution**
4. **If it doesn’t update state, it didn’t happen**
5. **If it’s not logged, it doesn’t exist**

---

# 🧠 Brutal truth

* You don’t need better AI
* You need tighter systems
* You already have the hardest parts working

---

# 🎯 What wins this

Consistency over brilliance.

---

# Phase 5 — Self-Correcting Decision Intelligence (CURRENT CEILING)

### Goal:
The system no longer trusts "successful" tool results. It closes the loop between execution drift and future plans, and it does so on a **per-scenario** basis so one bad domain cannot poison another.

---

## Phase 5.0 — Self-Correction v1 (COMPLETED)

### Step 5.0.1 — The Verification Daemon
Implemented `verify_execution.py` to check `api_ack` vs `read_back`.
This is the **Execution Truth Model**.

### Step 5.0.2 — Owen Loop Closure
Owen now ingests verification failures as `owen_negative_patterns`. These patterns are injected into Aria's briefings as **RELIABILITY ALERTS**.

### Step 5.0.3 — Adaptive Confidence Gate
Implemented the **Drift Pressure Index (DPI)** in `decision_finalizer.py`.
- Penalties raise the required confidence threshold.
- System automatically "pulls the plug" (Escalates) when a tool becomes untrustworthy.

**Milestone ✅** — System successfully passed a 5-turn Drift Escalation Simulation. Auto-escalated a valid plan because the Gmail operator's reliability history had degraded.

---

## Phase 5.1 — Context-Scoped Adaptive Distrust (COMPLETED)

### Problem
v1 penalties were **global per action type**. A single failing scenario (e.g. `delay_notice`) would gradually poison every other scenario using the same action (e.g. `variation` emails). Classic over-defensive system failure mode.

### Step 5.1.1 — Pure-Scoped Penalty Keys
`owen_negative_patterns` now keyed on `(action_type, failure_key, scenario_type)`. Idempotent v2-swap migration carries legacy rows forward tagged as `'global'`.

### Step 5.1.2 — Explicit Fallback Contract
`get_patterns_for_action(action, scenario)` returns:
- exact scenario matches if any exist;
- otherwise falls back to `'global'`;
- **never** blends the two when exact matches exist.

This gives isolation when scenarios have history, and graceful coverage when they don't.

### Step 5.1.3 — "Why" One-Liner
Every `FinalizedDecision` carries a `why` field — a single human-readable sentence that names the override, the proximate cause, and the distrust level. Surfaced in `log_issue.py` above the JUSTIFICATION block.

### Step 5.1.4 — Distrust Label
Pure DPI → `LOW | ELEVATED | HIGH | BLOCKED` mapping appended to every WHY line. **Label only, not a control path.**

### Step 5.1.5 — Usage Feedback Capture
After every CLI run: three skippable prompts → `Agent logs/usage_feedback.jsonl`. Foundation for "does this save time?" — the single metric that gates all future feature work.

**Milestone ✅** — `tests/verify_context_scoped_distrust.py` passes: cross-scenario isolation confirmed, global fallback confirmed, exact-match wins confirmed, adaptive distrust at conf=0.85 confirmed.

---

## Phase 5.1.5 — Inference Caching + Cost Control (NEXT)

### Problem
The system is now multi-agent, iterative, and memory-influenced. Repeated similar inputs recompute the same Nadia → Aria loop, paying full token cost each time. Without caching, the moment real daily usage starts, token spend and latency will spike and kill adoption. Caching must ship BEFORE the dashboard.

### Technical architecture (3 tiers, in order of leverage)

**Tier 1 — KV Caching (always-on, provider-side)**
No new code; pure discipline. Every prompt must be structured so the LLM provider's own KV cache can hit on the prefix. This is free performance — but only if we don't waste it with non-deterministic prompt construction.

**Tier 2 — Prefix Caching (highest leverage)**
Reuse KV state across requests. Every prompt is `static_prefix || dynamic_suffix`:
- **Static prefix** (in this order): system instructions → reference documents → few-shot examples → Owen briefing → governance flags.
- **Dynamic suffix**: user/agent message, session id, current date, trace id.
- **Determinism rules**: sorted dict keys, stable JSON indentation, no wall-clock strings inside the prefix, no Python `set` dumps, no order-sensitive loops over dict iteration.

Adopt the discipline across every prompt builder **now**, even before implementing a cache, so Tier 2 drops in later with zero rewrite.

**Tier 3 — Semantic Caching (future)**
Only after Tier 2 is measured and stable. Even then, treat it as experimental.

### Application cache targets (priority order)

**Layer 1 — Decision Cache (SHIPPED)**
Cache `FinalizedDecision` keyed on:
```
hash(scenario_type || normalized_issue || cost_bucket || delay_bucket || governance_flag_set || policy_version)
```
`policy_version` (currently `"v1"`) bumps whenever governance thresholds or scoping logic change; old entries then cease to match new keys and age out. On hit: skip Nadia + Tucker + Sentinel + Aria + finalize_decision, reuse the cached `FinalizedDecision`, still run Jenny (email content depends on exact cost/days within a bucket), still write a new `decisions` row, still go through the gateway. Owen's `extract_lesson_from_decision` is NOT re-run on hits so the same source decision is not re-learned.

*Staleness*: TTL defaults to 48h, overridable via `AGENTS_DECISION_CACHE_TTL` env. Expired rows return `MISS` with `reason="expired"`.

*Snapshot shape*: the full `FinalizedDecision.to_event_payload()` dict is serialized with `sort_keys=True` (deterministic) and reconstituted via `FinalizedDecision.from_payload()`. Jenny's email is NOT cached (regenerated per run with current cost/days).

*Race safety*: `UNIQUE(cache_key)` + `INSERT OR IGNORE`. Concurrent writers collapse to a no-op; first writer's `source_trace_id` is preserved.

**Layer 2 — Planning Cache**
Cache `plan_v1` + risk breakdown + reasoning summary for identical inputs. Keyed on the same tuple as Layer 1 minus `governance_flag_set` (plans are recomputed whenever governance context changes).

**Layer 3 — Prompt Fragment Cache**
Cache Owen briefings, system prompts, and static reasoning blocks. Lowest value; only after Layer 1 and 2.

### Non-negotiable bypass rules

Do NOT cache when ANY of:
- `governance_flags` includes a CRITICAL flag
- `confidence_score < 0.7`
- `distrust_level in {HIGH, BLOCKED}`
- `conflict_detected == True`
- `was_system_forced == True`

DO cache when ALL of:
- decision is APPROVED
- scenario's recent execution history shows VERIFIED_SUCCESS
- drift is low (penalty small, DPI in the LOW or ELEVATED band)
- no active CRITICAL flags for the scenario

### Scope for this phase (SHIPPED)

Layer 1 (Decision Cache) is live:
- Current state update: STRICT+ v2 normalization is active with curated connector stripping (`on/of/the/for/to/at/in`) while identifiers and physical location markers remain preserved.
- `CACHE_MISS reason=no_entry` now includes `miss_classification` for measurement only.
- Structural workflow telemetry now appends to `Agent logs/pattern_registry.log.jsonl` as passive `pattern_observed` records plus downstream `outcome_quality_update` records.
- `agents/logic/decision_cache.py` — centralized `build_cache_context()`, STRICT+ normalization (light canonicalization, no stopword removal, no fuzzy matching), bypass matrix, telemetry.
- `decision_cache` SQLite table in `data/agents_memory.db` — no migration needed, table auto-created on next `_ensure_db()`.
- Orchestrator (`_run_generic_construction_loop`) checks the cache after risk + governance + Owen briefing; on hit, skips Nadia → Aria and reuses the cached `FinalizedDecision`.
- Tiers 2 (prefix caching) and 3 (semantic caching) are explicitly deferred. Prompt-ordering discipline will be adopted when Tier 2 is scheduled.

### Cache telemetry (required)

Companion measurement note:
- `CACHE_MISS reason=no_entry` is additionally classified into `wording_variation`, `same_intent_different_entity`, `insufficient_context`, or `new_intent`.
- Pattern-registry data remains diagnostic only. It is not a second cache and is not used for routing or optimization decisions.

Emit events for every cache interaction:
- `CACHE_HIT` — key, source decision `trace_id`, age, penalty at time of hit
- `CACHE_MISS` — key, reason (no prior entry)
- `CACHE_BYPASS` — key, bypass reason (CRITICAL / low confidence / HIGH distrust / system-forced)

This telemetry becomes the primary input to the Phase 5.2 dashboard.

### Verification (SHIPPED)

**Unit** — `tests/verify_decision_cache.py` asserts:
1. Normalization collides pluralization/tense variants but preserves stopwords and mid-sentence words.
2. Cost / delay buckets align with governance thresholds.
3. Centralized key builder is deterministic; flag-order variations produce identical keys.
4. Cache put/get round-trip reconstitutes the full `FinalizedDecision` snapshot.
5. Write-side bypass matrix rejects every unsafe write reason (7 checks: system_forced, critical_governance, conflict, overridden, non-APPROVE, low_confidence, HIGH distrust).
6. Read-side bypass matrix rejects replays when live context is risky (CRITICAL governance or HIGH/BLOCKED distrust).
7. TTL staleness: rows older than TTL return `MISS reason=expired`.
8. `policy_version` change invalidates existing entries cleanly.
9. `cost_bucket` and `scenario_type` changes flip the key → `MISS`.
10. `UNIQUE(cache_key) + INSERT OR IGNORE` — concurrent writes are safe, first writer remains the source.
11. Every `CACHE_HIT` increments `hit_count` and updates `last_hit_at`.

**Integration** — `tests/verify_cache_integration.py` (live orchestrator loop, mocked LLM turns via `_execute_contract_turn` monkey-patch):
1. **SKIP PROOF**: Run 1 invokes `[nadia, tucker, wall-e, aria, jenny, wall-e]` (6 turns). Run 2 (same input) invokes only `[jenny, wall-e]` (2 turns). **67% LLM-call reduction**. Nadia / Tucker / Sentinel / Aria are not invoked on cache hit.
2. **TELEMETRY**: `CACHE_MISS` on Run 1; `CACHE_HIT` on Run 2 with `source_trace_id` pointing back to Run 1 and current `distrust_level`; `DECISION_FINALIZED_V1` tagged `served_from_cache=true` so the dashboard can distinguish fresh vs cached decisions.
3. **BYPASS FLIPS ON LIVE DRIFT**: after seeding the cache and then injecting `gmail_draft` drift patterns (4 on `subject`, 2 on `body` scoped to the scenario), the same input yields `CACHE_BYPASS reason=distrust_high` and the full Nadia → Aria chain re-runs.
4. **STRICT+ BOUNDARY END-TO-END**: pluralization variants (`Rain delay` ≡ `Rain delays`) collide; stopwords preserved (`Rain delays on slab` distinct from `Rain delays slab` — by design); different topic (`Concrete supply delay`) distinct from rain-delay variants.

**Still manual (intentionally out of automated scope)**: wall-clock latency delta against real LLM (target HIT < 100ms), and real-world hit-rate (Phase 6 daily-use signal).

**Measurement telemetry added**: `DECISION_FINALIZED_V1.metadata.decision_phase_ms` records wall-clock ms across the cache-lookup-to-finalized-decision segment. Combined with `served_from_cache`, a future read-only aggregator can compute `effective_savings_ms = avg(decision_phase_ms | served_from_cache=false) - avg(decision_phase_ms | served_from_cache=true)` without any new instrumentation.

### Expected impact

- 40–70% token reduction on repeat inputs
- Near-instant responses on known-safe patterns
- Cache hit rate becomes a first-class metric on the dashboard

**Milestone ✅** — All 11 decision-cache contract assertions pass in isolated verification. Manual confirmation via `log_issue.py` on identical repeat input pending first real-world run (Phase 6 gate).

---

## Phase 5.2 — Measurement, then (if justified) Operator Dashboard

### Measurement posture first
No new features until 20–50 real-world `log_issue.py` runs have produced telemetry. The dashboard is a read-only aggregator over events that are ALREADY being written; it is not a build blocker — data is. Four questions it must answer once data exists:

1. **Hit rate** — `CACHE_HIT / (HIT + MISS)`. Healthy Layer 1 = 10–30%.
2. **Miss classification distribution** — does reuse mostly fail due to wording variation, different entities, insufficient context, or genuinely new intent?
3. **Pattern divergence** — do repeated structural workflows correlate with repeated value, or only repeated shape?
4. **Bypass distribution** — high `distrust_high` means upstream is unstable; high `low_confidence` means Aria is under-decisive; mostly clean means Layer 2 is a legitimate candidate.

### Goal (the dashboard, when built)
One screen that makes this system usable daily. Read-only aggregation of existing data. No new agents, no new abstractions, no LLM calls.

### Panels (minimum viable)
- Base vs Adjusted Confidence (per recent decision)
- Penalty trajectory (per scenario × action) over time
- Active top failure patterns (scenario-scoped)
- Escalation rate (rolling 7d / 30d)
- Distrust distribution (LOW / ELEVATED / HIGH / BLOCKED)
- Cache hit / miss / bypass rates + token-spend trend (so Phase 5.1.5 is observable)
- `would_use_again` trend from `usage_feedback.jsonl`
- Pattern / outcome divergence from `pattern_registry.log.jsonl`

### Data sources
- `data/agents_memory.db` → `decisions` table + `owen_negative_patterns` table
- `Agent logs/usage_feedback.jsonl`
- `Agent logs/events.log.jsonl` (already indexed for analytics)
- `Agent logs/pattern_registry.log.jsonl`

### Constraint
If the dashboard can't be built from the existing data as-is, that means the schema is incomplete. Fix the schema before adding new writers.

---

## Phase 5.3 — Penalty Decay (AFTER DASHBOARD)
Time-based forgiveness implemented at **read time** on `owen_negative_patterns.last_seen`. Recent failures weigh heavier; stale ones decay. Never mutate historical rows.

## Phase 5.4 — Cross-Action Penalty Sharing (DEFERRED)
Opt-in per action-family only. Never automatic. Only considered after dashboard + decay have proven stable in real use.

---

## Validation gate for moving past Phase 5.2
Five real site issues processed via `log_issue.py`. `would_use_again` trend positive. Cache hit rate > 0 on at least one repeat. If the dashboard isn't helping, fix the dashboard — don't build Phase 5.3.

## Discipline reminder
Finish the construction loop and make it daily BEFORE replicating into PA / trading. Three half-working systems > one weapon is a trap.

---

