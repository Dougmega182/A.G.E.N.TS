---
name: trace-lifecycle-auditor
description: Identifies decision traces that fail lifecycle completion across decision, approval, execution, outcome, and pattern stages.
metadata:
  short-description: Audit decision trace lifecycle completeness
---

# Trace Lifecycle Auditor

## Purpose
Identify which decision traces fail to complete their full lifecycle chain.

## Lifecycle Definition
A complete trace MUST include:
- DECISION_CREATED
- APPROVAL_DECIDED
- EXECUTION_ATTEMPTED
- OUTCOME_FINALIZED
- PATTERN_LOGGED

## Data Sources
- Agent logs/events.log.jsonl
- Agent logs/pattern_registry.log.jsonl
- Agent logs/usage_feedback.jsonl
- decision_cache telemetry

## Rules (STRICT)
- Read-only analysis only
- No execution or mutation
- No system changes
- No inference beyond observed logs

## Output Format

1. Incomplete Traces:
- TRACE_ID → missing: [STAGE_1, STAGE_2]

2. Failure Categories:
- approval_missing
- execution_missing
- outcome_missing
- partial_execution_chain
- orphan_pattern_logged

3. Summary:
- total traces analysed
- total incomplete traces
- dominant failure stage

## Hard Constraint
If lifecycle data is incomplete:
> INSUFFICIENT LIFECYCLE DATA — DO NOT DRAW SYSTEM CONCLUSIONS