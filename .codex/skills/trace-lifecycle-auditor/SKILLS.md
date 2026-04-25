---
name: trace-lifecycle-auditor
description: Identifies decision traces that failed to complete their lifecycle chain from decision creation through outcome finalization.
---

# Trace Lifecycle Auditor

## Purpose
For each run, answer only this question:

> Which decision traces failed to complete their full lifecycle chain?

## Scope (STRICT READ-ONLY)
Do NOT modify code, logs, or system state.

Only analyze existing telemetry from:
- Agent logs/events.log.jsonl
- pattern_registry.log.jsonl
- usage_feedback.jsonl
- decision_cache telemetry

## Lifecycle definition

A complete trace MUST include:

1. DECISION_CREATED
2. APPROVAL_DECIDED
3. EXECUTION_ATTEMPTED (if approved)
4. OUTCOME_FINALIZED (if execution attempted)
5. PATTERN_LOGGED

## Output rules (VERY IMPORTANT)

Return ONLY:

### 1. Incomplete Traces
List trace IDs missing steps in lifecycle order.

Format:
- TRACE_ID → missing: [STEP_1, STEP_2, ...]

### 2. Failure Categories
Group missing traces into:

- approval_missing
- execution_missing
- outcome_missing
- partial_execution_chain
- orphan_pattern_logged

### 3. Summary (single block only)
- total traces analysed
- total incomplete traces
- dominant failure stage

## Hard constraints

- Do NOT suggest fixes
- Do NOT propose architecture changes
- Do NOT infer missing data
- Do NOT score or rank traces
- Do NOT create new metrics

## Behavioural rule

If data is incomplete, explicitly state:
> "INSUFFICIENT LIFECYCLE DATA — DO NOT DRAW SYSTEM CONCLUSIONS"

## Goal

Maintain strict separation between:
- observation
- interpretation
- optimisation

This skill is observation only.