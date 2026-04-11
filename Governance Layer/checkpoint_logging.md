# Checkpoint Logging Standard

Status: Draft
Owner: Governance Layer (Audit and Compliance)
Approval: Audit Agent + Gatekeeper
Review Cycle: Monthly

Purpose
Ensure every material action taken in the repository is logged at checkpoints for traceability and auditability.

When to Log
- Start of a work session
- After any set of file changes
- Before and after commits
- End of session

Checkpoint Log Format (JSONL)
Each line is a JSON object with the following fields:
- timestamp_utc
- author
- action
- summary
- files_changed
- decisions
- risks
- next_action

Log File Location
Governance Layer/memory/checkpoints.jsonl

Minimum Compliance
No changes are considered complete until the checkpoint log is updated.

Non-Recursive Rule
Checkpoint log updates do not require additional checkpoint entries to avoid infinite recursion.

