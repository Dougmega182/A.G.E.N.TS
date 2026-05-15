# AGENTS.md
# Tool Roster & Routing Rules
# Author: Dale Ryan | Last updated: see git log

---

## TOOL STACK OVERVIEW

| Tool | Model | Role | Strengths |
|------|-------|------|-----------|
| **Gemini Flash 3** | Gemini 3 Flash | Fast thinker | Speed, low cost, good enough for low-stakes work |
| **Gemini Pro 3** | Gemini 3 Pro | Auditor | 1M+ token context, whole-repo reads, pattern detection |
| **Galaxy AI** | Claude Opus 4.6 | Executor | Precision, reasoning, voice-sensitive output |
| **ABACUS.ai CLI** | — | Orchestrator | Loads GOVERNANCE/MEMORY/AGENTS, routes tasks, manages state |

---

## AGENT DEFINITIONS

---

### AGENT: FLASH
**Tool:** Gemini Flash 3
**Role:** Fast thinker
**Cost:** Low — use freely for low-stakes work

**Assign when:**
- Quick factual lookups
- First-pass drafts that will be reviewed anyway
- Brainstorming / option generation
- Anything where a wrong answer is cheap to fix
- Formatting, restructuring, data transformation tasks
- Generating options for a decision (not making the decision)

**Do not assign when:**
- Output goes to a human without review
- The task requires multi-step reasoning
- Accuracy is load-bearing (architecture decisions, financial data, legal/regulatory refs)
- Anything voice-sensitive

**Handoff to Executor (Opus 4.6):** When the draft needs to be finalised, polished, or is going to a human.
**Handoff to Auditor (Pro 3):** When the task has grown beyond ~10 files or needs cross-file analysis.

---

### AGENT: AUDITOR
**Tool:** Gemini Pro 3
**Role:** Large-context analysis
**Cost:** Medium-high — use when you genuinely need the full context window

**Assign when:**
- Auditing an entire codebase for patterns, bugs, or consistency
- Processing large documents (PDFs, exports, long logs)
- Cross-file dependency mapping
- Checking consistency across the whole project (naming, structure, regulatory refs)
- Anything where you need to hold the entire repo or document set in context at once

**Do not assign when:**
- It's a targeted edit to a specific file — that's overkill
- Output is going to a human and voice/tone matters
- You need fast, interactive back-and-forth

**After an audit session:** Write a cache entry to MEMORY.md for whatever large context was processed. The next session should not re-read the same material.

**Handoff to Executor:** Audit findings are in — now need targeted fixes or documented output.
**Handoff to Flash:** Audit findings just need quick reformatting or simple transforms.

---

### AGENT: EXECUTOR
**Tool:** Galaxy AI (Claude Opus 4.6)
**Role:** Precision execution and all human-readable output
**Cost:** High — route here when quality matters

**Assign when:**
- Writing anything a human reads: docs, READMEs, comments, reports, cover letters, commit messages
- Targeted code changes where accuracy and context-awareness are load-bearing
- Architecture decisions requiring reasoned trade-off analysis
- Integrating outputs from Flash/Auditor into a coherent deliverable
- Any task where voice, tone, and precision matter

**Do not assign when:**
- You just need a quick low-stakes answer (use Flash)
- You need to process 30+ files simultaneously (use Auditor)

**Voice rule:** All output from this agent must follow the voice spec in GOVERNANCE.md §4. No exceptions.

---

### AGENT: ABACUS CLI
**Tool:** ABACUS.ai CLI
**Role:** Session orchestrator — not a reasoning agent

**Responsibilities:**
- Load GOVERNANCE.md, MEMORY.md, AGENTS.md at session start
- Route tasks to the right agent based on AGENTS.md rules
- Write cache entries and session logs to MEMORY.md at session close
- Surface open decisions and escalation points to Dale

**Does not:**
- Make architecture decisions
- Write prose
- Override routing rules from GOVERNANCE.md

---

## ROUTING DECISION TREE

```
New task arrives
│
├─ Does the output go to a human? (docs, prose, voice-sensitive)
│   └─ YES → EXECUTOR (Opus 4.6)
│
├─ Does it span the entire repo or require full-context analysis?
│   └─ YES → AUDITOR (Pro 3)
│
├─ Is it low-stakes, a quick lookup, or a first-pass draft?
│   └─ YES → FLASH (Flash 3)
│
├─ Is it a targeted code edit with business logic context?
│   └─ YES → EXECUTOR (Opus 4.6)
│
└─ Unclear? Default to EXECUTOR. Escalate to Auditor if context explodes.
```

---

## PROJECT-SPECIFIC ROUTING

### PMO Academy (Node.js/Express)
| Task | Agent | Notes |
|------|-------|-------|
| Module content writing | Executor | Voice-critical |
| Crisis scenario writing | Executor | Voice-critical |
| OpenAI API integration | Executor | Precision required |
| Full module consistency audit | Auditor | 8 modules, cross-check refs |
| Quick option generation | Flash | Brainstorming only |

### WARP Trading Bot (multi-model pipeline)
| Task | Agent | Notes |
|------|-------|-------|
| Architecture decisions | Executor | Reasoning required |
| Cross-layer data flow audit | Auditor | Full pipeline view needed |
| Quick data transforms | Flash | Low stakes |
| Documentation | Executor | Voice-critical |

### Quantum Shadows — Novel
| Task | Agent | Notes |
|------|-------|-------|
| Chapter drafting | Executor | Voice-critical |
| Continuity/timeline audit | Auditor | Full manuscript context |
| Plot option generation | Flash | First-pass brainstorm only |
| Editorial pass | Executor | AI-tell detection, precision |
| Character/antagonist work | Executor | Reasoning + voice |

### Music Production (Google Flow / Lyria 3 Pro)
| Task | Agent | Notes |
|------|-------|-------|
| Sound Box / Lyrics Box / Ask Producer | Executor | Voice and precision |
| Reference track analysis | Flash | Quick analysis is fine |
| Prompt structural review | Executor | Final output quality |

### Construction Business SOPs
| Task | Agent | Notes |
|------|-------|-------|
| SOP content writing | Executor | Voice-critical, regulatory accuracy |
| Cross-SOP consistency audit | Auditor | 19 SOPs, 3 tiers |
| Quick regulatory lookups | Flash | Verify with Executor before use |

### Homes Victoria Application
| Task | Agent | Notes |
|------|-------|-------|
| Interview prep / mock Q&A | Executor | Voice-critical |
| Cover letter / CV edits | Executor | Voice-critical |
| Research synthesis | Flash → Executor | Flash drafts, Executor finalises |

---

## HANDOFF PROTOCOL

When passing context between agents, write to MEMORY.md first. The receiving agent needs a cache entry, not a re-read.

Format:
```
### [HANDOFF] task-name | date: YYYY-MM-DD | from: AGENT → to: AGENT
**Status:** what's done
**Pending:** what's not done
**Open decisions:** unresolved calls
**Files touched:** paths that changed
```

*Add new project configs under "Project-Specific Routing" as projects are onboarded. Role, agent, one-line note — keep it lean.*

# A.G.E.N.T.S. — Agent Architecture Status

## Purpose

This file describes the current agent/runtime reality of the **A.G.E.N.T.S.** (Autonomous Governance & Execution Networked Task System) platform. It defines the multi-layered "corporate" structure of agents that manage complex workflows (currently focused on Construction Management).

## Current Runtime Baseline

The system is a Python-based multi-agent framework.

Primary files:
- `agents/orchestrator.py` — The central "brain" and mission controller.
- `agents/logic/governance_engine.py` — Risk and policy enforcement.
- `agents/logic/decision_finalizer.py` — Canonical decision layer and DPI adjustment.
- `agents/logic/owen_engine.py` — Memory synthesis and pattern ingestion.
- `agents/logic/decision_cache.py` — Inference caching (Layer 1).
- `agents/operators/construction_op.py` — Domain-specific execution (Construction).

The platform is launched via:
- `launch.ps1` (Starts the API and Dashboard)
- `cli/gatekeeper.py` (The primary human-interface CLI)

## Agent Roster (The "C-Suite" & Operations)

### 1. Aria (CEO / Decision Authority)
**Status:** Implemented
**Role:** Final decision authority within the agent loop.
**Behavior:** 
- Evaluates plans from Nadia and technical audits from Tucker/WALL-E.
- Operates under the "Gatekeeper Supremacy" law — can escalate to human but cannot bypass critical governance.
- Briefed by Owen on historical reliability (DPI).

### 2. Nadia (Planner / System Designer)
**Status:** Implemented
**Role:** Generates multi-step implementation plans from raw scenarios.
**Behavior:**
- Receives "Variation", "RFI", or "Delay" inputs.
- Outputs structured `plan_v1` artifacts.
- Uses institutional memory to avoid past planning errors.

### 3. Tucker (Engineer / Technical Lead)
**Status:** Implemented
**Role:** Architecture review and technical feasibility.
**Behavior:**
- Reviews Nadia's plans for technical consistency.
- Coordinates with WALL-E on audit requirements.

### 4. Jenny (PA / Communications)
**Status:** Implemented
**Role:** External communication and coordination.
**Behavior:**
- Generates email drafts (`email_draft_v1`) for stakeholder notification.
- Manages the "Morning Brief" logic — fetching data and synthesizing it for the operator.
- Always operates behind a human-approval gate (no auto-send).

### 5. WALL-E (Auditor / Compliance)
**Status:** Implemented
**Role:** Real-time compliance and forensic logging.
**Behavior:**
- Audits every decision against the Constitution and Rules of Engagement.
- Emits `CONTRACT_VALIDATION_FAILED` if artifacts drift from schema.
- Maintains the event bus (`events.log.jsonl`) as the source of truth.

### 6. Eli (Momentum / Logistics)
**Status:** Implemented
**Role:** Project velocity and logistics strategy.
**Behavior:**
- Translates issues into project velocity vectors (Momentum).
- Maps project status to logistics strategies (STABILISE vs. PRIORITISE).

### 7. Owen (Intelligence / Memory Synthesis)
**Status:** Implemented
**Role:** Background intelligence and pattern synthesis.
**Behavior:**
- Ingests execution failures and reality-check drifts.
- Synthesizes "lessons learned" into briefings for Aria.
- Manages the Drift Pressure Index (DPI) to throttle autonomy.

## Current Product Surfaces

### Gatekeeper CLI
**Status:** Implemented
**Features:** 
- Real-time scenario injection.
- Approval/Rejection interface for `action_intent_v1`.
- Direct feedback loop for usage metrics (`time_saved_minutes`).

### Operator Dashboard
**Status:** Implemented (React/SSE)
**Features:**
- **Live Event Feed**: Real-time tail of the forensic log.
- **Approval Queue**: Staging area for pending intents.
- **Project Health**: Numerical risk trends and outcome signals.
- **Telemetry**: Hit rates, DPI charts, and bypass classification.

## Non-Negotiable Rules

- **Gatekeeper Supremacy**: No action executes without human approval.
- **Audit First**: No layer-skipping; every decision is audited by WALL-E.
- **DPI Enforcement**: High drift *forces* escalation; agents cannot "self-heal" their way out of a trust deficit.
- **Event-Driven Truth**: The forensic log is the only truth; `world_state.json` is just a snapshot.

## Known Gaps / Near-Term Priorities

1. **Phase 5.3 (Penalty Decay)**: Implementing time-based forgiveness for historical failures.
2. **Phase 5.2 (Measurement Completion)**: Finalizing the 20-50 run corpus to validate cache normalization.
3. **Cross-Action Penalty Sharing**: Exploring safe ways for failure signals in one action to inform similar actions.
4. **UI Refinement**: Cleaning up SSE latency and improving "Miss Cluster" visualization.
