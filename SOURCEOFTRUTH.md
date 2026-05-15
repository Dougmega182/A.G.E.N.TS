# SOURCEOFTRUTH.md

## A.G.E.N.T.S. Canonical Project Source of Truth

This document consolidates and supersedes the following project documents for progress tracking and project insight:

- SHADOW_AUDIT_PROTOCOL.md
- README.md
- PLANNINGPROGRESS.md
- PLANNING.md
- DOCUMENT_INDEX.md
- ADAPTIVE_INTELLIGENCE.md
- 24H_AUDIT_TEMPLATE.md

## 1) Project Definition

**Name:** A.G.E.N.T.S. (Autonomous Governance & Execution Networked Task System)

**Purpose:** Multi-agent, governance-first orchestration system for construction operations with deterministic safety gates, traceability, adaptive distrust, and execution feedback loops.

**Current focus:** Construction workflow reliability and measurable daily utility before expanding to other domains.

## 2) Runtime Status

- **Current phase:** Phase 5.2.1 — Checkpoint Gamma (in progress)
- **Current priority:** Discipline hardening KPI verification and real-world telemetry collection
- **Primary gate:** Collect **20–50 real runs** via `log_issue.py` before new feature expansion
- **Build baseline context:** Phase 5 self-correcting intelligence stack active

## 3) Non-Negotiable Operating Rules

1. **Gatekeeper supremacy:** no execution without human approval.
2. **No layer skipping:** decisions pass through the defined chain.
3. **Audit first:** audit events precede state mutation.
4. **Full traceability:** unique trace lineage on all actions.
5. **Zero hallucination:** no fabricated dates, costs, or execution facts.
6. **Momentum protection:** decisions account for project velocity/drag.
7. **Execution truth:** API ack is insufficient; reality verification is mandatory.
8. **If not in state/logs, it did not happen.**

## 4) Agent Chain and Responsibilities

- **Aria (CEO):** decision authority under governance constraints.
- **Nadia (Planner):** structured plan generation (`plan_v1`).
- **Tucker (Engineer):** technical feasibility and architecture review.
- **Jenny (PA):** comms artifacts (`email_draft_v1`), always human-gated.
- **WALL-E (Auditor):** schema/constitution compliance and forensic logging.
- **Eli (Momentum):** logistics strategy from momentum signals.
- **Owen (Intelligence):** reliability synthesis, pattern ingestion, DPI influence.

## 5) System Architecture (Operational)

Core loop:

`STRATEGY -> PLANNING -> EXECUTION -> MONITORING -> AUDIT -> IMPROVEMENT`

Execution shape:

- Input scenario (`Variation:`, `RFI:`, `Delay:`)
- Plan generation
- Decision finalization with governance + distrust logic
- Human approval gate
- Tool execution
- Truth verification
- Failure/pattern ingestion
- Next-turn reliability-adjusted briefing

## 6) Adaptive Decision Intelligence (Phase 5 Core)

### 6.1 Drift Pressure Index (DPI)

DPI is the skepticism control unit. It raises effective confidence requirements as reliability degrades.

Formula basis:

`DPI = sum(component_penalties) / confidence_threshold`

Impact:

- Low drift: normal autonomy path.
- Rising drift: stricter approve/execute conversion.
- High drift: forced escalation despite nominal confidence.

### 6.2 Truth Model (3-Phase Validation)

Every execution is verified across:

1. `api_ack` (service accepted request)
2. `read_back` (artifact retrieved)
3. `semantic_match` (artifact content matches intent)

Execution drift = mismatch between acceptance and semantic reality.

### 6.3 Failure Taxonomy

- `TRANSIENT`
- `DEGRADED_SUCCESS`
- `DRIFT_CONFIRMED`
- `TRUE_FAILURE`

These feed Owen’s reliability memory and influence future gating.

## 7) Inference Caching (Deterministic, Safety-Gated)

### 7.1 Layer 1 Decision Cache (shipped)

Key basis:

`SHA256(scenario_type || normalized_issue || cost_bucket || delay_bucket || governance_flags || policy_version)`

Properties:

- deterministic key builder
- TTL-based staleness
- race-safe write (`UNIQUE` + insert-ignore semantics)
- hit telemetry and bypass telemetry

Bypass is enforced for unsafe contexts (critical governance, high distrust, low confidence, forced/system-override contexts).

### 7.2 Measurement Expectations

- healthy Layer-1 hit band: ~10–30% in real usage
- explicit miss classification required
- bypass reason distribution required
- pattern-vs-outcome divergence required

## 8) Progress Snapshot by Phase

### Completed foundations

- Phase 0: core team activation
- Phase 1: first complete construction workflow (proposal -> approval -> execute -> mutate)
- Phase 2: planning/reasoning + governance hardening
- Phase 2.5: memory boundary and Owen intelligence infrastructure
- Phase 5.0: self-correcting intelligence v1 (truth loop + DPI)
- Phase 5.1: context-scoped adaptive distrust
- Phase 5.1.5: Layer-1 decision cache + telemetry

### In progress

- Phase 5.2.1 Gamma checkpoint discipline hardening
- KPI verification for sanitizer/block/cache behavior
- real-run evidence collection and dashboard-readiness validation

### Deferred by policy

- penalty decay (Phase 5.3) after measurement confidence
- cross-action sharing (Phase 5.4) only if stability is proven

## 9) Audit Protocol (Shadow Mode)

## 9.1 Hard-stop triggers (immediate pause)

Pause system immediately if any occur:

- any CRITICAL auto-act bypasses human approval
- critical error rate > 5%
- controlled-tier auto-act exceeds 35% in first 24h

## 9.2 Checkpoint Alpha (T+24h)

Healthy pattern:

- SAFE mostly auto-act
- CONTROLLED mostly require approval
- CRITICAL always require approval
- overrides mostly cosmetic, minimal context miss

Decision:

- continue / tighten / pause

## 9.3 Checkpoint Beta (T+48h)

- **Expand autonomy** if critical_error <= 2%, controlled auto-act <= 25%, and shadow accuracy stable.
- **Hold** if stable but sample weak.
- **Tighten** if context miss high, controlled auto-act > 30%, or logic gaps persist.

## 9.4 24h Audit Snapshot Template

Use this exact structure:

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
- STABLE / OVERCONFIDENT / TOO TIMID / UNSTABLE

ACTION:
- CONTINUE / TIGHTEN / PAUSE
```

## 10) Execution and Monitoring Surfaces

### CLI

`python cli/gatekeeper.py`

### Web monitoring

`powershell -NoProfile -ExecutionPolicy Bypass -File .\launch.ps1`

Endpoints:

- `http://localhost:8000/static/index.html`
- `http://localhost:8000/status`
- `http://localhost:8000/telemetry`

## 11) Data and Telemetry Sources

Primary sources for project truth and analytics:

- `Agent logs/events.log.jsonl`
- `Agent logs/usage_feedback.jsonl`
- `Agent logs/pattern_registry.log.jsonl`
- `data/agents_memory.db` (`decisions`, `owen_negative_patterns`, `decision_cache`)

## 12) KPI and Gate Criteria (Current)

- sanitizer repair rate target: low single digits on clean traffic
- block rate target: very low (<1% class)
- cache hit rate: improve with real corpus; no synthetic inflation
- escalation latency: monitor p50/p95 for operator load
- usability trend: `would_use_again` must stay positive

## 13) Roadmap Discipline Rules

1. One workflow at a time.
2. No feature expansion before data gates are passed.
3. Prefer deterministic controls over prompt-only behavior.
4. Read-only aggregation before introducing new writers.
5. Construction loop daily reliability is mandatory before PA/trading replication.

## 14) Document Authority and Change Control

This file is now the canonical project reference for:

- progress updates
- architecture status
- audit protocol
- current priorities
- operational decisions requiring project-wide context

Update this file whenever phase status, gating policy, or operational baselines change.
