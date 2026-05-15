# MEMORY.md
# Claude Code — Persistent State, Cache & Decisions
# Author: Dale | Last updated: 2026-05-15

---

## HOW TO USE THIS FILE

- **Read:** Every session starts here. Full read, no skipping.
- **Write:** After any session that produced significant new context, add cache entries before closing.
- **Purge:** Mark stale entries `[STALE]` — don't delete, they're useful history. Explicit `[PURGE]` to actually remove.
- **Format:** Follow the templates exactly. This file is machine-read as well as human-read.

Cache entries go in `§ INFERENCE CACHE`. Decisions go in `§ DECISIONS LOG`. Project state goes in `§ ACTIVE PROJECTS`.

---

## § PROFILE

**Name:** Dale 
**Location:** Eltham North, Victoria, Australia
**Background:** Victorian Registered Builder, 20 years experience. Founded and ran Ryandale Building Group ~15 years. Currently Project Coordinator (portfolio management) + runs 11-person residential construction company.

**Career target:** Transition from construction business ownership into client-side project management / PMO consulting. Targeting healthcare and government infrastructure in Melbourne. Current live application: Director, Portfolio Management Office — Homes Victoria (DFFH).

**Credentials:** Advanced Diploma Construction + Advanced Diploma IT, RMIT.

**AI tool stack:**
- ABACUS.ai → scaffolding, shell ops
- Gemini Flash 3 → fast/low-stakes thinking
- Gemini Pro 3 → large-context audits
- Galaxy AI (Opus 4.6) → execution, precision, all prose output
- ABACUS.ai CLI → session orchestrator, loads context files
- GPT (various) → WARP trading bot stack, creative tasks

**Writing voice (mandatory for all prose output):**
- Direct, terse, no corporate language
- Short sentences, active voice
- No hedging, no flattery, no padding
- Dry humour acceptable, forced positivity not
- Technical precision over accessibility — he'll ask if simpler is needed
- See GOVERNANCE.md §3 for full spec

---

## § ACTIVE PROJECTS

*Update status, current task, and next action every session. One entry per project.*

---

### PROJECT: PMO Academy
**Status:** Active
**Stack:** Node.js / Express / localhost / OpenAI API
**Location:** [add local path]
**Description:** Localhost learning platform with 8 modules for PMO knowledge and live crisis scenarios. Built specifically to support Homes Victoria application prep.
**Current task:** [update each session]
**Next action:** [update each session]
**Last touched:** [date]
**Cache entries:** [list any cache block IDs for this project]

---

### PROJECT: WARP Trading Bot
**Status:** Active
**Stack:** Python, GPT-4.5 Mini/Pro, Gemini 2.5 Flash/Pro (no Anthropic models)
**Architecture:** 5-layer pipeline
**Location:** [add local path]
**Description:** Multi-model AI trading research bot. WARP multi-agent system.
**Current task:** [update each session]
**Next action:** [update each session]
**Last touched:** [date]
**Cache entries:** [list any cache block IDs for this project]

---

### PROJECT: Quantum Shadows — Book 1: Entangled
**Status:** Active
**Stack:** 4-agent AI writing system (Architect, Analyst, Writer, Editor)
**Genre:** Sci-fi
**Setting:** 2618 CE Melbourne. Protagonist: Detective Nolan Kain, Quantum Security Agency (QSA).
**Known issues (from last editorial pass):**
- Name/year contradictions
- Chapter 6 voice drop
- Character Bell underdeveloped
- Antagonist motivation shallow
**Current task:** Stabilize ProseLab rewrite behavior so full editorial rewrite returns rewritten scene prose only.
**Next action:** Run another end-to-end rewrite pass in UI and verify no prompt/feedback leakage in output.
**Last touched:** 2026-05-15
**Cache entries:** proselab-rewrite-flow-apply-full-editorial, governance-memory-agents-baseline

---

### PROJECT: Music Production — Google Flow / Lyria 3 Pro
**Status:** Active
**Engine:** Lyria 3 Pro
**Deliverable format:** Sound Box + Lyrics Box + Ask Producer per track
**Active tracks:**
1. Complacency/self-improvement — anthemic pop-punk architecture
2. Absurdist mundane — emotional emptiness, mundane specificity
**Reference:** Blink-182 *Neighbourhoods* — BPM ranges, guitar delay motifs, polyrhythmic drums, DeLonge vs Hoppus vocal registers
**Current task:** [update each session]
**Next action:** [update each session]
**Last touched:** [date]

---

### PROJECT: Construction Business SOPs
**Status:** Complete (19 SOPs across 3 tiers)
**Stack:** Victorian regulatory refs, Buildertrend/BuildPass integration
**Location:** [add local path]
**Notes:** Complete unless regulatory changes require updates.
**Last touched:** [date]

---

### PROJECT: A.G.E.N.T.S.
**Status:** Active (Phase 5.2.1 Checkpoint Gamma)
**Stack:** Python (Orchestrator), React (Dashboard), SQLite/Redis/JSONL (Memory), Gemini 3 Flash / OpenAI
**Location:** e:\Ai\WORK-IN-PROGRESS\A.G.E.N.T.S
**Description:** Autonomous Governance & Execution Networked Task System. A multi-agent framework for construction management with self-correcting intelligence and strict governance.
**Current task:** Discipline hardening and KPI verification (Sanitizer repair rate, Cache hit rate).
**Next action:** Collect 20-50 real runs via `log_issue.py` to validate cache normalization.
**Last touched:** 2026-05-15
**Cache entries:** agents-project-baseline, governance-memory-agents-baseline

---

### PROJECT: Homes Victoria Application — Director PMO
**Status:** Submitted / In progress
**Target role:** Director, Portfolio Management Office — Homes Victoria (DFFH)
**Capital portfolio context:** Big Housing Build, Ground Lease Model, High-rise Redevelopment
**Materials produced:** CV (modernised, PMO/govt targeting), cover letter (includes HIA/ABS research — 98.6% of Victorian construction businesses are small), mock interview prep
**Current task:** [update each session — interview prep, follow-up, etc.]
**Last touched:** [date]

---

## § INFERENCE CACHE

*Entries added here when large context has been processed. Use these instead of re-reading source material.*
*Format: [CACHE] id | cached: date | status: FRESH|STALE*

---

<!-- CACHE ENTRIES GO HERE -->
<!-- Copy this template when adding a new entry:

### [CACHE] descriptive-id | cached: YYYY-MM-DD | status: FRESH
**Source:** path/to/file or URL
**Summary:**
- fact 1
- fact 2
- fact 3
**Key identifiers:** function names, class names, schema fields, config keys
**Used in:** project name(s)
**Stale if:** what change would invalidate this
**Handed off from:** agent (if applicable)

-->

### [CACHE] proselab-rewrite-flow-apply-full-editorial | cached: 2026-05-15 | status: FRESH
**Source:** proselab/src/App.jsx, proselab/src/engine/rewrite.js, proselab/src/engine/guards.js, output.md
**Summary:**
- "Apply Full Editorial Rewrite" routes through runTargetedRewrite and generateRewrite with mode="intent-repair".
- Root cause of leakage: intent-repair prompt lacked strict "output only rewritten scene text" contract; model could echo original scene and feedback/instructions.
- Fix applied: tightened intent-repair prompt output rules and added prompt-leakage detection in validateOutputContract.
**Key identifiers:** runTargetedRewrite, buildRewritePrompt, generateRewrite, validateOutputContract, mode: "intent-repair"
**Used in:** Quantum Shadows — Book 1: Entangled
**Stale if:** rewrite pipeline files change (App.jsx rewrite action, rewrite.js prompt construction, guards.js contract checks).
**Handed off from:** ABACUS.ai CLI Executor

### [CACHE] governance-memory-agents-baseline | cached: 2026-05-15 | status: FRESH
**Source:** GOVERNANCE.md, MEMORY.md, AGENTS.md
**Summary:**
- Session load order is fixed: GOVERNANCE → MEMORY → AGENTS, with cache-first behavior mandatory.
- Token policy requires reuse of cache entries, batching related work, and mandatory cache writes after significant context processing.
- Routing policy: low-stakes quick work to Flash behavior, full-context audits to Pro behavior, precision edits and human-facing output to Opus executor behavior.
**Key identifiers:** cache-first, TOKEN BUDGET RULES, INFERENCE CACHE POLICY, ROUTING DECISION TREE, HANDOFF PROTOCOL
**Used in:** all active projects
**Stale if:** governance/routing/cache policies are revised in source files.
**Handed off from:** ABACUS.ai CLI Orchestrator

---

### [CACHE] agents-project-baseline | cached: 2026-05-15 | status: FRESH
**Source:** AGENTS.md, PLANNINGPROGRESS.md, ROADMAP.md
**Summary:**
- A.G.E.N.T.S. is in Phase 5.2.1 (Checkpoint Gamma).
- Core agents: Aria (CEO), Nadia (Planner), Tucker (Engineer), Jenny (PA), WALL-E (Auditor), Eli (Momentum), Owen (Intelligence).
- Key systems: Decision Cache (Layer 1), Drift Pressure Index (DPI), Context-Scoped Adaptive Distrust.
- Current focus: Discipline hardening and data-driven measurement (20-50 runs).
**Key identifiers:** Aria, Nadia, Tucker, Jenny, WALL-E, Eli, Owen, DPI, Decision Cache, Checkpoint Gamma
**Used in:** A.G.E.N.T.S.
**Stale if:** Major architectural shift or phase graduation.
**Handed off from:** ABACUS.ai CLI Orchestrator

---

## § DECISIONS LOG

*Architectural, technical, or strategic decisions made during sessions. Never delete — stale decisions are useful context for why things are the way they are.*

---

<!-- DECISION ENTRIES GO HERE -->
<!-- Copy this template:

### [DECISION] decision-id | date: YYYY-MM-DD | project: project-name
**Decision:** What was decided
**Options considered:** What else was on the table (brief)
**Rationale:** Why this option won
**Trade-offs accepted:** What we're living with
**Revisit if:** What circumstances would make us reconsider

-->

### [DECISION] proselab-rewrite-output-contract-hardening | date: 2026-05-15 | project: Quantum Shadows — Book 1: Entangled
**Decision:** Enforce strict output-only prose contract for intent-repair rewrites and reject prompt/instruction leakage.
**Options considered:** (1) Prompt-only fix, (2) parser/extractor post-processing, (3) prompt + validator hardening.
**Rationale:** Prompt-only is fragile under model drift. Prompt + validator gives defense-in-depth while staying minimal and local to rewrite path.
**Trade-offs accepted:** Slightly stricter validation may trigger retry more often on borderline outputs.
**Revisit if:** leakage still appears in production outputs; then add deterministic extraction fallback.


---

## § HANDOFF LOG

*Records of context handoffs between agents. Populated automatically during inter-agent handoffs per AGENTS.md protocol.*

---

<!-- HANDOFF ENTRIES GO HERE -->
<!-- Copy this template:

### [HANDOFF] task-name | date: YYYY-MM-DD | from: AGENT → to: AGENT
**Status:** what's complete
**Pending:** what's not done
**Open decisions:** unresolved calls
**Files touched:** paths

-->

*No handoffs logged yet.*

---

## § SESSION LOG

*One-line entry per session. What was done, what changed, what was cached.*

---

| Date | Project | Work done | Cache entries added | Decisions made |
|------|---------|-----------|--------------------:|----------------|
| 2026-05-15 | A.G.E.N.T.S. | Refreshed project status; aligned AGENTS.md, MEMORY.md, and GOVERNANCE.md with current A.G.E.N.T.S. architecture | agents-project-baseline | |
| 2026-05-15 | Quantum Shadows — Book 1: Entangled | Diagnosed and fixed Apply Full Editorial Rewrite prompt leakage; aligned runtime context from governance docs | proselab-rewrite-flow-apply-full-editorial, governance-memory-agents-baseline | proselab-rewrite-output-contract-hardening |

---

## § VOICE REFERENCE — QUICK CARD

*Paste this into any session prompt when generating human-readable output.*

```
VOICE RULES — Dale
- Short sentences. Active voice. No passive unless it's genuinely clearer.
- No: leverage, utilise, synergy, ensure alignment, robust, seamless, cutting-edge
- No hedging: not "may potentially", not "it could be worth considering"
- No flattery openers. Just answer.
- State opinions as opinions. Defend them if challenged.
- Technical accuracy > accessible simplification
- Cut 30% of words from every sentence before outputting
- Dry humour is fine. Forced positivity is not.
- Write like someone who's been building things for 20 years and has no time for waffle.
```

---

*This file is the source of truth for session state. If something isn't here, it didn't happen.*
*Every session that changes something should update this file before closing.*