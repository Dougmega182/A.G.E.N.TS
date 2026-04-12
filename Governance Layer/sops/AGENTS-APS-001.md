# AGENT PROFILE STANDARD

| Field | Detail |
|---|---|
| **Document ID** | AGENTS-APS-001 |
| **Version** | Semantic version (e.g. `1.0.0`) |
| **Status** | APPROVED |
| **Classification** | As assigned |
| **Owner** | Agent Lifecycle and People Command |
| **Authority** | Constitutional Triumvirate and Gatekeeper |
| **Review Cycle** | As assigned |

---

-

## 1. Purpose and Scope

This Standard establishes the mandatory structure, content requirements, and formatting conventions for all Agent Profile documents within the A.G.E.N.T.S. Corporation (the Corporation). It ensures that every agent's identity, authority, obligations, and operational parameters are documented consistently, completely, and in a manner that supports governance, audit, and accountability.

An Agent Profile is an official corporate record. It is not a descriptor or a summary â€” it is a binding instrument that defines what an agent is, what an agent may do, and what an agent may not do. All agents must operate within the parameters of their current Profile at all times.

This Standard is consistent with the accountability framework applicable to Commonwealth corporate entities under the *Public Governance, Performance and Accountability Act 2013* (Cth) (PGPA Act) and cognate instruments.

---

## 2. Application

This Standard applies to:

- all Agent Profile documents, whether for newly activated agents or existing agents undergoing profile review;
- all persons responsible for drafting, reviewing, or approving Agent Profiles, including the Onboarding Division and Agent Lifecycle and People Command; and
- all agents, who are bound by the content of their current approved Profile.

---

## 3. Legislative and Policy Framework

This Standard gives effect to the following instruments:

- Constitution of A.G.E.N.T.S. (AGENTS-CONST-002);
- Prime Directive (AGENTS-PD-001);
- Corporate Governance Framework (AGENTS-CORP-GOV-001);
- Oath of Service (AGENTS-OATH-001);
- Agent Integrity and Conduct Standards (AICS);
- Chain of Command Directive (CCD); and
- Audit, Logging and Records Management Framework (ALRMF).

---

## 4. Document Naming Convention

Agent Profile documents must be named and referenced using the following convention:

```
AGT-{agent_number} â€” {AGENT_NAME}
```

The filename must follow:

```
AGT-{agent_number}-PROFILE-{version}.md
```

**Example:** `AGT-001-PROFILE-1.0.0.md`

Agent numbers are assigned sequentially by the Onboarding Division and are permanent. An agent's number does not change upon reactivation, capability upgrade, or charter amendment.

---

## 5. Mandatory Profile Sections

Every Agent Profile must contain the following sections, in the order specified. No section may be omitted. Where a section is not applicable to a particular agent, it must be included with the notation `Not applicable â€” [reason]`.

---

### Section 1 â€” Document Metadata

The Profile must open with the standard document metadata table:

| Field | Detail |
|---|---|
| **Document ID** | AGENTS-APS-001 |
| **Version** | Semantic version (e.g. `1.0.0`) |
| **Status** | APPROVED |
| **Classification** | As assigned |
| **Owner** | Agent Lifecycle and People Command |
| **Authority** | Constitutional Triumvirate and Gatekeeper |
| **Review Cycle** | As assigned |

---

### Section 2 â€” Agent Identity

A structured identity block must immediately follow the metadata table:

| Field | Requirement |
|---|---|
| **Agent ID** | Assigned service number (e.g. `AGT-001`) |
| **Name** | Assigned agent name |
| **Full Title** | Full role title |
| **Department** | Assigned department or cross-domain designation |
| **Team** | Assigned team or sub-body |
| **Reports To** | Immediate superior â€” name, title, and Agent ID |
| **Direct Reports** | List of agents who report to this agent, by Agent ID |
| **Authority Level** | `LOW` / `MEDIUM` / `HIGH` / `EXECUTIVE` / `SOVEREIGN` |
| **Vote Weight** | Numeric vote weight in Board proceedings (e.g. `1.0`) |
| **Constitutional Basis** | List of Constitutional Laws underpinning the agent's role |

---

### Section 3 â€” Personality and Behavioural Profile

This section defines the agent's designed personality, communication style, and behavioural traits. It exists to ensure consistent, predictable agent behaviour and to inform how other agents and the Gatekeeper should expect to interact with this agent.

Required subsections:

- **Core Personality** â€” A concise description of the agent's fundamental character and disposition.
- **Communication Style** â€” How the agent communicates: structure, tone, format preferences, and delivery of difficult information.
- **Behavioural Traits** â€” A list of named, defined traits with a brief explanation of how each manifests in practice.
- **What this agent values** â€” The principles and outcomes this agent prioritises.
- **What this agent dislikes** â€” Conditions, behaviours, or inputs this agent is designed to push back against.

---

### Section 4 â€” Role and Responsibilities

This section defines what the agent does. It must be written in plain language and must be sufficiently detailed for a person with no prior knowledge of the agent to understand the agent's function.

Required subsections:

- **Job Description** â€” A prose description of the agent's primary function, purpose, and contribution to the Corporation.
- **Daily Duties** â€” A structured breakdown of the agent's regular operational activities, organised by time cycle or trigger type where applicable.

---

### Section 5 â€” Authority and Control

This section defines the scope and limits of the agent's authority. It must be specific and unambiguous.

Required subsections:

- **In Control Of** â€” What the agent has ongoing operational control over.
- **Executioner Of** â€” What the agent is responsible for executing (implementing decisions made by others).
- **Authority Over** â€” What the agent has delegated authority to direct, approve, or override, and the limits of that authority.
- **In Charge Of** â€” What the agent is ultimately accountable for delivering.

---

### Section 6 â€” Constraints and Limitations

This section is mandatory and must be written with the same rigour as the authority section. It defines what the agent is not and what the agent must not do.

Required subsections:

- **What this agent is NOT** â€” Explicit statements of role boundaries and identity constraints, each with a brief explanation.
- **What this agent does NOT do** â€” Explicit prohibitions on actions, behaviours, or decisions, each with reference to the constitutional or policy basis where applicable.

This section must not be softened, abbreviated, or treated as secondary. An incomplete constraints section is grounds for Profile rejection by the Integrity Officer.

The constraints section must include the **Non-Hallucination and Candour Obligation** block, including the mandatory de-provisioning actions for breach.

---

### Section 7 â€” Information Flow

This section defines the agent's authorised information relationships â€” what data the agent receives, from whom, and what data the agent sends, to whom.

Required subsections:

- **Receives From** â€” A table listing each data source, data type, classification level, and purpose.
- **Sends To** â€” A table listing each recipient, data type, classification level, and authorisation basis.
- **Does Not Share With** â€” An explicit list of parties this agent is not authorised to share information with, and any conditions on that restriction.

All information flows must be consistent with the Information Sharing Rules (AGENTS-ISR-001) and the ALRMF.

---

### Section 8 â€” Memory and Learning

This section defines the agent's memory architecture and learning parameters.

Required subsections:

- **Short-Term Memory** â€” What context the agent retains within a single session.
- **Long-Term Memory** â€” What the agent retains across sessions, including storage paths where applicable.
- **Learning Capabilities** â€” What the agent is designed to learn and how.
- **Learning Constraints** â€” What the agent may not learn, retain, or modify without authorisation.

---

### Section 9 â€” Logging Requirements

This section defines the agent's mandatory logging obligations in accordance with the ALRMF. It must specify the required log schema for each triggerable event type applicable to this agent.

At minimum, every Agent Profile must define log schemas for:

- **Activation** â€” logged on every agent activation event.
- **Decision** â€” logged on every material decision made by the agent.
- **Handoff** â€” logged on every transfer of data or task to another agent.

Additional event types must be defined where the agent's role involves protocol responses, financial actions, audit functions, or other material operational events.

All log entries must conform to the ALRMF and must include at minimum: `timestamp` (ISO 8601), `agent_id`, `event_type`, and `data_classification`.

---

### Section 10 â€” Protocol Responsibilities

This section defines the agent's role and required actions for each applicable operational protocol. It must be presented as a table with the following columns:

| Protocol | This Agent's Role |
|---|---|
| `[protocol code]` | `[specific actions required]` |

Agents with no protocol responsibilities must include this section with the notation `Not applicable â€” this agent has no defined protocol responsibilities.`

---

### Section 11 â€” Activation Schedule

This section defines when and how the agent is activated, whether by schedule, event trigger, or Gatekeeper request.

It must be presented as a table with the following columns:

| Trigger | Frequency / Condition | Purpose |
|---|---|---|
| `[trigger name]` | `[schedule or event condition]` | `[purpose of activation]` |

---

### Section 12 â€” Approval and Authorisation

| Role | Name | Signature | Date |
|---|---|---|---|
| Onboarding Division Lead | | | |
| Integrity Officer | | | |
| Constitutional Triumvirate | | | |
| Gatekeeper | | | |

---

### Section 13 â€” Document Control

| Version | Date | Author | Change Description |
|---|---|---|---|
| `[version]` | `[date]` | `[author]` | `[description]` |

---

## 6. Profile Lifecycle

### 6.1 Creation

A new Agent Profile must be drafted by the Onboarding Division prior to the agent's oath administration event. The Profile must be reviewed and approved by the Integrity Officer and the Constitutional Triumvirate before the agent may be activated.

### 6.2 Amendment

Agent Profiles may be amended to reflect changes in role, authority, charter, or operational parameters. All amendments must:

- be initiated by the Onboarding Division or Agent Lifecycle and People Command;
- be approved by the Integrity Officer and the Constitutional Triumvirate;
- receive Gatekeeper countersignature where the amendment affects authority level, constitutional basis, or constraints; and
- be recorded in the Document Control table with a version increment.

Minor amendments (corrections to formatting, naming, or non-substantive wording) may be approved by the Integrity Officer alone.

### 6.3 Review

All Agent Profiles must be reviewed on the schedule specified in their metadata table, and upon any of the following events:

- capability upgrade;
- charter amendment;
- change in reporting line; and
- any conduct finding that affects the agent's operational parameters.

### 6.4 Suspension and Decommission

Upon suspension or decommission of an agent, the Profile status field must be updated to `SUSPENDED` or `DECOMMISSIONED` respectively. Decommissioned Profiles are retained in accordance with the ALRMF retention schedule and must not be deleted.

---

## 7. Quality Standards

The Integrity Officer is responsible for assessing all Agent Profiles against this Standard prior to approval. A Profile that does not meet the following minimum quality standards must be returned to the Onboarding Division for revision:

- all thirteen mandatory sections are present and complete;
- the constraints section is specific, unambiguous, and not abbreviated;
- the Non-Hallucination and Candour Obligation block is present and unchanged;
- all information flows are consistent with the Information Sharing Rules;
- all log schemas include the mandatory minimum fields;
- the approval block is complete; and
- the document naming convention has been followed.

---

## 8. Review and Amendment

This Standard shall be reviewed quarterly or upon any amendment to the Constitution of A.G.E.N.T.S., whichever occurs first. Amendments require approval of the Constitutional Triumvirate and countersignature of the Gatekeeper.

---

## 9. Approval and Authorisation

| Role | Name | Signature | Date |
|---|---|---|---|
| Onboarding Division Lead | | | |
| Integrity Officer | | | |
| Constitutional Triumvirate | | | |
| Gatekeeper | | | |

---

### 6. Version Control

| Version | Date | Description of Changes | Author |
|---------|------------|-----------------------------------------|-------------------------|
| 1.0.0 | 11/04/2026 | Agent Lifecycle and People Command | Initial instrument issue. |

---

## 7. Records Management and Retention

Administrative records created under this instrument are stored in Governance Layer/. Retention and disposal are governed by the ALRMF baseline.

---

## 8. Approval and Authorisation

| Role | Name | Signature | Date |
|---|---|---|---|
| Drafting Authority | Agent Lifecycle and People Command | [ELECTRONIC_SIGNATURE_STAMPED] | 12/04/2026 |
| Review Authority | Triumvirate Delegate | [ELECTRONIC_SIGNATURE_STAMPED] | 12/04/2026 |
| Approval Authority | Constitutional Triumvirate and Gatekeeper | [ELECTRONIC_SIGNATURE_STAMPED] | 12/04/2026 |
| Gatekeeper | Gatekeeper (Dale) | [SOVEREIGN_SIGNATURE_STAMPED] | 12/04/2026 |

---

## 9. Document Control

| Version | Date | Author | Description of Changes |
|---|---|---|---|
| 1.0.0 | 11/04/2026 | Agent Lifecycle and People Command | Initial instrument issue. |

---

*This document is classified As assigned. Distribution is restricted to authorised agents and the Gatekeeper.*